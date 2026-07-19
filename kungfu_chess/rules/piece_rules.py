from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Callable, Tuple

from kungfu_chess.model.board import BoardInterface
from kungfu_chess.model.position import Position
from kungfu_chess.model.piece import Piece


class MovementRule(ABC):
    """Strategy interface for a piece type's movement rule."""

    @abstractmethod
    def is_legal_move(self, board: BoardInterface, piece: Piece,
                       src: Position, dst: Position) -> bool:
        ...


class BaseMovementRule(MovementRule):
    """Common checks (no staying put, no capturing own piece); subclasses define shape."""

    def is_legal_move(self, board, piece, src, dst):
        if src == dst:
            return False
        dest_piece = board.get_piece_at(dst)
        if dest_piece is not None and dest_piece.color == piece.color:
            return False
        return self._is_shape_legal(board, piece, src, dst)

    @staticmethod
    def _delta(src: Position, dst: Position) -> Tuple[int, int]:
        """Row/column displacement of dst relative to src."""
        return dst[0] - src[0], dst[1] - src[1]

    @abstractmethod
    def _is_shape_legal(self, board, piece, src, dst) -> bool:
        ...


class KingMovementRule(BaseMovementRule):
    def _is_shape_legal(self, board, piece, src, dst):
        dr, dc = self._delta(src, dst)
        return max(abs(dr), abs(dc)) == 1


class RookMovementRule(BaseMovementRule):
    def _is_shape_legal(self, board, piece, src, dst):
        dr, dc = self._delta(src, dst)
        return dr == 0 or dc == 0


class BishopMovementRule(BaseMovementRule):
    def _is_shape_legal(self, board, piece, src, dst):
        dr, dc = self._delta(src, dst)
        return abs(dr) == abs(dc)


class QueenMovementRule(BaseMovementRule):
    def _is_shape_legal(self, board, piece, src, dst):
        dr, dc = self._delta(src, dst)
        return dr == 0 or dc == 0 or abs(dr) == abs(dc)


class KnightMovementRule(BaseMovementRule):
    def _is_shape_legal(self, board, piece, src, dst):
        dr, dc = self._delta(src, dst)
        return (abs(dr), abs(dc)) in [(1, 2), (2, 1)]


# Returns (forward_direction, start_row) for a given color/board.
PawnDirectionProvider = Callable[[str, BoardInterface], Tuple[int, int]]


def default_pawn_direction_provider(color: str, board: BoardInterface) -> Tuple[int, int]:
    """White pawns advance toward row 0, starting on the second-to-last row;
    black pawns advance toward the last row, starting on the second row."""
    if color == 'w':
        return -1, board.nrows - 2
    return 1, 1


class PawnMovementRule(BaseMovementRule):
    def __init__(self, direction_provider: PawnDirectionProvider = default_pawn_direction_provider):
        self._direction_provider = direction_provider

    def _is_shape_legal(self, board, piece, src, dst):
        direction, start_row = self._direction_provider(piece.color, board)
        dr, dc = self._delta(src, dst)
        dest_piece = board.get_piece_at(dst)

        if dc == 0:
            if dr == direction:
                return dest_piece is None
            if dr == 2 * direction and src[0] == start_row:
                # Path-blocking is resolved later by RealTimeArbiter, not here.
                return dest_piece is None
            return False

        if abs(dc) == 1 and dr == direction:
            return dest_piece is not None and dest_piece.color != piece.color

        return False