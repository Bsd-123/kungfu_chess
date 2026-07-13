from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from kungfu_chess.model.position import Position


@dataclass(frozen=True)
class Piece:
    """Immutable value object representing a piece.

    `color` and `type` are the original, load-bearing fields -- every
    existing call site (`piece.color`, `piece.type`, `Piece.parse`,
    `to_token`) keeps working exactly as before.

    `id`, `cell`, and `state` are added to satisfy Spec §6 (stable
    identity + idle/moving/captured lifecycle flag) but default to values
    that make two pieces built the old way (`Piece(color=.., type=..)`)
    compare equal exactly as they did before this change, so nothing
    downstream that relies on Piece equality (e.g. the arbiter's
    "is the piece still where we think it is" check) breaks.

    `state` is only a lifecycle flag, per spec -- it never stores path,
    destination, elapsed time, or interpolation data. That belongs to
    Motion / RealTimeArbiter.
    """

    color: str
    type: str
    id: Optional[str] = None
    cell: Optional[Position] = None
    state: str = 'idle'

    @property
    def kind(self) -> str:
        """Spec-vocabulary alias for `type` (§6 calls the field `kind`).
        Kept as a read-only alias rather than a rename so no existing
        code that reads `.type` has to change."""
        return self.type

    @staticmethod
    def parse(token: str, id: Optional[str] = None,
              cell: Optional[Position] = None) -> "Piece":
        return Piece(color=token[0], type=token[1], id=id, cell=cell)

    def to_token(self) -> str:
        return f"{self.color}{self.type}"

    def with_state(self, state: str) -> "Piece":
        """Returns a copy with an updated lifecycle state, leaving
        identity/color/type/cell untouched."""
        return Piece(color=self.color, type=self.type, id=self.id,
                     cell=self.cell, state=state)
