"""Wire protocol: the uniform Message Envelope used by every message
crossing the WebSocket in either direction -- commands, relayed domain
events, transport events, snapshots. This is the only module that
knows about wire format; serialization stays out of both the engine
and the UI (SRP)."""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional

from kungfu_chess.server.config import NetworkConfig

_REQUIRED_FIELDS = frozenset({"protocol_version", "type", "message_id", "timestamp_ms", "payload"})


class ProtocolError(Exception):
    """Raised for a malformed/oversized/unsupported-version frame; callers
    must reject and log without crashing the connection handler for other
    clients."""


@dataclass(frozen=True)
class Envelope:
    type: str
    payload: Dict[str, Any]
    protocol_version: int
    message_id: str
    timestamp_ms: int

    def to_json(self) -> str:
        return json.dumps({
            "protocol_version": self.protocol_version,
            "type": self.type,
            "message_id": self.message_id,
            "timestamp_ms": self.timestamp_ms,
            "payload": self.payload,
        })

    @staticmethod
    def from_json(raw: str, config: NetworkConfig) -> "Envelope":
        if len(raw.encode("utf-8")) > config.max_message_bytes:
            raise ProtocolError(
                f"frame of {len(raw.encode('utf-8'))} bytes exceeds "
                f"max_message_bytes={config.max_message_bytes}")

        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError) as exc:
            raise ProtocolError(f"malformed JSON: {exc}") from exc

        if not isinstance(data, dict):
            raise ProtocolError("envelope must be a JSON object")

        missing = _REQUIRED_FIELDS - data.keys()
        if missing:
            raise ProtocolError(f"envelope missing fields: {sorted(missing)}")

        if not isinstance(data["payload"], dict):
            raise ProtocolError("envelope 'payload' must be a JSON object")

        if data["protocol_version"] != config.protocol_version:
            raise ProtocolError(
                f"unsupported protocol_version {data['protocol_version']!r}, "
                f"expected {config.protocol_version}")

        return Envelope(
            type=data["type"],
            payload=data["payload"],
            protocol_version=data["protocol_version"],
            message_id=data["message_id"],
            timestamp_ms=data["timestamp_ms"],
        )


def new_message_id() -> str:
    return uuid.uuid4().hex


def make_envelope(type_: str, payload: Dict[str, Any], config: NetworkConfig,
                   message_id: Optional[str] = None,
                   timestamp_ms: Optional[int] = None) -> Envelope:
    return Envelope(
        type=type_,
        payload=payload,
        protocol_version=config.protocol_version,
        message_id=message_id or new_message_id(),
        timestamp_ms=timestamp_ms if timestamp_ms is not None else int(time.time() * 1000),
    )


class IdempotencyCache:
    """Detects a duplicate `message_id` arriving within `window_ms` (e.g. a
    client retry after a slow/dropped ack on a flaky connection) so the
    caller can replay the cached response instead of reprocessing the
    command. `clock_ms` is injectable so tests don't depend on wall time."""

    def __init__(self, window_ms: int, clock_ms=lambda: int(time.time() * 1000)):
        self._window_ms = window_ms
        self._clock_ms = clock_ms
        self._entries: Dict[str, tuple] = {}

    def get_cached_response(self, message_id: str) -> Optional[Envelope]:
        self._evict_expired()
        entry = self._entries.get(message_id)
        return entry[1] if entry is not None else None

    def remember(self, message_id: str, response: Envelope) -> None:
        self._entries[message_id] = (self._clock_ms(), response)

    def _evict_expired(self) -> None:
        now = self._clock_ms()
        expired = [mid for mid, (recorded_at, _) in self._entries.items()
                   if now - recorded_at > self._window_ms]
        for mid in expired:
            del self._entries[mid]
