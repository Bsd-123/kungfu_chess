import asyncio

import pytest

from kungfu_chess.app import build_game_engine
from kungfu_chess.config import GameConfig
from kungfu_chess.model.position import Position
from kungfu_chess.server.config import NetworkConfig
from kungfu_chess.server.session.game_session import GameSession, PlayerRole, SessionFullError
from kungfu_chess.server.session.session_reasons import SessionReasons
from kungfu_chess.ui.events.event_bus import EventBus


class FakeConnection:
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f"FakeConnection({self.name})"


def make_session(rows=None, network_config=None, sent=None):
    rows = rows or [['.'] * 8 for _ in range(8)]
    engine = build_game_engine(rows, GameConfig())

    async def send_to_connection(connection, envelope):
        if sent is not None:
            sent.append((connection, envelope))

    return GameSession(
        game_id="abc123", engine=engine, event_bus=EventBus(),
        network_config=network_config or NetworkConfig(),
        send_to_connection=send_to_connection,
    )


def test_first_joiner_is_white_second_is_black():
    session = make_session()
    conn_a, conn_b = FakeConnection('a'), FakeConnection('b')
    assert session.add_player(conn_a) == PlayerRole.WHITE
    assert session.add_player(conn_b) == PlayerRole.BLACK
    assert session.role_for(conn_a) == PlayerRole.WHITE
    assert session.role_for(conn_b) == PlayerRole.BLACK


def test_third_join_raises_session_full_error():
    session = make_session()
    session.add_player(FakeConnection('a'))
    session.add_player(FakeConnection('b'))
    with pytest.raises(SessionFullError):
        session.add_player(FakeConnection('c'))


def test_is_full_reflects_both_slots():
    session = make_session()
    assert session.is_full() is False
    session.add_player(FakeConnection('a'))
    assert session.is_full() is False
    session.add_player(FakeConnection('b'))
    assert session.is_full() is True


def test_remove_player_frees_the_slot():
    session = make_session()
    conn_a = FakeConnection('a')
    session.add_player(conn_a)
    session.remove_player(conn_a)
    assert session.role_for(conn_a) is None
    assert session.white_connection is None


def test_connections_lists_only_occupied_slots():
    session = make_session()
    assert session.connections == []
    conn_a = FakeConnection('a')
    session.add_player(conn_a)
    assert session.connections == [conn_a]


def test_move_command_rejected_for_non_player_connection():
    rows = [['.'] * 8 for _ in range(8)]
    rows[6][0] = 'wP'
    session = make_session(rows)
    session.add_player(FakeConnection('a'))  # white
    stranger = FakeConnection('stranger')
    result = session.handle_move_command(stranger, Position(6, 0), Position(5, 0))
    assert bool(result) is False
    assert result.reason == SessionReasons.NOT_A_PLAYER


def test_move_command_rejected_when_color_does_not_match_role():
    rows = [['.'] * 8 for _ in range(8)]
    rows[6][0] = 'wP'
    session = make_session(rows)
    white = FakeConnection('white')
    black = FakeConnection('black')
    session.add_player(white)
    session.add_player(black)
    # Black tries to move a white piece.
    result = session.handle_move_command(black, Position(6, 0), Position(5, 0))
    assert bool(result) is False
    assert result.reason == SessionReasons.WRONG_COLOR


def test_move_command_accepted_for_matching_color_and_role():
    rows = [['.'] * 8 for _ in range(8)]
    rows[6][0] = 'wP'
    session = make_session(rows)
    white = FakeConnection('white')
    session.add_player(white)
    session.add_player(FakeConnection('black'))
    result = session.handle_move_command(white, Position(6, 0), Position(5, 0))
    assert bool(result) is True


def test_move_command_rejected_no_piece_at_source():
    session = make_session()
    white = FakeConnection('white')
    session.add_player(white)
    result = session.handle_move_command(white, Position(3, 3), Position(2, 3))
    assert bool(result) is False
    assert result.reason == SessionReasons.NO_PIECE_AT_SOURCE


def test_jump_command_rejected_for_wrong_color():
    rows = [['.'] * 8 for _ in range(8)]
    rows[6][0] = 'wP'
    session = make_session(rows)
    white = FakeConnection('white')
    black = FakeConnection('black')
    session.add_player(white)
    session.add_player(black)
    result = session.handle_jump_command(black, Position(6, 0))
    assert bool(result) is False
    assert result.reason == SessionReasons.WRONG_COLOR


def test_jump_command_accepted_for_owning_player():
    rows = [['.'] * 8 for _ in range(8)]
    rows[6][0] = 'wP'
    session = make_session(rows)
    white = FakeConnection('white')
    session.add_player(white)
    result = session.handle_jump_command(white, Position(6, 0))
    assert bool(result) is True


async def test_send_snapshot_to_delivers_one_envelope():
    sent = []
    session = make_session(sent=sent)
    conn = FakeConnection('a')
    await session.send_snapshot_to(conn)
    assert len(sent) == 1
    assert sent[0][0] is conn
    assert sent[0][1].type == "snapshot"


async def test_broadcast_snapshot_delivers_to_every_connection():
    sent = []
    session = make_session(sent=sent)
    conn_a, conn_b = FakeConnection('a'), FakeConnection('b')
    session.add_player(conn_a)
    session.add_player(conn_b)
    await session.broadcast_snapshot()
    recipients = {c for c, _ in sent}
    assert recipients == {conn_a, conn_b}


async def test_tick_loop_advances_clock_only_while_active():
    rows = [['.'] * 8 for _ in range(8)]
    rows[6][0] = 'wP'
    network_config = NetworkConfig(tick_interval_ms=5)
    fake_time = [0.0]
    sent = []
    session = make_session(rows, network_config=network_config, sent=sent)
    session._clock = lambda: fake_time[0]
    conn = FakeConnection('a')
    session.add_player(conn)

    # No motion in flight yet -- tick loop should not broadcast.
    session.start()
    await asyncio.sleep(0.03)
    session.stop()
    assert sent == []

    # Now schedule a move so the engine reports activity.
    session.engine.request_move(Position(6, 0), Position(5, 0))
    session.start()
    for _ in range(5):
        fake_time[0] += network_config.tick_interval_ms / 1000
        await asyncio.sleep(0.01)
    session.stop()
    assert len(sent) > 0
