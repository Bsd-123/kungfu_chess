"""Translates domain events into `SoundTriggeredEvent`s on the same
bus. Owns no audio playback -- picking a sound name for "a move just
resolved" is this module's whole job (SRP); actually playing audio is
a rendering-layer concern outside this phase."""
from __future__ import annotations

from kungfu_chess.ui.events.event_bus import EventBus
from kungfu_chess.ui.events.events import (
    GameEndedEvent,
    GameStartedEvent,
    JumpResolvedEvent,
    MoveResolvedEvent,
    SoundTriggeredEvent,
)


class SoundObserver:
    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    def on_move_resolved(self, event: MoveResolvedEvent) -> None:
        name = "capture" if event.captured_piece_kind else "move"
        self._event_bus.publish(SoundTriggeredEvent(sound_name=name))

    def on_jump_resolved(self, event: JumpResolvedEvent) -> None:
        name = "capture" if event.captured_piece_kind else "jump"
        self._event_bus.publish(SoundTriggeredEvent(sound_name=name))

    def on_game_started(self, event: GameStartedEvent) -> None:
        self._event_bus.publish(SoundTriggeredEvent(sound_name="game_start"))

    def on_game_ended(self, event: GameEndedEvent) -> None:
        self._event_bus.publish(SoundTriggeredEvent(sound_name="game_end"))
