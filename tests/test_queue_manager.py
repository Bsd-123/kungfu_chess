"""QueueManager.enqueue schedules a timeout via asyncio.ensure_future,
so it -- like GameSession's tick loop -- can only run inside a live
event loop; every test here is async even where no `await` is needed,
mirroring the real caller (a WS message handler coroutine)."""
from __future__ import annotations

import asyncio

import pytest

from kungfu_chess.server.config import MatchmakingConfig
from kungfu_chess.server.matchmaking.queue_manager import QueueManager
from kungfu_chess.server.messaging.application_message_bus import ApplicationMessageBus
from kungfu_chess.server.messaging.transport_events import MatchFoundEvent, MatchmakingTimedOutEvent

pytestmark = pytest.mark.asyncio


class FakeSession:
    def __init__(self, game_id, white_connection, black_connection):
        self.game_id = game_id
        self.white_connection = white_connection
        self.black_connection = black_connection


def make_manager(config=None, sessions=None):
    sessions = sessions if sessions is not None else []

    def create_session(first, second):
        session = FakeSession(f"game-{len(sessions)}", first.connection, second.connection)
        sessions.append((session, first, second))
        return session

    bus = ApplicationMessageBus()
    manager = QueueManager(create_session, bus, config or MatchmakingConfig())
    return manager, bus, sessions


async def test_enqueue_alone_does_not_match():
    manager, _, sessions = make_manager()
    manager.enqueue(connection=object(), user_id=1, rating=1200)
    assert sessions == []


async def test_two_players_within_band_are_matched_immediately():
    manager, bus, sessions = make_manager(MatchmakingConfig(elo_band=100, timeout_s=60))
    found = []
    bus.subscribe(MatchFoundEvent, found.append)

    conn_a, conn_b = object(), object()
    manager.enqueue(connection=conn_a, user_id=1, rating=1200)
    manager.enqueue(connection=conn_b, user_id=2, rating=1250)

    assert len(sessions) == 1
    session, first, second = sessions[0]
    # First-in-queue (conn_a) is White, the new arrival (conn_b) is Black.
    assert session.white_connection is conn_a
    assert session.black_connection is conn_b
    assert len(found) == 1
    assert found[0].white_user_id == 1
    assert found[0].black_user_id == 2


async def test_players_outside_the_band_are_not_matched():
    manager, _, sessions = make_manager(MatchmakingConfig(elo_band=100, timeout_s=60))
    manager.enqueue(connection=object(), user_id=1, rating=1200)
    manager.enqueue(connection=object(), user_id=2, rating=1400)
    assert sessions == []


async def test_a_matched_player_is_not_available_to_match_again():
    manager, _, sessions = make_manager(MatchmakingConfig(elo_band=1000, timeout_s=60))
    manager.enqueue(connection=object(), user_id=1, rating=1200)
    manager.enqueue(connection=object(), user_id=2, rating=1200)
    manager.enqueue(connection=object(), user_id=3, rating=1200)
    # Only the first pair should have matched; the third player is left
    # waiting rather than matched against an already-claimed entry.
    assert len(sessions) == 1


async def test_timeout_fires_after_the_configured_delay():
    manager, bus, sessions = make_manager(MatchmakingConfig(elo_band=100, timeout_s=0.03))
    timed_out = []
    bus.subscribe(MatchmakingTimedOutEvent, timed_out.append)

    manager.enqueue(connection=object(), user_id=1, rating=1200)
    await asyncio.sleep(0.08)

    assert sessions == []
    assert len(timed_out) == 1
    assert timed_out[0].user_id == 1


async def test_a_match_before_timeout_suppresses_the_timeout_event():
    manager, bus, sessions = make_manager(MatchmakingConfig(elo_band=100, timeout_s=0.03))
    timed_out = []
    bus.subscribe(MatchmakingTimedOutEvent, timed_out.append)

    manager.enqueue(connection=object(), user_id=1, rating=1200)
    manager.enqueue(connection=object(), user_id=2, rating=1200)
    await asyncio.sleep(0.08)

    assert len(sessions) == 1
    assert timed_out == []


async def test_cancel_removes_a_waiting_entry():
    manager, _, sessions = make_manager(MatchmakingConfig(elo_band=100, timeout_s=60))
    conn = object()
    manager.enqueue(connection=conn, user_id=1, rating=1200)

    assert manager.cancel(conn) is True
    manager.enqueue(connection=object(), user_id=2, rating=1200)  # would have matched conn
    assert sessions == []


async def test_cancel_on_an_unqueued_connection_returns_false():
    manager, _, _ = make_manager()
    assert manager.cancel(object()) is False


async def test_a_cancelled_entrys_timeout_does_not_fire_afterwards():
    manager, bus, _ = make_manager(MatchmakingConfig(elo_band=100, timeout_s=0.03))
    timed_out = []
    bus.subscribe(MatchmakingTimedOutEvent, timed_out.append)

    conn = object()
    manager.enqueue(connection=conn, user_id=1, rating=1200)
    manager.cancel(conn)
    await asyncio.sleep(0.08)

    assert timed_out == []
