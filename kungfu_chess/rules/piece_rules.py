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


# NOTE on real-time collision handling: sliding pieces (Rook/Bishop/
# Queen) used to gate legality on `board.path_clear(src, dst)` -- "is
# every square between here and there empty *right now*". In Kung Fu
# Chess that question no longer has a single meaningful answer at
# request time: the board several hundred ms from now (when the piece
# actually reaches those squares) is not the board right now, and a
# piece already travelling toward one of those squares may vacate or
# occupy it before this move gets there. So these rules now validate
# shape only; whether the path is actually clear when the piece gets
# there is resolved dynamically, square by square, by
# RealTimeArbiter._advance_through_path at settlement time (a same-
# color occupant truncates the move there, a different-color occupant
# is captured there). `board.path_clear` is kept on BoardInterface for
# any caller that still wants a static "is it clear right now" read.


class RookMovementRule(BaseMovementRule):
    def _is_shape_legal(self, board, piece, src, dst):
        dr = dst[0] - src[0]
        dc = dst[1] - src[1]
        return dr == 0 or dc == 0


class BishopMovementRule(BaseMovementRule):
    def _is_shape_legal(self, board, piece, src, dst):
        dr = dst[0] - src[0]
        dc = dst[1] - src[1]
        return abs(dr) == abs(dc)


class QueenMovementRule(BaseMovementRule):
    def _is_shape_legal(self, board, piece, src, dst):
        dr = dst[0] - src[0]
        dc = dst[1] - src[1]
        return dr == 0 or dc == 0 or abs(dr) == abs(dc)


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
                # Mid-square occupancy is no longer checked here for the
                # same reason sliding pieces dropped their path_clear
                # gate above: it's resolved dynamically at settlement
                # time via RealTimeArbiter._advance_through_path, not
                # upfront against the current board.
                return dest_piece is None
            return False

        if abs(dc) == 1 and dr == direction:
            return dest_piece is not None and dest_piece.color != piece.color

        return False
