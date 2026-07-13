from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List, Optional

from kungfu_chess.model.piece import Piece
from kungfu_chess.model.position import Position

__all__ = ["BoardInterface", "ArrayBoard", "Position"]


def _direction(a: int, b: int) -> int:
    return (b > a) - (b < a)


class BoardInterface(ABC):
    """Abstract board API. The rest of the engine only ever talks to a
    board through this interface, so both the underlying storage
    mechanism (text grid today, packed/binary representation tomorrow)
    AND the piece representation it hands back (a `Piece` value object,
    never a raw token string) can change without touching any calling
    code."""

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
    def path_clear(self, src: Position, dst: Position) -> bool:
        """True if every square strictly between src and dst (in a
        straight line, orthogonal or diagonal) is empty. Exposed as a
        board capability -- rather than an external loop -- so that a
        future compact/bitmask representation can answer this natively
        and efficiently (e.g. via bitwise masks) instead of being forced
        through a generic square-by-square walk."""

    @abstractmethod
    def to_rows(self) -> List[List[str]]:
        """Snapshot the board as rows of raw tokens, for rendering/export.
        This is a serialization concern (text in, text out) and is the
        one place tokens are allowed to surface -- engine/game logic
        never calls this."""


class ArrayBoard(BoardInterface):
    """Simple 2D-list backed implementation of BoardInterface. Stores raw
    tokens internally (since that's what the text format provides and
    expects), but only ever exposes/accepts Piece objects at its public
    get/set boundary -- token slicing lives entirely inside this class."""

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
        # Engine-level bounds guard: any out-of-bounds query is treated
        # as "nothing there" rather than raising IndexError, so callers
        # elsewhere in the engine (which already validate bounds through
        # PositionArgParser/RuleEngine) get a safe, predictable answer
        # even if a bad coordinate slips through some other path.
        if not self.is_within_bounds(pos):
            return None
        r, c = pos
        token = self._grid[r][c]
        return None if token == self._empty_token else Piece.parse(token, cell=Position(r, c))

    def set_piece_at(self, pos: Position, piece: Optional[Piece]) -> None:
        # Mirror image of the get_piece_at guard: writes to an
        # out-of-bounds cell are safely dropped instead of throwing.
        if not self.is_within_bounds(pos):
            return
        r, c = pos
        self._grid[r][c] = self._empty_token if piece is None else piece.to_token()

    def is_empty_at(self, pos: Position) -> bool:
        return self.get_piece_at(pos) is None

    def path_clear(self, src: Position, dst: Position) -> bool:
        r1, c1 = src
        r2, c2 = dst
        dr = _direction(r1, r2)
        dc = _direction(c1, c2)
        r, c = r1 + dr, c1 + dc
        while (r, c) != (r2, c2):
            if not self.is_empty_at((r, c)):
                return False
            r += dr
            c += dc
        return True

    def to_rows(self) -> List[List[str]]:
        return [list(row) for row in self._grid]
