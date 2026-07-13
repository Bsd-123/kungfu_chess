from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Callable, Tuple

from kungfu_chess.model.board import BoardInterface
from kungfu_chess.model.position import Position
from kungfu_chess.model.piece import Piece


class MovementRule(ABC):
    """Strategy interface for a piece type's movement rule. New piece
    types / custom games plug in new implementations without any engine
    changes."""

    @abstractmethod
    def is_legal_move(self, board: BoardInterface, piece: Piece,
                       src: Position, dst: Position) -> bool:
        ...


class BaseMovementRule(MovementRule):
    """Factors out the checks common to nearly every piece: can't stay
    put, can't capture your own piece. Subclasses only define shape.
    Operates entirely on Piece attributes (`.color`, `.type`) -- never
    on raw token characters -- so it stays correct regardless of how
    the board stores pieces internally."""

    def is_legal_move(self, board, piece, src, dst):
        if src == dst:
            return False
        dest_piece = board.get_piece_at(dst)
        if dest_piece is not None and dest_piece.color == piece.color:
            return False
        return self._is_shape_legal(board, piece, src, dst)

    @abstractmethod
    def _is_shape_legal(self, board, piece, src, dst) -> bool:
        ...


class KingMovementRule(BaseMovementRule):
    def _is_shape_legal(self, board, piece, src, dst):
        dr = dst[0] - src[0]
        dc = dst[1] - src[1]
        return max(abs(dr), abs(dc)) == 1


class RookMovementRule(BaseMovementRule):
    def _is_shape_legal(self, board, piece, src, dst):
        dr = dst[0] - src[0]
        dc = dst[1] - src[1]
        if dr != 0 and dc != 0:
            return False
        return board.path_clear(src, dst)


class BishopMovementRule(BaseMovementRule):
    def _is_shape_legal(self, board, piece, src, dst):
        dr = dst[0] - src[0]
        dc = dst[1] - src[1]
        if abs(dr) != abs(dc):
            return False
        return board.path_clear(src, dst)


class QueenMovementRule(BaseMovementRule):
    def _is_shape_legal(self, board, piece, src, dst):
        dr = dst[0] - src[0]
        dc = dst[1] - src[1]
        if dr != 0 and dc != 0 and abs(dr) != abs(dc):
            return False
        return board.path_clear(src, dst)


class KnightMovementRule(BaseMovementRule):
    def _is_shape_legal(self, board, piece, src, dst):
        dr = abs(dst[0] - src[0])
        dc = abs(dst[1] - src[1])
        return (dr, dc) in [(1, 2), (2, 1)]


# A pawn direction provider returns (forward_direction, start_row) for a
# given color and board. Injecting this lets custom games flip pawn
# direction, change starting rows, etc. without editing PawnMovementRule.
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
        dr = dst[0] - src[0]
        dc = dst[1] - src[1]
        dest_piece = board.get_piece_at(dst)

        if dc == 0:
            if dr == direction:
                return dest_piece is None
            if dr == 2 * direction and src[0] == start_row:
                mid = (src[0] + direction, src[1])
                return board.is_empty_at(mid) and dest_piece is None
            return False

        if abs(dc) == 1 and dr == direction:
            return dest_piece is not None and dest_piece.color != piece.color

        return False
