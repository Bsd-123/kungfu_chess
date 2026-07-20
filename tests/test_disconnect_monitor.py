from __future__ import annotations

import asyncio

import pytest

from kungfu_chess.app import build_game_engine
from kungfu_chess.config import GameConfig
from kungfu_chess.server.config import NetworkConfig
from kungfu_chess.server.messaging.application_message_bus import ApplicationMessageBus
from kungfu_chess.server.messaging.transport_events import PlayerDisconnectedEvent, PlayerForfeitedEvent
from kungfu_chess.server.reliability.disconnect_monitor import DisconnectMonitor
from kungfu_chess.server.session.game_session import GameSession, PlayerRole
from kungfu_chess.ui.events.event_bus import EventBus
from kungfu_chess.ui.events.events import GameEndedEvent

pytestmark = pytest.mark.asyncio


def make_session(sent=None):
    engine = build_game_engine([['.'] * 8 for _ in range(8)], GameConfig())

    async def send_to_connection(connection, envelope):
        if sent is not None:
            sent.append((connection, envelope))

    return GameSession(game_id="g1", engine=engine, event_bus=EventBus(),
                        network_config=NetworkConfig(), send_to_connection=send_to_connection)


async def test_returns_none_and_has_no_effect_for_a_spectator():
    session = make_session()
    spectator = object()
    session.add_spectator(spectator)
    monitor = DisconnectMonitor()

    role = monitor.handle_disconnect(session, spectator)

    assert role is None
    assert session.is_spectator(spectator) is True  # untouched


async def test_frees_the_seat_and_starts_a_grace_timer():
    session = make_session()
    white = object()
    session.add_player(white, user_id=1)
    monitor = DisconnectMonitor(grace_period_ms=5_000)

    role = monitor.handle_disconnect(session, white)

    assert role is PlayerRole.WHITE
    assert session.white_connection is None
    assert session.has_pending_disconnect(PlayerRole.WHITE) is True


async def test_broadcasts_a_single_player_disconnected_message_with_grace_period():
    sent = []
    session = make_session(sent=sent)
    white, black = object(), object()
    session.add_player(white, user_id=1)
    session.add_player(black, user_id=2)
    monitor = DisconnectMonitor(grace_period_ms=20_000)

    monitor.handle_disconnect(session, white)
    await asyncio.sleep(0.01)  # let the ensure_future'd broadcast run

    disconnect_messages = [envelope for conn, envelope in sent if envelope.type == "player_disconnected"]
    assert len(disconnect_messages) == 1
    assert disconnect_messages[0].payload == {"role": "white", "grace_period_ms": 20_000}


async def test_forfeit_fires_game_ended_event_after_the_grace_period_elapses():
    session = make_session()
    white, black = object(), object()
    session.add_player(white, user_id=1)
    session.add_player(black, user_id=2)
    monitor = DisconnectMonitor(grace_period_ms=30)
    ended = []
    session.event_bus.subscribe(GameEndedEvent, ended.append)

    monitor.handle_disconnect(session, white)
    await asyncio.sleep(0.08)

    assert len(ended) == 1
    assert ended[0].winner == 'b'  # White disconnected -> Black wins


async def test_forfeit_winner_is_white_when_black_disconnects():
    session = make_session()
    white, black = object(), object()
    session.add_player(white, user_id=1)
    session.add_player(black, user_id=2)
    monitor = DisconnectMonitor(grace_period_ms=30)
    ended = []
    session.event_bus.subscribe(GameEndedEvent, ended.append)

    monitor.handle_disconnect(session, black)
    await asyncio.sleep(0.08)

    assert ended[0].winner == 'w'


async def test_reconnecting_before_the_grace_period_elapses_prevents_the_forfeit():
    session = make_session()
    white, black = object(), object()
    session.add_player(white, user_id=1)
    session.add_player(black, user_id=2)
    monitor = DisconnectMonitor(grace_period_ms=50)
    ended = []
    session.event_bus.subscribe(GameEndedEvent, ended.append)

    monitor.handle_disconnect(session, white)
    session.cancel_disconnect(PlayerRole.WHITE)  # simulates ReconnectHandler winning the race
    await asyncio.sleep(0.09)

    assert ended == []


async def test_publishes_transport_events_when_a_message_bus_is_given():
    session = make_session()
    white, black = object(), object()
    session.add_player(white, user_id=1)
    session.add_player(black, user_id=2)
    bus = ApplicationMessageBus()
    disconnected, forfeited = [], []
    bus.subscribe(PlayerDisconnectedEvent, disconnected.append)
    bus.subscribe(PlayerForfeitedEvent, forfeited.append)
    monitor = DisconnectMonitor(grace_period_ms=30, message_bus=bus)

    monitor.handle_disconnect(session, white)
    assert len(disconnected) == 1
    assert disconnected[0].user_id == 1
    assert disconnected[0].grace_period_ms == 30

    await asyncio.sleep(0.08)
    assert len(forfeited) == 1
    assert forfeited[0].user_id == 1
