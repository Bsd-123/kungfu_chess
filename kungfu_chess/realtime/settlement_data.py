from __future__ import annotations
from typing import Optional, Protocol, runtime_checkable

from kungfu_chess.model.position import Position

__all__ = ["SettlementDataInterface"]


@runtime_checkable
class SettlementDataInterface(Protocol):
    """Read-only, dry-data view of a settled motion (move or jump); what `GameEngine.add_settlement_listener` is
    typed against instead of the engine-internal `SettlementEvent`. Exposes only plain values (no live `Piece`).
    Structural (PEP 544) -- `SettlementEvent` satisfies this by attribute shape, not inheritance."""

    @property
    def move_type(self) -> str:
        """'move' or 'jump'."""
        ...

    @property
    def src(self) -> Position:
        """Square the settled motion started from."""
        ...

    @property
    def dst(self) -> Position:
        """Actual landing square (may differ from requested, e.g. a truncated slide)."""
        ...

    @property
    def requested_dst(self) -> Optional[Position]:
        """Originally requested destination (move-only); None for jumps."""
        ...

    @property
    def piece_color(self) -> str:
        ...

    @property
    def piece_kind(self) -> str:
        ...

    @property
    def captured_piece_kind(self) -> Optional[str]:
        """None if this settlement was not a capture."""
        ...
