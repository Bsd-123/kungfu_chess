from __future__ import annotations
from typing import Callable, List, Optional

__all__ = ["GameLifecycleNotifier"]

GameEndedListener = Callable[[Optional[str], int], None]


class GameLifecycleNotifier:
    """Owns the game-ended-listener list and fan-out; `GameEngine` decides
    when to notify. Listeners receive only primitive values (winner_color,
    clock_ms), never live `Piece`/`GameState` references -- same convention
    as `SettlementNotifier`."""

    def __init__(self) -> None:
        self._listeners: List[GameEndedListener] = []

    def add_listener(self, listener: GameEndedListener) -> None:
        self._listeners.append(listener)

    def notify_game_ended(self, winner_color: Optional[str], clock_ms: int) -> None:
        for listener in self._listeners:
            listener(winner_color, clock_ms)
