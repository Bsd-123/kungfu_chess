"""Drains a `NetworkClient`'s incoming envelopes once per rendered
frame and dispatches each: a "snapshot" envelope updates the
`RemoteGameProxy` directly (bypassing the bus -- per Event & Message
Architecture, "a snapshot was sent" is deliberately not modeled as a
bus event on either bus); every other known domain-event type is
republished onto the local `EventBus` via `client_event_relay`, so
every Phase-1 subscriber (renderer, sound, score, move log, board
mirror) works unmodified. Unrecognized types (move_response/
jump_response/error) are acks/diagnostics, not domain events -- silently
skipped here."""
from __future__ import annotations

from kungfu_chess.network.client_event_relay import republish_envelope
from kungfu_chess.network.network_client import NetworkClient
from kungfu_chess.network.remote_game_proxy import RemoteGameProxy
from kungfu_chess.server.snapshot_codec import snapshot_from_dict
from kungfu_chess.ui.events.event_bus import EventBus


def drain_network_client(network_client: NetworkClient, proxy: RemoteGameProxy,
                          event_bus: EventBus) -> None:
    for envelope in network_client.poll_incoming():
        if envelope.type == "snapshot":
            proxy.apply_snapshot(snapshot_from_dict(envelope.payload))
            continue
        republish_envelope(envelope, event_bus)
