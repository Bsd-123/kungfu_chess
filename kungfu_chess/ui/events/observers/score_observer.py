"""Tracks per-color score from captures, keyed on single-character piece
codes (`"P"`, etc.). Piece values are injected via the constructor,
defaulting to `GameConfig.piece_values` (lazily imported). If an
`event_bus` is supplied, each capture also re-publishes a
`ScoreUpdatedEvent` so other subscribers (future network relay, etc.)
never need to poll `.score` directly."""
from __future__ import annotations

from typing import Dict, Optional

from kungfu_chess.ui.events.event_bus import EventBus
from kungfu_chess.ui.events.events import JumpResolvedEvent, MoveResolvedEvent, ScoreUpdatedEvent


class ScoreObserver:
    def __init__(self, piece_values: Optional[Dict[str, int]] = None,
                 event_bus: Optional[EventBus] = None) -> None:
        if piece_values is None:
            # Lazy import avoids a hard UI -> engine-config coupling.
            from kungfu_chess.config import GameConfig
            piece_values = GameConfig().piece_values
        self._piece_values = piece_values
        self._event_bus = event_bus
        self.score = {"w": 0, "b": 0}

    def on_move_resolved(self, event: MoveResolvedEvent) -> None:
        self._apply_capture(event.captured_piece_kind, event.piece_color)

    def on_jump_resolved(self, event: JumpResolvedEvent) -> None:
        self._apply_capture(event.captured_piece_kind, event.piece_color)

    def _apply_capture(self, captured_kind: Optional[str], capturing_color: str) -> None:
        if captured_kind is None:
            return
        self.score[capturing_color] += self._piece_values.get(captured_kind, 0)
        if self._event_bus is not None:
            self._event_bus.publish(
                ScoreUpdatedEvent(color=capturing_color, score=self.score[capturing_color]))
