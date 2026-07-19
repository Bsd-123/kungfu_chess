"""Tracks game start/end transitions as plain state a renderer can
query to trigger start/end animations. Mirrors `MoveLogObserver`/
`ScoreObserver`'s shape -- owns no rendering, no scoring, no logging
knowledge (SRP)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from kungfu_chess.ui.events.events import GameEndedEvent, GameStartedEvent


@dataclass(frozen=True)
class LifecycleState:
    started: bool = False
    started_at_ms: Optional[int] = None
    ended: bool = False
    ended_at_ms: Optional[int] = None
    winner: Optional[str] = None


class GameLifecycleObserver:
    def __init__(self) -> None:
        self.state = LifecycleState()

    def on_game_started(self, event: GameStartedEvent) -> None:
        self.state = LifecycleState(started=True, started_at_ms=event.timestamp_ms)

    def on_game_ended(self, event: GameEndedEvent) -> None:
        self.state = LifecycleState(
            started=self.state.started, started_at_ms=self.state.started_at_ms,
            ended=True, ended_at_ms=event.timestamp_ms, winner=event.winner)
