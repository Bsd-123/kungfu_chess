from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from kungfu_chess.model.position import Position


@dataclass(frozen=True)
class Piece:
    """Immutable value object representing a piece. `state` is a lifecycle
    flag only (idle/moving/captured); motion data lives in Motion/RealTimeArbiter."""

    color: str
    type: str
    id: Optional[str] = None
    cell: Optional[Position] = None
    state: str = 'idle'

    @property
    def kind(self) -> str:
        """Read-only alias for `type`."""
        return self.type

    @staticmethod
    def parse(token: str, id: Optional[str] = None,
              cell: Optional[Position] = None) -> "Piece":
        return Piece(color=token[0], type=token[1], id=id, cell=cell)

    def to_token(self) -> str:
        return f"{self.color}{self.type}"

    def with_state(self, state: str) -> "Piece":
        """Returns a copy with an updated lifecycle state."""
        return Piece(color=self.color, type=self.type, id=self.id,
                     cell=self.cell, state=state)
