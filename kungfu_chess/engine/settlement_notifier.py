from __future__ import annotations
from typing import Callable, List

from kungfu_chess.realtime.settlement_data import SettlementDataInterface

__all__ = ["SettlementNotifier"]


class SettlementNotifier:
    """Owns the settlement-listener list and fan-out; `GameEngine.settle()` decides
    when to notify. Typed against `SettlementDataInterface`, not the engine-internal
    `SettlementEvent`, so listeners never depend on live `Piece` references."""

    def __init__(self):
        self._listeners: List[Callable[[SettlementDataInterface], None]] = []

    def add_listener(self, listener: Callable[[SettlementDataInterface], None]) -> None:
        self._listeners.append(listener)

    def notify(self, event: SettlementDataInterface) -> None:
        for listener in self._listeners:
            listener(event)
