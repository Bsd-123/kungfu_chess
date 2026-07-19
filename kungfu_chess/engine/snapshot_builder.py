from __future__ import annotations
from typing import Optional

from kungfu_chess.config import GameConfig
from kungfu_chess.model.game_state import GameState
from kungfu_chess.model.position import Position
from kungfu_chess.realtime.motion import PendingMove
from kungfu_chess.realtime.collision_handler import CollisionHandler
from kungfu_chess.view.game_snapshot import GameSnapshot, PieceSnapshot

__all__ = ["SnapshotBuilder"]


class SnapshotBuilder:
    """Assembles the read-only GameSnapshot DTO handed to a renderer; does not expose
    live Board/Piece objects. In-flight motions are represented via `motion_progress`/
    `dst_pixel_x`/`dst_pixel_y` rather than live position. Shares the same
    `CollisionHandler` instance as `GameEngine.settle()` for landing-preview logic."""

    def __init__(self, state: GameState, config: GameConfig, collision_handler: CollisionHandler):
        self._state = state
        self._config = config
        self._collision_handler = collision_handler

    # `piece.state` is dead (get_piece_at reconstructs a fresh Piece each call), so
    # animation state is derived from the arbiter's pending-motions list instead.
    def _pending_motion_at(self, pos: Position) -> Optional[PendingMove]:
        return next((m for m in self._state.arbiter.pending_moves if m.src == pos), None)

    def build(self) -> GameSnapshot:
        board = self._state.board
        cell = self._config.cell_pixel_size
        pieces = []
        for row in range(board.nrows):
            for col in range(board.ncols):
                piece = board.get_piece_at(Position(row, col))
                if piece is None:
                    continue

                motion = self._pending_motion_at(Position(row, col))
                if motion is None:
                    state, progress = GameConfig.MOTION_STATE_IDLE, 1.0
                    dst_x, dst_y = None, None
                else:
                    state = motion.move_type  # "move" or "jump"
                    span = motion.complete_time - motion.start_time
                    progress = 1.0 if span <= 0 else min(1.0, max(0.0,
                        (self._state.clock_ms - motion.start_time) / span))
                    if motion.move_type == GameConfig.MOTION_STATE_MOVE and motion.dst is not None:
                        # Live preview against current occupancy, not the originally
                        # requested square, so a sliding piece stops/captures visually
                        # at the right spot instead of gliding through to motion.dst.
                        preview_square = self._collision_handler.preview_landing_square(
                            motion, board, self._state.arbiter.pending_moves)
                        dst_x = preview_square[1] * cell
                        dst_y = preview_square[0] * cell
                    else:
                        dst_x, dst_y = None, None

                # None if not cooling down, else 0.0->1.0 elapsed fraction for the
                # renderer's cooldown-wheel animation.
                cooldown_progress = self._state.arbiter.cooldown_progress(
                    Position(row, col), self._state.clock_ms)

                pieces.append(PieceSnapshot(
                    kind=piece.kind,
                    color=piece.color,
                    pixel_x=col * cell,
                    pixel_y=row * cell,
                    state=state,
                    motion_progress=progress,
                    dst_pixel_x=dst_x,
                    dst_pixel_y=dst_y,
                    cooldown_progress=cooldown_progress,
                ))

        return GameSnapshot(
            board_width=board.ncols,
            board_height=board.nrows,
            pieces=pieces,
            selected=self._state.selected,
            game_over=self._state.game_over,
            winner=self._state.winner_color,
        )
