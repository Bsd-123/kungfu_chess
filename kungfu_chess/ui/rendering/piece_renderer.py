"""Phase 1 step 2/3, extended in Phase 4 for interpolation + the
per-piece animation state machine (final_plan_verified.md). Instead of
one static sprite cached per (color, kind), each *currently-occupied
cell* gets its own `AnimatedSprite` instance (state pattern), tracked
across frames so breathing/motion/cooldown timers stay continuous for
that piece.

Keying by current cell (rather than a stable piece id -- ArrayBoard
reconstructs a fresh Piece via Piece.parse on every read, so there is
no stable identity to key on) works cleanly given how the engine
reports position during a motion (Rule 10): `pixel_x`/`pixel_y` stay
pinned to the *source* cell for a piece's entire "move" flight, only
jumping to the destination cell in the same snapshot where it settles.
A jump's src never changes at all (it lands back on its own square).
The only imperfection is a fresh (cold) AnimatedSprite starting up at
the destination cell the instant a "move" settles -- invisible in
practice since the animation goes straight into breathing "idle" there.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from kungfu_chess.model.position import Position
from kungfu_chess.ui.events.events import MoveResolvedEvent
from kungfu_chess.ui.img import Img
from kungfu_chess.ui.sprites.animated_sprite import AnimatedSprite
from kungfu_chess.ui.sprites.sprite_library import SpriteLibrary
from kungfu_chess.view.game_snapshot import GameSnapshot, PieceSnapshot

JUMP_HOP_HEIGHT_PX = 18
FADE_DURATION_MS = 220.0

# Animation snap-back feature (design decision #2): how long the
# corrective slide takes when a sliding move settles somewhere other
# than where it was requested to go. Short on purpose -- "fast slide",
# not a leisurely rebound -- but never an instant pop.
CORRECTION_DURATION_MS = 180.0


@dataclass
class _Tracked:
    color: str
    kind: str
    sprite: AnimatedSprite
    last_state: str = "idle"
    last_dst: Optional[Tuple[int, int]] = None
    last_render_pos: Tuple[int, int] = (0, 0)


@dataclass
class _FadingGhost:
    frame: Img
    x: int
    y: int
    elapsed_ms: float = 0.0


@dataclass
class _Correction:
    """A brief corrective slide, played instead of an instant snap when
    a settled move's true landing square differs from the one it had
    been animating toward the whole flight (design decision #2: a
    same-color near-miss truncation, or a mid-path capture that stopped
    the mover early -- requirements 1/2 -- both redirect a move away
    from its originally-requested destination).

    `to_x`/`to_y` is always the piece's true settled pixel position
    (where `draw()` would render it anyway, once the correction
    finishes). `from_x`/`from_y` is wherever the piece was actually
    last rendered -- mid-interpolation toward the *wrong* target -- the
    instant the settlement was reported, so the slide always starts
    exactly where the eye last saw the piece, with no visible pop at
    the start of the correction either."""
    from_x: int
    from_y: int
    to_x: int
    to_y: int
    elapsed_ms: float = 0.0

    def finished(self) -> bool:
        return self.elapsed_ms >= CORRECTION_DURATION_MS

    def position(self) -> Tuple[int, int]:
        t = min(1.0, max(0.0, self.elapsed_ms / CORRECTION_DURATION_MS))
        # Ease-out cubic: fast at first, smoothly decelerating into the
        # landing square -- "smooth deceleration/fast slide", not a
        # linear glide and not a bounce/rebound.
        eased_t = 1.0 - (1.0 - t) ** 3
        return _lerp(self.from_x, self.to_x, eased_t), _lerp(self.from_y, self.to_y, eased_t)


def _lerp(a: int, b: int, t: float) -> int:
    return int(round(a + (b - a) * t))


class PieceRenderer:
    def __init__(self, asset_root: str, cell_pixel_size: int,
                 clock: Callable[[], float] = time.perf_counter,
                 offset: Tuple[int, int] = (0, 0)):
        """`offset = (x, y)` (task 16): screen-space pixel offset of the
        board's top-left checkerboard cell, now that the board no
        longer necessarily starts at frame origin (side panels + a
        top name/score band sit to its left/above). Every other
        calculation here (`_cell_of`, interpolation, motion state)
        stays in board-space pixels exactly as the engine reports
        them via `PieceSnapshot`; the offset is added once, only at
        the final `frame.draw_on` call, so nothing upstream needs to
        know the board has moved on screen."""
        self._library = SpriteLibrary(asset_root, cell_pixel_size)
        self._cell = cell_pixel_size
        self._clock = clock
        self._offset = offset
        self._last_tick: Optional[float] = None
        self._tracked: Dict[Position, _Tracked] = {}
        self._fading: List[_FadingGhost] = []

        # Animation snap-back feature (design decision #2): corrections
        # currently playing, keyed by the cell the piece actually
        # settled on. `_redirected_from` is a short-lived side channel
        # (populated in `on_move_resolved`, consumed once by the very
        # next `draw()` call's vanished-key pass) recording "this source
        # cell's piece was authoritatively redirected, not captured" --
        # needed because the existing swallowed-piece fade-out heuristic
        # below would otherwise misread a truncated landing as a capture
        # (it never sees the true destination, only the *requested* one).
        self._correcting: Dict[Position, _Correction] = {}
        self._redirected_from: Dict[Position, Position] = {}

    def _dt_ms(self) -> float:
        now = self._clock()
        if self._last_tick is None:
            self._last_tick = now
            return 0.0
        dt = max(0.0, (now - self._last_tick) * 1000.0)
        self._last_tick = now
        return dt

    def _cell_of(self, piece: PieceSnapshot) -> Position:
        return Position(piece.pixel_y // self._cell, piece.pixel_x // self._cell)

    def _interpolated_position(self, piece: PieceSnapshot) -> Tuple[int, int]:
        if piece.state == "move" and piece.dst_pixel_x is not None:
            x = _lerp(piece.pixel_x, piece.dst_pixel_x, piece.motion_progress)
            y = _lerp(piece.pixel_y, piece.dst_pixel_y, piece.motion_progress)
            return x, y
        if piece.state == "jump":
            bump = int(round(JUMP_HOP_HEIGHT_PX *
                              math.sin(math.pi * piece.motion_progress)))
            # Clamp rather than let a top-row piece's hop push it to a
            # negative y: Img.draw_on deliberately does no clipping
            # (plan section 3 plumbing note 4 -- callers are responsible
            # for valid placement), and a negative slice start silently
            # wraps around in numpy/Python rather than erroring cleanly,
            # producing a bogus zero-height destination slice.
            return piece.pixel_x, max(0, piece.pixel_y - bump)
        return piece.pixel_x, piece.pixel_y

    # -- animation snap-back feature (design decision #2) -----------------
    def on_move_resolved(self, event: MoveResolvedEvent) -> None:
        """Settlement-event hook, subscribed via `EventBus` in
        `ui/app.py`'s `wire_event_observers` (the same pattern
        `MoveLogObserver`/`ScoreObserver` already use). Fires
        synchronously inside `engine.advance_clock`, which always
        happens *before* this tick's own `draw()` call -- so
        `self._tracked`'s `last_render_pos` for the move's source cell
        still reflects the previous frame's interpolated position,
        exactly the right starting point for a corrective slide.

        A no-op whenever the move landed exactly where it was requested
        (nothing to correct) or this is a jump (jumps aren't routed
        through `MoveResolvedEvent` at all -- see `ui/app.py`)."""
        if event.requested_dst_row is None or event.requested_dst_col is None:
            return
        if (event.requested_dst_row, event.requested_dst_col) == (event.dst_row, event.dst_col):
            return  # landed exactly where requested -- an ordinary settle

        src_cell = Position(event.src_row, event.src_col)
        dst_cell = Position(event.dst_row, event.dst_col)

        tracked = self._tracked.get(src_cell)
        if tracked is not None:
            from_x, from_y = tracked.last_render_pos
        else:
            # No frame was ever rendered for this motion (e.g. it
            # settled on the very first tick) -- fall back to the
            # requested destination's pixel position, the best guess
            # for "where it looked like it was headed".
            from_x = event.requested_dst_col * self._cell
            from_y = event.requested_dst_row * self._cell

        to_x, to_y = event.dst_col * self._cell, event.dst_row * self._cell
        self._correcting[dst_cell] = _Correction(from_x, from_y, to_x, to_y)
        # Tell the vanished-key pass below "this exact source cell's
        # disappearance is accounted for -- it redirected, it wasn't
        # captured" so it doesn't also spawn a fade-out ghost for it.
        self._redirected_from[src_cell] = dst_cell

    def draw(self, frame: Img, snapshot: GameSnapshot) -> None:
        dt_ms = self._dt_ms()
        seen: Dict[Position, PieceSnapshot] = {}

        # Advance every in-progress corrective slide (design decision
        # #2) once per frame, same dt as everything else, and retire any
        # that have finished -- from then on the piece just renders at
        # its true position like any other idle piece.
        for correction in self._correcting.values():
            correction.elapsed_ms += dt_ms
        self._correcting = {cell: c for cell, c in self._correcting.items()
                             if not c.finished()}

        for piece in snapshot.pieces:
            cell = self._cell_of(piece)
            seen[cell] = piece
            tracked = self._tracked.get(cell)
            if (tracked is None or tracked.color != piece.color
                    or tracked.kind != piece.kind):
                tracked = _Tracked(piece.color, piece.kind,
                                    AnimatedSprite(self._library, piece.color, piece.kind))
                self._tracked[cell] = tracked

            tracked.sprite.update(dt_ms, piece.state)
            tracked.last_state = piece.state
            tracked.last_dst = (
                (piece.dst_pixel_x, piece.dst_pixel_y)
                if piece.state == "move" and piece.dst_pixel_x is not None
                else None
            )

            correction = self._correcting.get(cell)
            if correction is not None and piece.state == "idle":
                # Mid corrective slide -- override the ordinary idle
                # position with the eased in-progress one.
                render_x, render_y = correction.position()
            else:
                if correction is not None:
                    # A brand new motion already started from this cell
                    # before the correction finished playing -- that
                    # motion's own interpolation takes priority.
                    del self._correcting[cell]
                render_x, render_y = self._interpolated_position(piece)

            tracked.last_render_pos = (render_x, render_y)
            off_x, off_y = self._offset
            frame.draw_on(tracked.sprite.current_frame(),
                           render_x + off_x, render_y + off_y)

        # A key tracked last frame but missing now either settled
        # normally (its key just moved to the destination cell, handled
        # as a fresh entry there above), was authoritatively redirected
        # (design decision #2 -- `on_move_resolved` already recorded it
        # in `_redirected_from` and queued its correction above, so
        # there's nothing further to do here), or was genuinely
        # swallowed mid-flight (plan section 1: an arriving move is
        # captured by an airborne jumper at its destination) -- only the
        # last of those three should ever produce a fade-out ghost.
        # Heuristic fallback for anything *not* covered by
        # `_redirected_from`: if no piece of the same color+kind shows
        # up at the recorded (requested) destination this frame, treat
        # it as swallowed. Known limitation: a promoting pawn's kind
        # changes on arrival (P -> Q), so this heuristic can't fully
        # distinguish "promoted" from "swallowed" for that one case;
        # this stays a reasonable approximation.
        vanished_keys = set(self._tracked) - set(seen)
        for key in vanished_keys:
            tracked = self._tracked.pop(key)
            if key in self._redirected_from:
                del self._redirected_from[key]
                continue  # accounted for already -- redirected, not captured
            if tracked.last_state == "move" and tracked.last_dst is not None:
                dst_x, dst_y = tracked.last_dst
                settled_normally = any(
                    p.pixel_x == dst_x and p.pixel_y == dst_y
                    and p.color == tracked.color and p.kind == tracked.kind
                    for p in snapshot.pieces
                )
                if not settled_normally:
                    ghost_x, ghost_y = tracked.last_render_pos
                    off_x, off_y = self._offset
                    self._fading.append(_FadingGhost(
                        tracked.sprite.current_frame(),
                        ghost_x + off_x, ghost_y + off_y))

        still_fading: List[_FadingGhost] = []
        for ghost in self._fading:
            ghost.elapsed_ms += dt_ms
            if ghost.elapsed_ms < FADE_DURATION_MS:
                alpha_scale = 1.0 - (ghost.elapsed_ms / FADE_DURATION_MS)
                faded = ghost.frame.copy()
                faded.array[:, :, 3] = (
                    faded.array[:, :, 3].astype("float32") * alpha_scale
                ).astype("uint8")
                frame.draw_on(faded, ghost.x, ghost.y)
                still_fading.append(ghost)
        self._fading = still_fading
