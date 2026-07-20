"""Adapter: bridges one game's transport-agnostic per-game `EventBus`
(Phase 1 Domain Events) to the WebSocket transport, so neither the
engine nor the UI-side event types ever need to import a websocket
library. Domain events never carry `game_id`/`room_id`/`user_id` --
this adapter is bound to exactly one `GameSession` and never
re-publishes onto the server-wide `ApplicationMessageBus` (that would
violate the two-namespace boundary; see Event & Message Architecture
in master_work_plan.md)."""
from __future__ import annotations

import asyncio
from dataclasses import asdict

from kungfu_chess.server.protocol import make_envelope
from kungfu_chess.server.session.game_session import GameSession
from kungfu_chess.ui.events.events import (
    GameEndedEvent,
    GameStartedEvent,
    JumpResolvedEvent,
    MoveLoggedEvent,
    MoveResolvedEvent,
    ScoreUpdatedEvent,
    SoundTriggeredEvent,
)

# Wire message `type` for each per-game domain event that reaches connected
# clients. Deliberately not including a "snapshot was sent" entry -- that's
# not modeled as a bus event on either bus (see Snapshot Synchronization
# Strategy); GameSession.broadcast_snapshot sends it directly.
_EVENT_TYPE_NAMES = {
    MoveResolvedEvent: "move_resolved",
    JumpResolvedEvent: "jump_resolved",
    GameStartedEvent: "game_started",
    GameEndedEvent: "game_ended",
    ScoreUpdatedEvent: "score_updated",
    MoveLoggedEvent: "move_logged",
    SoundTriggeredEvent: "sound_triggered",
}


class NetworkEventBusAdapter:
    def __init__(self, session: GameSession) -> None:
        self._session = session
        for event_type, type_name in _EVENT_TYPE_NAMES.items():
            self._session.event_bus.subscribe(event_type, self._make_relay(type_name))

    def _make_relay(self, type_name: str):
        def relay(event) -> None:
            envelope = make_envelope(type_name, asdict(event), self._session.network_config)
            asyncio.ensure_future(self._session.broadcast(envelope))
        return relay
