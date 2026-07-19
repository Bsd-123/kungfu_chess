"""`FadingGhostPool` detects mid-flight captures ("swallowed" pieces,
already filtered from normal settles/redirects by
`TrackedPieceRegistry.pop_vanished`) and animates their fade-out."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from kungfu_chess.model.position import Position
from kungfu_chess.ui.img import Img
from kungfu_chess.ui.rendering.piece.tracked_piece import TrackedPiece
from kungfu_chess.view.game_snapshot import GameSnapshot


@dataclass
class FadingGhost:
    frame: Img
    x: int
    y: int
    elapsed_ms: float = 0.0


class FadingGhostPool:
    def __init__(self) -> None:
        self._fading: List[FadingGhost] = []

    def spawn_if_swallowed(self, vanished: List[Tuple[Position, TrackedPiece]],
                            snapshot: GameSnapshot, offset: Tuple[int, int]) -> None:
        """Heuristic: if no same-color+kind piece shows up at the
        recorded destination this frame, treat it as swallowed mid-flight.
        Known gap: a promoting pawn changes kind (P -> Q) on arrival, so
        this can't distinguish "promoted" from "swallowed" there."""
        off_x, off_y = offset
        for _key, tracked in vanished:
            if tracked.last_state != "move" or tracked.last_dst is None:
                continue
            dst_x, dst_y = tracked.last_dst
            settled_normally = any(
                p.pixel_x == dst_x and p.pixel_y == dst_y
                and p.color == tracked.color and p.kind == tracked.kind
                for p in snapshot.pieces
            )
            if not settled_normally:
                ghost_x, ghost_y = tracked.last_render_pos
                self._fading.append(FadingGhost(
                    tracked.sprite.current_frame(),
                    ghost_x + off_x, ghost_y + off_y))

    def step_and_draw(self, frame: Img, dt_ms: float, fade_duration_ms: float) -> None:
        still_fading: List[FadingGhost] = []
        for ghost in self._fading:
            ghost.elapsed_ms += dt_ms
            if ghost.elapsed_ms < fade_duration_ms:
                alpha_scale = 1.0 - (ghost.elapsed_ms / fade_duration_ms)
                faded = ghost.frame.copy()
                faded.array[:, :, 3] = (
                    faded.array[:, :, 3].astype("float32") * alpha_scale
                ).astype("uint8")
                frame.draw_on(faded, ghost.x, ghost.y)
                still_fading.append(ghost)
        self._fading = still_fading
