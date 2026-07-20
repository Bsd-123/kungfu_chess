"""Client-side counterpart to `server/network_event_bus_adapter.py`:
decodes incoming envelopes for known domain-event wire types and
republishes them as the concrete UI-side event dataclasses onto the
local per-game `EventBus`, so every Phase-1 subscriber (renderer,
sound, score, move log) works unmodified whether the engine is local
or remote -- this is the payoff of doing Phase 1 first."""
from __future__ import annotations

from kungfu_chess.server.protocol import Envelope
from kungfu_chess.ui.events.event_bus import EventBus
from kungfu_chess.ui.events.wire_names import WIRE_NAME_TO_DOMAIN_EVENT


def republish_envelope(envelope: Envelope, event_bus: EventBus) -> bool:
    """Returns True if `envelope` was a known domain-event type and was
    republished; False otherwise (e.g. "snapshot"/"move_response",
    which the caller handles separately)."""
    event_type = WIRE_NAME_TO_DOMAIN_EVENT.get(envelope.type)
    if event_type is None:
        return False
    event_bus.publish(event_type(**envelope.payload))
    return True
