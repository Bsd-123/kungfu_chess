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
from kungfu_chess.ui.img import Img
from kungfu_chess.ui.sprites.animated_sprite import AnimatedSprite
from kungfu_chess.ui.sprites.sprite_library import SpriteLibrary
from kungfu_chess.view.game_snapshot import GameSnapshot, PieceSnapshot

JUMP_HOP_HEIGHT_PX = 18
FADE_DURATION_MS = 220.0


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


def _lerp(a: int, b: int, t: float) -> int:
    return int(round(a + (b - a) * t))


class PieceRenderer:
    def __init__(self, asset_root: str, cell_pixel_size: int,
                 clock: Callable[[], float] = time.perf_counter):
        self._library = SpriteLibrary(asset_root, cell_pixel_size)
        self._cell = cell_pixel_size
        self._clock = clock
        self._last_tick: Optional[float] = None
        self._tracked: Dict[Position, _Tracked] = {}
        self._fading: List[_FadingGhost] = []

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

    def draw(self, frame: Img, snapshot: GameSnapshot) -> None:
        dt_ms = self._dt_ms()
        seen: Dict[Position, PieceSnapshot] = {}

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

            render_x, render_y = self._interpolated_position(piece)
            tracked.last_render_pos = (render_x, render_y)
            frame.draw_on(tracked.sprite.current_frame(), render_x, render_y)

        # A key tracked last frame but missing now either settled
        # normally (its key just moved to the destination cell, handled
        # as a fresh entry there above) or was swallowed mid-flight
        # (plan section 1: an arriving move is captured by an airborne
        # jumper at its destination) -- detect the latter and fade it
        # out instead of letting it vanish with zero visual feedback.
        # Heuristic: if no piece of the *same color+kind* shows up at
        # the recorded destination this frame, treat it as swallowed.
        # Known limitation: a promoting pawn's kind changes on arrival
        # (P -> Q), so this heuristic can't fully distinguish "promoted"
        # from "swallowed" -- Phase 5's SettlementEvent/Observer hook
        # (which reports exactly what happened) is the precise fix;
        # this stays a reasonable approximation until then.
        vanished_keys = set(self._tracked) - set(seen)
        for key in vanished_keys:
            tracked = self._tracked.pop(key)
            if tracked.last_state == "move" and tracked.last_dst is not None:
                dst_x, dst_y = tracked.last_dst
                settled_normally = any(
                    p.pixel_x == dst_x and p.pixel_y == dst_y
                    and p.color == tracked.color and p.kind == tracked.kind
                    for p in snapshot.pieces
                )
                if not settled_normally:
                    ghost_x, ghost_y = tracked.last_render_pos
                    self._fading.append(_FadingGhost(
                        tracked.sprite.current_frame(), ghost_x, ghost_y))

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
