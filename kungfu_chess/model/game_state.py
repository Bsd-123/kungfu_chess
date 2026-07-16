from __future__ import annotations
from typing import List, Optional

from kungfu_chess.model.board import BoardInterface
from kungfu_chess.model.position import Position
from kungfu_chess.model.piece import Piece
from kungfu_chess.config import GameConfig
from kungfu_chess.realtime.real_time_arbiter import RealTimeArbiter


class GameState:
    """Pure Model (Rule 3): board, arbiter (in-flight motions), selection,
    clock and game-over flag only. GameState never validates a move,
    never decides promotion, never decides when a Motion is due to
    settle, and never formats text -- those are GameEngine/RuleEngine/
    RealTimeArbiter/BoardTextView responsibilities respectively. This
    keeps the Model completely decoupled from orchestration and
    rendering, and forwards Piece objects only, never raw tokens."""

    def __init__(self, board: BoardInterface, config: GameConfig,
                 arbiter: Optional[RealTimeArbiter] = None):
        self.board = board
        self.config = config
        self.selected: Optional[Position] = None
        self.clock_ms = 0
        self.arbiter = arbiter or RealTimeArbiter()
        self.output_chunks: List[str] = []
        self.game_over = False

    @property
    def nrows(self) -> int:
        return self.board.nrows

    @property
    def ncols(self) -> int:
        return self.board.ncols

    def is_piece_busy(self, src: Position) -> bool:
        return self.arbiter.is_piece_busy(src, self.clock_ms)

    def is_target_busy(self, dst: Position) -> bool:
        """Rule 8 Step 2: is some other Motion already converging on
        dst? Delegates entirely to the RealTimeArbiter -- GameState only
        forwards the current clock reading."""
        return self.arbiter.is_target_busy(dst, self.clock_ms)

    def is_active_airborne_at(self, cell: Position) -> bool:
        return self.arbiter.is_active_airborne_at(cell, self.clock_ms)

    def schedule_move(self, src: Position, dst: Position, piece: Piece, duration_ms: int) -> None:
        self.arbiter.schedule_move(src, dst, piece, self.clock_ms, duration_ms, self.board)

    def schedule_jump(self, src: Position, piece: Piece, duration_ms: int) -> None:
        # Deliberately does NOT clear the board cell: the piece must
        # stay visible/renderable at its square for the whole hover (the
        # snapshot layer only ever draws what board.get_piece_at
        # returns). "Vacant for collision purposes while airborne"
        # (requirement 3) is instead a property the Arbiter's path-walk
        # asks for explicitly via `is_active_airborne_at`, layered on
        # top of the literal board content -- see
        # RealTimeArbiter._advance_through_path -- rather than something
        # achieved by actually removing the piece from the board.
        self.arbiter.schedule_jump(src, piece, self.clock_ms, duration_ms)
