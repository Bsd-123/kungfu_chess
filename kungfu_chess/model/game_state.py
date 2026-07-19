from __future__ import annotations
from typing import List, Optional

from kungfu_chess.model.board import BoardInterface
from kungfu_chess.model.position import Position
from kungfu_chess.model.piece import Piece
from kungfu_chess.config import GameConfig
from kungfu_chess.realtime.real_time_arbiter import RealTimeArbiter


class GameState:
    """Pure model: board, arbiter, selection, clock, game-over flag. No
    validation/promotion/settlement/formatting logic lives here.
    `game_over`/`winner_color` change only together via `mark_game_over`."""

    def __init__(self, board: BoardInterface, config: GameConfig,
                 arbiter: Optional[RealTimeArbiter] = None):
        self.board = board
        self.config = config
        self.selected: Optional[Position] = None
        self._clock_ms = 0
        self.arbiter = arbiter or RealTimeArbiter()
        self.output_chunks: List[str] = []
        self._game_over = False

        # 'w'/'b' whose move triggered the win, or None until game ends.
        self._winner_color: Optional[str] = None

    @property
    def nrows(self) -> int:
        return self.board.nrows

    @property
    def ncols(self) -> int:
        return self.board.ncols

    @property
    def clock_ms(self) -> int:
        return self._clock_ms

    @property
    def game_over(self) -> bool:
        return self._game_over

    @property
    def winner_color(self) -> Optional[str]:
        return self._winner_color

    def advance_clock(self, ms: int) -> None:
        self._clock_ms += ms

    def mark_game_over(self, winner_color: Optional[str]) -> None:
        """Sets `game_over` and `winner_color` together; only place either changes."""
        self._game_over = True
        self._winner_color = winner_color

    def is_piece_busy(self, src: Position) -> bool:
        return self.arbiter.is_piece_busy(src, self.clock_ms)

    def is_target_busy(self, dst: Position) -> bool:
        """Whether some other Motion is already converging on dst."""
        return self.arbiter.is_target_busy(dst, self.clock_ms)

    def is_active_airborne_at(self, cell: Position) -> bool:
        return self.arbiter.is_active_airborne_at(cell, self.clock_ms)

    def is_cooling_down(self, pos: Position) -> bool:
        return self.arbiter.is_cooling_down(pos, self.clock_ms)

    def schedule_move(self, src: Position, dst: Position, piece: Piece,
                       duration_ms: int, cooldown_ms: int = 0) -> None:
        """Schedules a move Motion with the RealTimeArbiter."""
        self.arbiter.schedule_move(src, dst, piece, self.clock_ms,
                                    duration_ms, self.board, cooldown_ms)

    def schedule_jump(self, pos: Position, piece: Piece,
                       duration_ms: int, cooldown_ms: int = 0) -> None:
        """Schedules a jump Motion with the RealTimeArbiter."""
        self.arbiter.schedule_jump(pos, piece, self.clock_ms,
                                    duration_ms, cooldown_ms)
