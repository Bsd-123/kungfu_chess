import json

import pytest

from kungfu_chess.server.config import NetworkConfig
from kungfu_chess.server.protocol import (
    Envelope,
    IdempotencyCache,
    ProtocolError,
    make_envelope,
    new_message_id,
)


def test_new_message_id_is_unique():
    assert new_message_id() != new_message_id()


def test_make_envelope_round_trips_through_json():
    config = NetworkConfig()
    envelope = make_envelope("move_request", {"src": "e2", "dst": "e4"}, config)
    raw = envelope.to_json()
    parsed = Envelope.from_json(raw, config)
    assert parsed == envelope


def test_from_json_rejects_malformed_json():
    config = NetworkConfig()
    with pytest.raises(ProtocolError):
        Envelope.from_json("{not valid json", config)


def test_from_json_rejects_non_object_json():
    config = NetworkConfig()
    with pytest.raises(ProtocolError):
        Envelope.from_json(json.dumps([1, 2, 3]), config)


def test_from_json_rejects_missing_fields():
    config = NetworkConfig()
    raw = json.dumps({"type": "move_request", "payload": {}})
    with pytest.raises(ProtocolError):
        Envelope.from_json(raw, config)


def test_from_json_rejects_non_object_payload():
    config = NetworkConfig()
    raw = json.dumps({
        "protocol_version": 1, "type": "move_request",
        "message_id": "x", "timestamp_ms": 0, "payload": "not an object",
    })
    with pytest.raises(ProtocolError):
        Envelope.from_json(raw, config)


def test_from_json_rejects_wrong_protocol_version():
    config = NetworkConfig(protocol_version=1)
    raw = json.dumps({
        "protocol_version": 2, "type": "move_request",
        "message_id": "x", "timestamp_ms": 0, "payload": {},
    })
    with pytest.raises(ProtocolError):
        Envelope.from_json(raw, config)


def test_from_json_rejects_oversized_frame():
    config = NetworkConfig(max_message_bytes=10)
    raw = json.dumps({
        "protocol_version": 1, "type": "move_request",
        "message_id": "x", "timestamp_ms": 0, "payload": {},
    })
    with pytest.raises(ProtocolError):
        Envelope.from_json(raw, config)


def test_make_envelope_generates_message_id_when_omitted():
    config = NetworkConfig()
    envelope = make_envelope("snapshot", {}, config)
    assert envelope.message_id


def test_make_envelope_uses_given_message_id():
    config = NetworkConfig()
    envelope = make_envelope("snapshot", {}, config, message_id="fixed-id")
    assert envelope.message_id == "fixed-id"


def test_idempotency_cache_returns_none_for_unknown_message_id():
    cache = IdempotencyCache(window_ms=1000, clock_ms=lambda: 0)
    assert cache.get_cached_response("unknown") is None


def test_idempotency_cache_replays_within_window():
    now = [0]
    cache = IdempotencyCache(window_ms=1000, clock_ms=lambda: now[0])
    config = NetworkConfig()
    response = make_envelope("move_resolved", {}, config, message_id="req-1")
    cache.remember("req-1", response)
    now[0] = 500
    assert cache.get_cached_response("req-1") == response


def test_idempotency_cache_expires_after_window():
    now = [0]
    cache = IdempotencyCache(window_ms=1000, clock_ms=lambda: now[0])
    config = NetworkConfig()
    response = make_envelope("move_resolved", {}, config, message_id="req-1")
    cache.remember("req-1", response)
    now[0] = 1500
    assert cache.get_cached_response("req-1") is None
