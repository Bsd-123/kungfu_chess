"""RoomManager.leave_room awaits a "room closed" broadcast, so -- like
QueueManager's tests -- every test here is async even where no `await`
is needed directly, for consistency with the one method that requires
it."""
from __future__ import annotations

import pytest

from kungfu_chess.app import build_game_engine
from kungfu_chess.config import GameConfig
from kungfu_chess.server.config import NetworkConfig, RoomConfig
from kungfu_chess.server.rooms.room_manager import RoomManager, RoomNotFoundError
from kungfu_chess.server.session.game_session import GameSession, PlayerRole, SpectatorCapError
from kungfu_chess.ui.events.event_bus import EventBus

pytestmark = pytest.mark.asyncio


class FakeConnection:
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f"FakeConnection({self.name})"


def make_manager(room_config=None, sent=None):
    async def send_to_connection(connection, envelope):
        if sent is not None:
            sent.append((connection, envelope))

    def create_session(room_id):
        engine = build_game_engine([['.'] * 8 for _ in range(8)], GameConfig())
        return GameSession(game_id=room_id, engine=engine, event_bus=EventBus(),
                            network_config=NetworkConfig(), send_to_connection=send_to_connection,
                            spectator_cap=(room_config or RoomConfig()).spectator_cap)

    return RoomManager(create_session, room_config or RoomConfig())


async def test_create_room_seats_the_creator_as_white_immediately():
    manager = make_manager()
    creator = FakeConnection('creator')
    room_id = manager.create_room(creator, user_id=1)

    session = manager.get_room(room_id)
    assert session.white_connection is creator
    assert session.white_user_id == 1
    assert len(room_id) == RoomConfig().room_code_length


async def test_join_room_seats_the_second_joiner_as_black():
    manager = make_manager()
    room_id = manager.create_room(FakeConnection('creator'), user_id=1)
    joiner = FakeConnection('joiner')

    role = manager.join_room(room_id, joiner, user_id=2)

    assert role == PlayerRole.BLACK
    session = manager.get_room(room_id)
    assert session.black_connection is joiner
    assert session.black_user_id == 2


async def test_join_room_seats_a_third_joiner_as_a_spectator():
    manager = make_manager()
    room_id = manager.create_room(FakeConnection('creator'))
    manager.join_room(room_id, FakeConnection('joiner'))
    spectator = FakeConnection('spectator')

    role = manager.join_room(room_id, spectator)

    assert role is None  # None means "seated as a spectator"
    session = manager.get_room(room_id)
    assert session.is_spectator(spectator) is True


async def test_join_room_rejects_an_unknown_room_id():
    manager = make_manager()
    with pytest.raises(RoomNotFoundError):
        manager.join_room("NOPE1", FakeConnection('x'))


async def test_join_room_beyond_the_spectator_cap_raises():
    manager = make_manager(RoomConfig(spectator_cap=1))
    room_id = manager.create_room(FakeConnection('creator'))
    manager.join_room(room_id, FakeConnection('joiner'))
    manager.join_room(room_id, FakeConnection('spectator-1'))

    with pytest.raises(SpectatorCapError):
        manager.join_room(room_id, FakeConnection('spectator-2'))


async def test_leave_room_by_a_spectator_only_frees_that_slot():
    manager = make_manager()
    room_id = manager.create_room(FakeConnection('creator'))
    manager.join_room(room_id, FakeConnection('joiner'))
    spectator = FakeConnection('spectator')
    manager.join_room(room_id, spectator)

    await manager.leave_room(room_id, spectator)

    assert manager.get_room(room_id) is not None
    assert manager.get_room(room_id).is_spectator(spectator) is False


async def test_room_persists_while_one_player_remains():
    manager = make_manager()
    creator = FakeConnection('creator')
    room_id = manager.create_room(creator)
    joiner = FakeConnection('joiner')
    manager.join_room(room_id, joiner)

    await manager.leave_room(room_id, joiner)

    assert manager.get_room(room_id) is not None
    assert manager.get_room(room_id).white_connection is creator


async def test_room_is_destroyed_immediately_once_both_players_have_left():
    manager = make_manager()
    creator = FakeConnection('creator')
    joiner = FakeConnection('joiner')
    room_id = manager.create_room(creator)
    manager.join_room(room_id, joiner)

    await manager.leave_room(room_id, creator)
    await manager.leave_room(room_id, joiner)

    assert manager.get_room(room_id) is None


async def test_room_id_is_released_for_reuse_after_teardown():
    manager = make_manager(RoomConfig(room_code_length=2))  # tiny space forces a real reuse check
    creator = FakeConnection('creator')
    joiner = FakeConnection('joiner')
    room_id = manager.create_room(creator)
    manager.join_room(room_id, joiner)
    await manager.leave_room(room_id, creator)
    await manager.leave_room(room_id, joiner)

    assert room_id not in manager._rooms  # freed, not just orphaned


async def test_remaining_spectators_are_told_the_room_closed():
    sent = []
    manager = make_manager(sent=sent)
    creator = FakeConnection('creator')
    joiner = FakeConnection('joiner')
    spectator = FakeConnection('spectator')
    room_id = manager.create_room(creator)
    manager.join_room(room_id, joiner)
    manager.join_room(room_id, spectator)

    await manager.leave_room(room_id, creator)
    await manager.leave_room(room_id, joiner)

    closed_messages = [envelope for conn, envelope in sent
                        if conn is spectator and envelope.type == "room_closed"]
    assert len(closed_messages) == 1
    assert closed_messages[0].payload["room_id"] == room_id


async def test_leave_room_for_an_unknown_room_id_is_a_noop():
    manager = make_manager()
    await manager.leave_room("NOPE1", FakeConnection('x'))  # should not raise
