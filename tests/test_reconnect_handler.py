from __future__ import annotations

import pytest

from kungfu_chess.app import build_game_engine
from kungfu_chess.config import GameConfig
from kungfu_chess.server.auth.credentials_store import SqliteUserRepository
from kungfu_chess.server.auth.db import open_connection
from kungfu_chess.server.auth.session_manager import SessionManager
from kungfu_chess.server.auth.session_repository import SqliteSessionRepository
from kungfu_chess.server.config import AuthenticationConfig, NetworkConfig
from kungfu_chess.server.messaging.application_message_bus import ApplicationMessageBus
from kungfu_chess.server.messaging.transport_events import ReconnectedEvent
from kungfu_chess.server.reliability.reconnect_handler import ReconnectHandler
from kungfu_chess.server.session.game_session import GameSession, PlayerRole
from kungfu_chess.ui.events.event_bus import EventBus

pytestmark = pytest.mark.asyncio

_AUTH_CONFIG = AuthenticationConfig(pbkdf2_iterations=1000)


def make_session_manager():
    conn = open_connection(":memory:")
    users = SqliteUserRepository(conn, _AUTH_CONFIG)
    sessions = SqliteSessionRepository(conn)
    return SessionManager(users, sessions, _AUTH_CONFIG), users


def make_session(sent=None):
    engine = build_game_engine([['.'] * 8 for _ in range(8)], GameConfig())

    async def send_to_connection(connection, envelope):
        if sent is not None:
            sent.append((connection, envelope))

    return GameSession(game_id="g1", engine=engine, event_bus=EventBus(),
                        network_config=NetworkConfig(), send_to_connection=send_to_connection)


async def test_returns_none_for_an_unresolvable_token():
    manager, _ = make_session_manager()
    handler = ReconnectHandler(manager, list_active_sessions=lambda: [])

    result = await handler.attempt_reconnect("no-such-token", object())

    assert result is None


async def test_returns_none_when_no_session_has_a_pending_disconnect_for_that_user():
    manager, users = make_session_manager()
    token = manager.login("alice", "hunter2")
    alice = users.get_by_username("alice")
    session = make_session()
    session.add_player(object(), user_id=alice.id)  # seated, but never disconnected

    handler = ReconnectHandler(manager, list_active_sessions=lambda: [session])
    result = await handler.attempt_reconnect(token, object())

    assert result is None


async def test_reconnects_to_the_pending_disconnect_slot():
    manager, users = make_session_manager()
    token = manager.login("alice", "hunter2")
    alice = users.get_by_username("alice")
    session = make_session()
    old_connection = object()
    session.add_player(old_connection, user_id=alice.id)
    session.remove_player(old_connection)
    session.mark_disconnected(PlayerRole.WHITE, grace_period_ms=20_000, on_expire=lambda: None)

    handler = ReconnectHandler(manager, list_active_sessions=lambda: [session])
    new_connection = object()
    result = await handler.attempt_reconnect(token, new_connection)

    assert result == (session, PlayerRole.WHITE)
    assert session.white_connection is new_connection
    assert session.has_pending_disconnect(PlayerRole.WHITE) is False


async def test_reconnect_sends_a_snapshot_and_broadcasts_reconnected():
    sent = []
    manager, users = make_session_manager()
    token = manager.login("alice", "hunter2")
    alice = users.get_by_username("alice")
    session = make_session(sent=sent)
    old_connection = object()
    session.add_player(old_connection, user_id=alice.id)
    session.remove_player(old_connection)
    session.mark_disconnected(PlayerRole.WHITE, grace_period_ms=20_000, on_expire=lambda: None)

    handler = ReconnectHandler(manager, list_active_sessions=lambda: [session])
    new_connection = object()
    await handler.attempt_reconnect(token, new_connection)

    snapshot_messages = [(c, e) for c, e in sent if e.type == "snapshot" and c is new_connection]
    reconnected_messages = [e for c, e in sent if e.type == "reconnected"]
    assert len(snapshot_messages) == 1
    assert len(reconnected_messages) == 1
    assert reconnected_messages[0].payload == {"role": "white"}


async def test_publishes_reconnected_event_when_a_message_bus_is_given():
    manager, users = make_session_manager()
    token = manager.login("alice", "hunter2")
    alice = users.get_by_username("alice")
    session = make_session()
    old_connection = object()
    session.add_player(old_connection, user_id=alice.id)
    session.remove_player(old_connection)
    session.mark_disconnected(PlayerRole.WHITE, grace_period_ms=20_000, on_expire=lambda: None)

    bus = ApplicationMessageBus()
    received = []
    bus.subscribe(ReconnectedEvent, received.append)
    handler = ReconnectHandler(manager, list_active_sessions=lambda: [session], message_bus=bus)

    await handler.attempt_reconnect(token, object())

    assert len(received) == 1
    assert received[0].user_id == alice.id
    assert received[0].game_id == "g1"
