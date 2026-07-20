"""Asyncio WebSocket server entry point (Decision 1: single process,
single-threaded asyncio event loop; Decision 15: trusted same-machine/
LAN clients only, so plain ws:// with no origin/TLS handling).

This phase has no matchmaking or rooms yet (Phase 4/5) -- one
GameSession is created lazily for the first connection, the first
joiner becomes White and the second Black (per the directive), and any
further connection while that session already has two players is
rejected outright (Decision 6's admission-control spirit, refined by
Phase 4's Play-specific queueing later)."""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

import websockets

from kungfu_chess.app import build_game_engine
from kungfu_chess.engine.domain_event_wiring import wire_engine_domain_events
from kungfu_chess.model.position import Position
from kungfu_chess.server.config import ServerConfig
from kungfu_chess.server.connection_registry import ConnectionRegistry
from kungfu_chess.server.network_event_bus_adapter import NetworkEventBusAdapter
from kungfu_chess.server.protocol import Envelope, IdempotencyCache, ProtocolError, make_envelope, new_message_id
from kungfu_chess.server.session.game_session import GameSession
from kungfu_chess.ui.events.event_bus import EventBus
from kungfu_chess.ui.events.events import GameStartedEvent
from kungfu_chess.ui.setup import standard_start_rows

_logger = logging.getLogger(__name__)


class KungFuChessServer:
    """Owns the single active `GameSession` for this minimal server (no
    matchmaking/rooms yet) and the `ConnectionRegistry` mapping
    connections to it. `handle_connection` is the per-socket coroutine
    passed to `websockets.serve`."""

    def __init__(self, config: Optional[ServerConfig] = None):
        self.config = config or ServerConfig()
        self.registry = ConnectionRegistry()
        self._session: Optional[GameSession] = None
        self._idempotency = IdempotencyCache(self.config.network.idempotency_window_ms)

    def _create_session(self) -> GameSession:
        engine = build_game_engine(standard_start_rows, self.config.game)
        session = GameSession(
            game_id=new_message_id(), engine=engine, event_bus=EventBus(),
            network_config=self.config.network, send_to_connection=self._send_envelope)
        wire_engine_domain_events(session.engine, session.event_bus)
        NetworkEventBusAdapter(session)
        return session

    async def _send_envelope(self, connection, envelope: Envelope) -> None:
        # A send can race a connection closing (e.g. a broadcast already
        # in flight when the other end drops) -- that's an ordinary
        # disconnect, not a bug, so it must not surface as an unhandled
        # background-task exception. Real disconnect/reconnect handling
        # is Phase 6's job; this is just I/O-boundary error containment.
        try:
            await connection.send(envelope.to_json())
        except websockets.exceptions.ConnectionClosed:
            pass

    async def _reject(self, websocket, reason: str) -> None:
        envelope = make_envelope("error", {"reason": reason}, self.config.network)
        await websocket.send(envelope.to_json())
        await websocket.close()

    async def handle_connection(self, websocket) -> None:
        if self._session is None:
            self._session = self._create_session()

        if self._session.is_full():
            await self._reject(websocket, "session_full")
            return

        # No `await` between the is_full() check above and add_player()
        # below -- under Decision 1's single-threaded event loop, nothing
        # else can run in between, so add_player() cannot raise here.
        role = self._session.add_player(websocket)
        self.registry.register(websocket, self._session, role)
        await self._session.send_snapshot_to(websocket)

        if self._session.is_full():
            self._session.event_bus.publish(
                GameStartedEvent(timestamp_ms=self._session.engine.clock_ms))
            self._session.start()

        session = self._session
        try:
            async for raw in websocket:
                await self._handle_message(websocket, raw)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            session.remove_player(websocket)
            self.registry.unregister(websocket)
            if not session.connections:
                # No one left to tick/broadcast for -- stop the loop so it
                # doesn't keep running (and erroring on sends) forever.
                # Full both-players-left room teardown is Phase 5's job;
                # this is just resource cleanup within Phase 2's scope.
                session.stop()
                if session is self._session:
                    self._session = None

    async def _handle_message(self, websocket, raw: str) -> None:
        try:
            envelope = Envelope.from_json(raw, self.config.network)
        except ProtocolError as exc:
            _logger.warning("rejecting malformed frame from %r: %s", websocket, exc)
            error = make_envelope("error", {"reason": "malformed_frame"}, self.config.network)
            await websocket.send(error.to_json())
            return

        cached = self._idempotency.get_cached_response(envelope.message_id)
        if cached is not None:
            await websocket.send(cached.to_json())
            return

        lookup = self.registry.lookup(websocket)
        if lookup is None:
            return
        session, _role = lookup

        if envelope.type == "move_request":
            response = self._build_move_response(session, websocket, envelope)
        elif envelope.type == "jump_request":
            response = self._build_jump_response(session, websocket, envelope)
        else:
            response = make_envelope("error", {"reason": "unknown_type"}, self.config.network,
                                      message_id=envelope.message_id)

        self._idempotency.remember(envelope.message_id, response)
        await websocket.send(response.to_json())

    def _build_move_response(self, session: GameSession, websocket, envelope: Envelope) -> Envelope:
        payload = envelope.payload
        source = Position(payload["src_row"], payload["src_col"])
        destination = Position(payload["dst_row"], payload["dst_col"])
        result = session.handle_move_command(websocket, source, destination)
        return make_envelope("move_response", {"accepted": bool(result), "reason": result.reason},
                              self.config.network, message_id=envelope.message_id)

    def _build_jump_response(self, session: GameSession, websocket, envelope: Envelope) -> Envelope:
        payload = envelope.payload
        position = Position(payload["row"], payload["col"])
        result = session.handle_jump_command(websocket, position)
        return make_envelope("jump_response", {"accepted": bool(result), "reason": result.reason},
                              self.config.network, message_id=envelope.message_id)


async def serve(config: Optional[ServerConfig] = None):
    """Returns the running `websockets` server; caller owns its lifetime
    (used directly by tests, wrapped by `main()` for the real process)."""
    config = config or ServerConfig()
    server = KungFuChessServer(config)
    return await websockets.serve(server.handle_connection, config.network.host, config.network.port)


def main() -> None:  # pragma: no cover
    logging.basicConfig(level=logging.INFO)

    async def _run() -> None:
        ws_server = await serve()
        async with ws_server:
            await asyncio.Future()  # run forever

    asyncio.run(_run())


if __name__ == "__main__":  # pragma: no cover
    main()
