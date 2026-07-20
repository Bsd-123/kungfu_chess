"""The canonical Domain Event <-> wire message `type` mapping. Shared
by the server's outbound relay (`server/network_event_bus_adapter.py`)
and the client's inbound translator (`network/client_event_relay.py`)
so the association lives in exactly one place (DRY) -- the two sides
would otherwise be able to drift out of sync silently."""
from __future__ import annotations

from typing import Dict, Type

from kungfu_chess.ui.events.events import (
    GameEndedEvent,
    GameStartedEvent,
    JumpResolvedEvent,
    MoveLoggedEvent,
    MoveResolvedEvent,
    ScoreUpdatedEvent,
    SoundTriggeredEvent,
)

DOMAIN_EVENT_WIRE_NAMES: Dict[type, str] = {
    MoveResolvedEvent: "move_resolved",
    JumpResolvedEvent: "jump_resolved",
    GameStartedEvent: "game_started",
    GameEndedEvent: "game_ended",
    ScoreUpdatedEvent: "score_updated",
    MoveLoggedEvent: "move_logged",
    SoundTriggeredEvent: "sound_triggered",
}

WIRE_NAME_TO_DOMAIN_EVENT: Dict[str, Type] = {
    name: event_type for event_type, name in DOMAIN_EVENT_WIRE_NAMES.items()
}
