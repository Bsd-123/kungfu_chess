from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List, Optional

from kungfu_chess.model.piece import Piece
from kungfu_chess.model.position import Position

__all__ = ["BoardInterface", "ArrayBoard", "Position"]


def _direction(a: int, b: int) -> int:
    return (b > a) - (b < a)


class BoardInterface(ABC):
    """Abstract board API; callers only ever see `Piece` objects, never raw tokens."""

    @property
    @abstractmethod
    def nrows(self) -> int:
        ...

    @property
    @abstractmethod
    def ncols(self) -> int:
        ...

    @abstractmethod
    def get_piece_at(self, pos: Position) -> Optional[Piece]:
        """Return the Piece at pos, or None if the square is empty."""

    @abstractmethod
    def set_piece_at(self, pos: Position, piece: Optional[Piece]) -> None:
        """Place a Piece at pos, or clear it if piece is None."""

    @abstractmethod
    def is_within_bounds(self, pos: Position) -> bool:
        ...

    @abstractmethod
    def is_empty_at(self, pos: Position) -> bool:
        ...

    @abstractmethod
    def get_path(self, src: Position, dst: Position) -> List[Position]:
        """Ordered squares from (excluding) src to (including) dst; non-sliding
        moves (e.g. knight) degenerate to `[dst]`. Used to resolve mid-path collisions."""

    @abstractmethod
    def to_rows(self) -> List[List[str]]:
        """Snapshot as rows of raw tokens, for rendering/export only."""


class ArrayBoard(BoardInterface):
    """2D-list backed BoardInterface; stores raw tokens internally, exposes only Piece objects."""

    def __init__(self, rows: List[List[str]], empty_token: str = '.'):
        self._grid = [list(row) for row in rows]
        self._empty_token = empty_token

    @property
    def nrows(self) -> int:
        return len(self._grid)

    @property
    def ncols(self) -> int:
        return len(self._grid[0]) if self._grid else 0

    def is_within_bounds(self, pos: Position) -> bool:
        r, c = pos
        return 0 <= r < self.nrows and 0 <= c < self.ncols

    def get_piece_at(self, pos: Position) -> Optional[Piece]:
        # Out-of-bounds queries return None instead of raising IndexError.
        if not self.is_within_bounds(pos):
            return None
        r, c = pos
        token = self._grid[r][c]
        return None if token == self._empty_token else Piece.parse(token, cell=Position(r, c))

    def set_piece_at(self, pos: Position, piece: Optional[Piece]) -> None:
        # Out-of-bounds writes are dropped instead of raising.
        if not self.is_within_bounds(pos):
            return
        r, c = pos
        self._grid[r][c] = self._empty_token if piece is None else piece.to_token()

    def is_empty_at(self, pos: Position) -> bool:
        return self.get_piece_at(pos) is None

    def get_path(self, src: Position, dst: Position) -> List[Position]:
        r1, c1 = src
        r2, c2 = dst
        dr = _direction(r1, r2)
        dc = _direction(c1, c2)
        is_straight_line = (r1 == r2) or (c1 == c2) or (abs(r2 - r1) == abs(c2 - c1))
        if not is_straight_line:
            # Non-sliding displacement: no intermediate square is passed through.
            return [Position(r2, c2)]

        path: List[Position] = []
        r, c = r1 + dr, c1 + dc
        while True:
            path.append(Position(r, c))
            if (r, c) == (r2, c2):
                break
            r += dr
            c += dc
        return path

    def to_rows(self) -> List[List[str]]:
        return [list(row) for row in self._grid]
