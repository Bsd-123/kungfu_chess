import asyncio

import pytest

from kungfu_chess.app import build_game_engine
from kungfu_chess.config import GameConfig
from kungfu_chess.engine.domain_event_wiring import wire_engine_domain_events
from kungfu_chess.model.position import Position
from kungfu_chess.server.config import NetworkConfig
from kungfu_chess.server.session.game_session import (
    GameSession, PlayerRole, SessionFullError, SpectatorCapError,
)
from kungfu_chess.server.session.session_reasons import SessionReasons
from kungfu_chess.ui.events.event_bus import EventBus
from kungfu_chess.ui.events.events import MoveResolvedEvent


class FakeConnection:
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f"FakeConnection({self.name})"


def make_session(rows=None, network_config=None, sent=None, spectator_cap=20):
    rows = rows or [['.'] * 8 for _ in range(8)]
    engine = build_game_engine(rows, GameConfig())

    async def send_to_connection(connection, envelope):
        if sent is not None:
            sent.append((connection, envelope))

    return GameSession(
        game_id="abc123", engine=engine, event_bus=EventBus(),
        network_config=network_config or NetworkConfig(),
        send_to_connection=send_to_connection, spectator_cap=spectator_cap,
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


def test_add_player_records_the_optional_user_id_per_role():
    session = make_session()
    conn_a, conn_b = FakeConnection('a'), FakeConnection('b')
    session.add_player(conn_a, user_id=7)
    session.add_player(conn_b, user_id=9)
    assert session.white_user_id == 7
    assert session.black_user_id == 9


def test_add_player_without_a_user_id_defaults_to_none():
    session = make_session()
    session.add_player(FakeConnection('a'))
    assert session.white_user_id is None


def test_rating_applied_defaults_to_false():
    session = make_session()
    assert session.rating_applied is False


def test_connections_lists_only_occupied_slots():
    session = make_session()
    assert session.connections == []
    conn_a = FakeConnection('a')
    session.add_player(conn_a)
    assert session.connections == [conn_a]


def test_add_spectator_appends_to_the_spectator_list():
    session = make_session()
    spectator = FakeConnection('spectator')
    session.add_spectator(spectator)
    assert session.is_spectator(spectator) is True
    assert session.spectators == [spectator]


def test_add_spectator_beyond_the_cap_raises():
    session = make_session(spectator_cap=2)
    session.add_spectator(FakeConnection('s1'))
    session.add_spectator(FakeConnection('s2'))
    with pytest.raises(SpectatorCapError):
        session.add_spectator(FakeConnection('s3'))


def test_remove_spectator_frees_the_slot():
    session = make_session()
    spectator = FakeConnection('spectator')
    session.add_spectator(spectator)
    session.remove_spectator(spectator)
    assert session.is_spectator(spectator) is False
    assert session.spectators == []


def test_remove_spectator_for_a_non_spectator_is_a_noop():
    session = make_session()
    session.remove_spectator(FakeConnection('stranger'))  # should not raise


def test_connections_excludes_spectators_but_all_connections_includes_them():
    session = make_session()
    player, spectator = FakeConnection('player'), FakeConnection('spectator')
    session.add_player(player)
    session.add_spectator(spectator)
    assert session.connections == [player]
    assert set(session.all_connections) == {player, spectator}


def test_spectator_move_command_is_rejected_as_not_a_player():
    rows = [['.'] * 8 for _ in range(8)]
    rows[6][0] = 'wP'
    session = make_session(rows)
    session.add_player(FakeConnection('white'))
    spectator = FakeConnection('spectator')
    session.add_spectator(spectator)
    result = session.handle_move_command(spectator, Position(6, 0), Position(5, 0))
    assert bool(result) is False
    assert result.reason == SessionReasons.NOT_A_PLAYER


async def test_broadcast_reaches_spectators_too():
    sent = []
    session = make_session(sent=sent)
    player, spectator = FakeConnection('player'), FakeConnection('spectator')
    session.add_player(player)
    session.add_spectator(spectator)
    await session.broadcast_snapshot()
    recipients = {c for c, _ in sent}
    assert recipients == {player, spectator}


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


def test_rebind_player_reseats_the_role_without_touching_user_id():
    session = make_session()
    old_conn = FakeConnection('old')
    new_conn = FakeConnection('new')
    session.add_player(old_conn, user_id=7)

    session.rebind_player(PlayerRole.WHITE, new_conn)

    assert session.white_connection is new_conn
    assert session.white_user_id == 7


def test_has_pending_disconnect_is_false_by_default():
    session = make_session()
    assert session.has_pending_disconnect(PlayerRole.WHITE) is False


async def test_mark_disconnected_then_cancel_prevents_on_expire():
    session = make_session()
    fired = []
    session.mark_disconnected(PlayerRole.WHITE, grace_period_ms=30, on_expire=lambda: fired.append(True))

    assert session.has_pending_disconnect(PlayerRole.WHITE) is True
    cancelled = session.cancel_disconnect(PlayerRole.WHITE)
    await asyncio.sleep(0.06)

    assert cancelled is True
    assert session.has_pending_disconnect(PlayerRole.WHITE) is False
    assert fired == []


async def test_mark_disconnected_calls_on_expire_after_the_grace_period():
    session = make_session()
    fired = []
    session.mark_disconnected(PlayerRole.WHITE, grace_period_ms=30, on_expire=lambda: fired.append(True))

    await asyncio.sleep(0.08)

    assert fired == [True]
    assert session.has_pending_disconnect(PlayerRole.WHITE) is False


def test_cancel_disconnect_with_nothing_pending_returns_false():
    session = make_session()
    assert session.cancel_disconnect(PlayerRole.BLACK) is False


async def test_stop_cancels_any_pending_disconnect_timer():
    session = make_session()
    fired = []
    session.mark_disconnected(PlayerRole.WHITE, grace_period_ms=30, on_expire=lambda: fired.append(True))

    session.stop()
    await asyncio.sleep(0.06)

    assert fired == []
    assert session.has_pending_disconnect(PlayerRole.WHITE) is False


async def test_stop_called_synchronously_from_within_the_tick_loop_does_not_truncate_the_broadcast():
    """Regression test: a domain-event subscriber that reacts to a
    settled move by calling session.stop() runs *inside* the tick
    loop's own call stack (advance_clock -> settlement listener ->
    event_bus.publish -> this subscriber). Self-cancelling the
    currently-running tick task there would defer a CancelledError to
    the very next await -- the in-flight broadcast_snapshot() -- and
    could truncate delivery to whichever connections hadn't been sent
    to yet. stop() must special-case this so the broadcast still
    reaches every connection before the loop exits."""
    rows = [['.'] * 8 for _ in range(8)]
    rows[6][0] = 'wP'
    # Fast enough that the move actually settles (fires MoveResolvedEvent)
    # within the fake-time window advanced below -- the default 2500ms
    # duration would leave the move still in flight the whole time,
    # never triggering the subscriber this test depends on.
    game_config = GameConfig(move_duration_ms={'P': 10}, default_move_duration_ms=10)
    network_config = NetworkConfig(tick_interval_ms=5)
    fake_time = [0.0]
    sent = []

    async def send_to_connection(connection, envelope):
        # A real yield point (unlike the module-level make_session's
        # fake, which never suspends and so never gives asyncio a
        # chance to deliver a pending cancellation) -- needed to
        # actually reproduce the truncated-broadcast hazard this test
        # guards against.
        await asyncio.sleep(0)
        sent.append((connection, envelope))

    engine = build_game_engine(rows, game_config)
    session = GameSession(game_id="abc123", engine=engine, event_bus=EventBus(),
                           network_config=network_config, send_to_connection=send_to_connection)
    session._clock = lambda: fake_time[0]
    wire_engine_domain_events(session.engine, session.event_bus)
    conn_a, conn_b = FakeConnection('a'), FakeConnection('b')
    session.add_player(conn_a)
    session.add_player(conn_b)

    # A connection appearing anywhere in `sent` isn't enough to prove
    # the *final* broadcast wasn't truncated -- both connections already
    # appear in earlier, unaffected ticks either way. Mark exactly where
    # in `sent` the settlement fires, so the assertion below can inspect
    # only what should have been appended afterward.
    marker_index = []

    def on_move_resolved(event):
        marker_index.append(len(sent))
        session.stop()

    session.event_bus.subscribe(MoveResolvedEvent, on_move_resolved)

    session.engine.request_move(Position(6, 0), Position(5, 0))
    session.start()
    for _ in range(20):
        fake_time[0] += network_config.tick_interval_ms / 1000
        await asyncio.sleep(0.01)

    assert len(marker_index) == 1
    final_broadcast = sent[marker_index[0]:]
    final_recipients = {c for c, e in final_broadcast if e.type == "snapshot"}
    assert final_recipients == {conn_a, conn_b}, (
        f"the broadcast for the tick that ended the game was truncated: {final_broadcast!r}")
