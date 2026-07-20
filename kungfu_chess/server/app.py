"""Asyncio WebSocket server entry point (Decision 1: single process,
single-threaded asyncio event loop; Decision 15: trusted same-machine/
LAN clients only, so plain ws:// with no origin/TLS handling).

Integration pass: every connection now goes through an authenticated
handshake (`login` with a fresh username/password, or `auth` with a
previously issued session token) before it can do anything else. Once
authenticated, a connection is "in the lobby" -- idle, not seated in
any `GameSession` -- until it sends `play_request` (Phase 4 matchmaking)
or `create_room`/`join_room` (Phase 5 rooms). `DisconnectMonitor`/
`ReconnectHandler` (Phase 6) are threaded into the connection lifecycle
so a dropped socket starts a 20-second grace period instead of
immediately vacating the seat, and a reconnecting token rebinds a new
socket to the same live `GameSession`.

Blocking SQLite calls (`SessionManager.login`/`resolve`, rating writes)
are offloaded via `asyncio.to_thread` so a slow disk write can't stall
other games' ticks, per master_work_plan.md's Phase 2 risk note."""
from __future__ import annotations

import asyncio
import logging
from typing import Dict, List, Optional, Tuple

import websockets

from kungfu_chess.app import build_game_engine
from kungfu_chess.engine.domain_event_wiring import wire_engine_domain_events
from kungfu_chess.model.position import Position
from kungfu_chess.server.auth.credentials_store import SqliteUserRepository
from kungfu_chess.server.auth.db import open_connection
from kungfu_chess.server.auth.session_manager import AuthenticationError, SessionManager
from kungfu_chess.server.auth.session_repository import SqliteSessionRepository
from kungfu_chess.server.config import ServerConfig
from kungfu_chess.server.connection_registry import ConnectionRegistry
from kungfu_chess.server.logging.structured_logger import get_logger, log_event
from kungfu_chess.server.matchmaking.queue_manager import QueueEntry, QueueManager
from kungfu_chess.server.messaging.application_message_bus import ApplicationMessageBus
from kungfu_chess.server.messaging.transport_events import MatchmakingTimedOutEvent
from kungfu_chess.server.network_event_bus_adapter import NetworkEventBusAdapter
from kungfu_chess.server.protocol import Envelope, IdempotencyCache, ProtocolError, make_envelope, new_message_id
from kungfu_chess.server.rating.rating_update_service import RatingUpdateService
from kungfu_chess.server.reliability.disconnect_monitor import DisconnectMonitor
from kungfu_chess.server.reliability.reconnect_handler import ReconnectHandler
from kungfu_chess.server.rooms.room_manager import RoomManager, RoomNotFoundError
from kungfu_chess.server.session.game_session import (
    GameSession, PlayerRole, SpectatorCapError,
)
from kungfu_chess.ui.events.event_bus import EventBus
from kungfu_chess.ui.events.events import GameEndedEvent, GameStartedEvent
from kungfu_chess.ui.setup import standard_start_rows


class KungFuChessServer:
    """Composition root for one running server process: owns the auth
    database/repositories, the `ApplicationMessageBus`, the matchmaking
    queue, the room manager, and the reliability layer, and wires a
    fresh `GameSession` for every match or room the same way (
    `_new_game_session`) so Play and Room games are indistinguishable to
    everything downstream (rating, domain-event relay, reconnection)."""

    def __init__(self, config: Optional[ServerConfig] = None):
        self.config = config or ServerConfig()
        self.registry = ConnectionRegistry()
        self._idempotency = IdempotencyCache(self.config.network.idempotency_window_ms)
        self._logger = get_logger(f"kungfu_chess.server.{id(self)}", self.config.logging)

        auth_db = open_connection(self.config.authentication.db_path)
        self._users = SqliteUserRepository(auth_db, self.config.authentication, self.config.rating)
        self._session_repository = SqliteSessionRepository(auth_db)
        self._session_manager = SessionManager(
            self._users, self._session_repository, self.config.authentication)

        self._message_bus = ApplicationMessageBus()
        self._rating_service = RatingUpdateService(self._users, self.config.rating, self._message_bus)

        self._queue_manager = QueueManager(
            self._create_matched_session, self._message_bus, self.config.matchmaking)
        self._room_manager = RoomManager(self._create_room_session, self.config.room)

        self._disconnect_monitor = DisconnectMonitor(
            self.config.network, self.config.reliability.disconnect_grace_period_ms, self._message_bus)
        self._reconnect_handler = ReconnectHandler(
            self._session_manager, self._list_active_sessions, self._message_bus)

        # Pre-session identity: who is authenticated on which socket,
        # before/without being seated in a GameSession -- needed to push
        # a match_found/matchmaking_timed_out notification to a
        # connection ConnectionRegistry doesn't know about yet.
        self._connections_by_user_id: Dict[int, object] = {}

        # Play has no room-code registry like RoomManager._rooms; this
        # is the equivalent bookkeeping so ReconnectHandler can scan
        # Play games too, and so a completed game's GameSession can be
        # dropped once it's over (see _on_game_ended).
        self._play_sessions: List[GameSession] = []

        self._message_bus.subscribe(MatchmakingTimedOutEvent, self._on_matchmaking_timed_out)

    # -- session construction: the one place either flow builds a
    # GameSession, so Play and Room games are wired identically -------
    def _new_game_session(self, game_id: str) -> GameSession:
        engine = build_game_engine(standard_start_rows, self.config.game)
        session = GameSession(
            game_id=game_id, engine=engine, event_bus=EventBus(),
            network_config=self.config.network, send_to_connection=self._send_envelope,
            spectator_cap=self.config.room.spectator_cap)
        wire_engine_domain_events(session.engine, session.event_bus)
        NetworkEventBusAdapter(session)
        self._rating_service.wire(session)
        session.event_bus.subscribe(GameEndedEvent, lambda event: self._on_game_ended(session, event))
        return session

    def _on_game_ended(self, session: GameSession, event: GameEndedEvent) -> None:
        # Stop ticking the instant the game is over (win or forfeit) --
        # also cancels any still-pending disconnect timer, so a
        # just-forfeited opponent's own countdown can't fire a second,
        # harmless-but-pointless GameEndedEvent later.
        session.stop()
        if session in self._play_sessions:
            self._play_sessions.remove(session)
        log_event(self._logger, "game ended", game_id=session.game_id, winner=event.winner)

    def _create_matched_session(self, first: QueueEntry, second: QueueEntry) -> GameSession:
        """QueueManager's injected session factory (Decision 6: exactly
        2 connections -- there is no code path for a third connection to
        reach a Play session afterward, since it's never registered
        under any joinable id)."""
        session = self._new_game_session(new_message_id())
        session.add_player(first.connection, first.user_id)
        session.add_player(second.connection, second.user_id)
        self._play_sessions.append(session)
        self.registry.register(first.connection, session, PlayerRole.WHITE)
        self.registry.register(second.connection, session, PlayerRole.BLACK)
        log_event(self._logger, "match found", game_id=session.game_id,
                  white_user_id=first.user_id, black_user_id=second.user_id)
        asyncio.ensure_future(self._start_matched_game(session))
        return session

    async def _start_matched_game(self, session: GameSession) -> None:
        """Runs as one coroutine so wire delivery order is guaranteed
        (match_found, then the initial snapshot, then game_started) --
        GameStartedEvent's own relay is scheduled as a *separate* task by
        NetworkEventBusAdapter, so publishing it any earlier here would
        race the snapshot/match_found sends below and could arrive
        first."""
        for connection in session.connections:
            role = session.role_for(connection)
            envelope = make_envelope(
                "match_found", {"role": role.value, "game_id": session.game_id}, self.config.network)
            await self._send_envelope(connection, envelope)
        await session.broadcast_snapshot()
        session.start()
        session.event_bus.publish(GameStartedEvent(timestamp_ms=session.engine.clock_ms))

    def _create_room_session(self, room_id: str) -> GameSession:
        """RoomManager's injected session factory -- RoomManager itself
        seats the connection(s); this only builds the session."""
        return self._new_game_session(room_id)

    def _list_active_sessions(self) -> List[GameSession]:
        return self._play_sessions + self._room_manager.list_sessions()

    def _rating_for(self, user_id: int) -> int:
        user = self._users.get_by_id(user_id)
        return user.rating if user is not None else self.config.rating.base_rating

    def _on_matchmaking_timed_out(self, event: MatchmakingTimedOutEvent) -> None:
        connection = self._connections_by_user_id.get(event.user_id)
        log_event(self._logger, "matchmaking timed out", user_id=event.user_id)
        if connection is not None:
            envelope = make_envelope("matchmaking_timed_out", {}, self.config.network)
            asyncio.ensure_future(self._send_envelope(connection, envelope))

    # -- transport-level I/O ----------------------------------------------
    async def _send_envelope(self, connection, envelope: Envelope) -> None:
        # A send can race a connection closing (e.g. a broadcast already
        # in flight when the other end drops) -- that's an ordinary
        # disconnect, not a bug, so it must not surface as an unhandled
        # background-task exception.
        try:
            await connection.send(envelope.to_json())
        except websockets.exceptions.ConnectionClosed:
            pass

    async def _reject(self, websocket, reason: str) -> None:
        envelope = make_envelope("error", {"reason": reason}, self.config.network)
        await self._send_envelope(websocket, envelope)
        await websocket.close()

    # -- authenticated handshake -------------------------------------------
    async def _authenticate(self, websocket) -> Optional[Tuple[int, bool]]:
        """Reads the connection's mandatory first message and returns
        `(user_id, reconnected)` on success, or None if the connection
        was rejected/closed and the caller should stop -- `login`
        exchanges a fresh username/password for a session token;
        `auth` presents a previously issued token, which may resolve to
        a pending reconnection."""
        try:
            raw = await websocket.recv()
        except websockets.exceptions.ConnectionClosed:
            return None

        try:
            envelope = Envelope.from_json(raw, self.config.network)
        except ProtocolError as exc:
            log_event(self._logger, "rejected malformed first frame", level=logging.WARNING,
                      reason=str(exc))
            await self._reject(websocket, "malformed_frame")
            return None

        if envelope.type == "login":
            return await self._handle_login(websocket, envelope)
        if envelope.type == "auth":
            return await self._handle_auth(websocket, envelope)

        log_event(self._logger, "first message was not login/auth", level=logging.WARNING,
                  message_type=envelope.type)
        await self._reject(websocket, "auth_required")
        return None

    async def _handle_login(self, websocket, envelope: Envelope) -> Optional[Tuple[int, bool]]:
        username = envelope.payload.get("username")
        password = envelope.payload.get("password")
        if not username or not password:
            await self._reject(websocket, "missing_credentials")
            return None

        try:
            token = await asyncio.to_thread(self._session_manager.login, username, password)
        except AuthenticationError as exc:
            log_event(self._logger, "login rejected", username=username, reason=str(exc))
            await self._reject(websocket, "invalid_credentials")
            return None

        user_id = await asyncio.to_thread(self._session_manager.resolve, token)
        await self._send_envelope(websocket, make_envelope(
            "auth_response",
            {"accepted": True, "reconnected": False, "session_token": token},
            self.config.network))
        log_event(self._logger, "login accepted", username=username, user_id=user_id)
        return user_id, False

    async def _handle_auth(self, websocket, envelope: Envelope) -> Optional[Tuple[int, bool]]:
        token = envelope.payload.get("session_token")
        if not token:
            await self._reject(websocket, "missing_session_token")
            return None

        reconnect_result = await self._reconnect_handler.attempt_reconnect(token, websocket)
        if reconnect_result is not None:
            session, role = reconnect_result
            self.registry.register(websocket, session, role)
            user_id = session.white_user_id if role is PlayerRole.WHITE else session.black_user_id
            await self._send_envelope(websocket, make_envelope(
                "auth_response",
                {"accepted": True, "reconnected": True, "role": role.value, "game_id": session.game_id},
                self.config.network))
            log_event(self._logger, "connection reconnected", user_id=user_id,
                      game_id=session.game_id, role=role.value)
            return user_id, True

        user_id = await asyncio.to_thread(self._session_manager.resolve, token)
        if user_id is None:
            log_event(self._logger, "auth rejected: invalid or expired token", session_token=token)
            await self._reject(websocket, "invalid_session_token")
            return None

        await self._send_envelope(websocket, make_envelope(
            "auth_response", {"accepted": True, "reconnected": False}, self.config.network))
        log_event(self._logger, "connection authenticated", user_id=user_id)
        return user_id, False

    # -- connection lifecycle ----------------------------------------------
    async def handle_connection(self, websocket) -> None:
        auth = await self._authenticate(websocket)
        if auth is None:
            return
        user_id, _reconnected = auth
        self._connections_by_user_id[user_id] = websocket

        try:
            async for raw in websocket:
                await self._handle_message(websocket, raw, user_id)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self._connections_by_user_id.pop(user_id, None)
            self._queue_manager.cancel(websocket)  # no-op if not queued

            lookup = self.registry.lookup(websocket)
            if lookup is not None:
                session, role = lookup
                self.registry.unregister(websocket)

                if role is None:
                    # A spectator leaving is immediate, no grace period
                    # (Phase 5's design) -- always a Room, since Play
                    # never has spectators.
                    await self._room_manager.leave_room(session.game_id, websocket)
                else:
                    self._disconnect_monitor.handle_disconnect(session, websocket)
                    log_event(self._logger, "player disconnected", user_id=user_id,
                              game_id=session.game_id, role=role.value)
                    # Decision 9: whether this was a voluntary leave or
                    # an unexpected drop, if it's a Room and both player
                    # slots are now empty, tear the room down immediately
                    # -- RoomManager.leave_room's own "both empty?" check
                    # is a no-op if the opponent is still seated, so this
                    # is safe to call unconditionally for any Room
                    # session a player just departed.
                    if self._room_manager.get_room(session.game_id) is session:
                        await self._room_manager.leave_room(session.game_id, websocket)

    # -- post-auth message dispatch ----------------------------------------
    async def _handle_message(self, websocket, raw: str, user_id: int) -> None:
        try:
            envelope = Envelope.from_json(raw, self.config.network)
        except ProtocolError as exc:
            log_event(self._logger, "rejecting malformed frame", level=logging.WARNING, reason=str(exc))
            await self._send_envelope(websocket, make_envelope(
                "error", {"reason": "malformed_frame"}, self.config.network))
            return

        cached = self._idempotency.get_cached_response(envelope.message_id)
        if cached is not None:
            await self._send_envelope(websocket, cached)
            return

        lookup = self.registry.lookup(websocket)
        if lookup is None:
            response = await self._handle_lobby_message(websocket, envelope, user_id)
        else:
            session, _role = lookup
            response = self._handle_seated_message(session, websocket, envelope)

        self._idempotency.remember(envelope.message_id, response)
        await self._send_envelope(websocket, response)

    # -- lobby: authenticated, not yet seated in any GameSession -----------
    async def _handle_lobby_message(self, websocket, envelope: Envelope, user_id: int) -> Envelope:
        if envelope.type == "play_request":
            return await self._handle_play_request(websocket, envelope, user_id)
        if envelope.type == "cancel_matchmaking":
            cancelled = self._queue_manager.cancel(websocket)
            return make_envelope("matchmaking_cancelled", {"cancelled": cancelled},
                                  self.config.network, message_id=envelope.message_id)
        if envelope.type == "create_room":
            return await self._handle_create_room(websocket, envelope, user_id)
        if envelope.type == "join_room":
            return await self._handle_join_room(websocket, envelope, user_id)

        return make_envelope("error", {"reason": "unknown_type"}, self.config.network,
                              message_id=envelope.message_id)

    async def _handle_play_request(self, websocket, envelope: Envelope, user_id: int) -> Envelope:
        if self._queue_manager.is_queued(websocket):
            return make_envelope("error", {"reason": "already_queued"}, self.config.network,
                                  message_id=envelope.message_id)
        rating = await asyncio.to_thread(self._rating_for, user_id)
        self._queue_manager.enqueue(websocket, user_id, rating)
        log_event(self._logger, "play request enqueued", user_id=user_id, rating=rating)
        return make_envelope("play_request_accepted", {}, self.config.network,
                              message_id=envelope.message_id)

    async def _handle_create_room(self, websocket, envelope: Envelope, user_id: int) -> Envelope:
        room_id = self._room_manager.create_room(websocket, user_id)
        session = self._room_manager.get_room(room_id)
        self.registry.register(websocket, session, PlayerRole.WHITE)
        # Scheduled, not awaited inline -- so the room_created ack below
        # (sent by the caller right after this returns) reaches the
        # creator before the snapshot, a predictable command-ack-first
        # ordering matched by _start_matched_game's Play equivalent.
        asyncio.ensure_future(session.send_snapshot_to(websocket))
        log_event(self._logger, "room created", user_id=user_id, game_id=room_id)
        return make_envelope("room_created", {"room_id": room_id}, self.config.network,
                              message_id=envelope.message_id)

    async def _handle_join_room(self, websocket, envelope: Envelope, user_id: int) -> Envelope:
        room_id = envelope.payload.get("room_id")
        try:
            role = self._room_manager.join_room(room_id, websocket, user_id)
        except RoomNotFoundError:
            return make_envelope("room_join_rejected", {"reason": "room_not_found"},
                                  self.config.network, message_id=envelope.message_id)
        except SpectatorCapError:
            return make_envelope("room_join_rejected", {"reason": "room_full"},
                                  self.config.network, message_id=envelope.message_id)

        session = self._room_manager.get_room(room_id)
        self.registry.register(websocket, session, role)
        # Same ordering rationale as _handle_create_room: room_joined
        # first, then the snapshot; game_started (if this seats Black)
        # is scheduled after both via its own NetworkEventBusAdapter
        # relay task, so it naturally lands last.
        asyncio.ensure_future(session.send_snapshot_to(websocket))

        if role is PlayerRole.BLACK and session.is_full():
            session.start()
            session.event_bus.publish(GameStartedEvent(timestamp_ms=session.engine.clock_ms))

        log_event(self._logger, "room joined", user_id=user_id, game_id=room_id,
                  role=(role.value if role is not None else "spectator"))
        return make_envelope("room_joined", {"role": role.value if role is not None else None},
                              self.config.network, message_id=envelope.message_id)

    # -- seated: registered in a GameSession as a player --------------------
    def _handle_seated_message(self, session: GameSession, websocket, envelope: Envelope) -> Envelope:
        if envelope.type == "move_request":
            return self._build_move_response(session, websocket, envelope)
        if envelope.type == "jump_request":
            return self._build_jump_response(session, websocket, envelope)
        return make_envelope("error", {"reason": "unknown_type"}, self.config.network,
                              message_id=envelope.message_id)

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
