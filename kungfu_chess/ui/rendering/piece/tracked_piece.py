"""`TrackedPieceRegistry` keys tracked pieces by their current cell
(there's no stable piece id -- `ArrayBoard` reconstructs a fresh `Piece`
via `Piece.parse` on every read). This works because `pixel_x/pixel_y`
stay pinned to the source cell for the whole "move" flight, only
jumping to the destination cell once settled. Call order per frame:
`step_corrections(dt_ms)`, then `update(...)` per piece, then
`pop_vanished(seen)`."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Set, Tuple

from kungfu_chess.model.position import Position
from kungfu_chess.ui.img import Img
from kungfu_chess.ui.rendering.piece.motion_math import Correction
from kungfu_chess.ui.sprites.animated_sprite import AnimatedSprite
from kungfu_chess.ui.sprites.sprite_library import SpriteLibrary
from kungfu_chess.view.game_snapshot import PieceSnapshot


@dataclass
class TrackedPiece:
    color: str
    kind: str
    sprite: AnimatedSprite
    last_state: str = "idle"
    last_dst: Optional[Tuple[int, int]] = None
    last_render_pos: Tuple[int, int] = (0, 0)


class TrackedPieceRegistry:
    def __init__(self, library: SpriteLibrary):
        self._library = library
        self._tracked: Dict[Position, TrackedPiece] = {}
        self._correcting: Dict[Position, Correction] = {}
        self._redirected_from: Dict[Position, Position] = {}

    def last_render_pos_at(self, cell: Position) -> Optional[Tuple[int, int]]:
        tracked = self._tracked.get(cell)
        return tracked.last_render_pos if tracked is not None else None

    def register_correction(self, src_cell: Position, dst_cell: Position,
                             correction: Correction) -> None:
        """Queues a corrective slide at `dst_cell` and marks `src_cell`'s
        disappearance as a redirect, not a capture, for `pop_vanished`."""
        self._correcting[dst_cell] = correction
        self._redirected_from[src_cell] = dst_cell

    def step_corrections(self, dt_ms: float) -> None:
        """Ages in-progress corrective slides and retires finished ones. Call once per frame, before `update()`."""
        for correction in self._correcting.values():
            correction.elapsed_ms += dt_ms
        self._correcting = {cell: c for cell, c in self._correcting.items()
                             if not c.finished()}

    def update(self, piece: PieceSnapshot, cell: Position, dt_ms: float,
               interpolated_position: Callable[[PieceSnapshot], Tuple[int, int]],
               ) -> Tuple[int, int]:
        """Creates/updates the `AnimatedSprite` at `cell`, advances it by
        `dt_ms`, and returns this frame's render position (a corrective
        slide's eased position, or `interpolated_position(piece)`)."""
        tracked = self._tracked.get(cell)
        if (tracked is None or tracked.color != piece.color
                or tracked.kind != piece.kind):
            tracked = TrackedPiece(piece.color, piece.kind,
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
            render_pos = correction.position()
        else:
            if correction is not None:
                # A new motion started before the correction finished; it takes priority.
                del self._correcting[cell]
            render_pos = interpolated_position(piece)

        tracked.last_render_pos = render_pos
        return render_pos

    def current_frame(self, cell: Position) -> Img:
        return self._tracked[cell].sprite.current_frame()

    def pop_vanished(self, seen: Set[Position]) -> List[Tuple[Position, TrackedPiece]]:
        """Returns cells tracked last frame but missing from `seen`,
        excluding ones already recorded as redirects -- the remainder
        are fade-out ghost candidates (see `FadingGhostPool`)."""
        vanished_keys = set(self._tracked) - seen
        result: List[Tuple[Position, TrackedPiece]] = []
        for key in vanished_keys:
            tracked = self._tracked.pop(key)
            if key in self._redirected_from:
                del self._redirected_from[key]
                continue  # redirected, not captured
            result.append((key, tracked))
        return result
