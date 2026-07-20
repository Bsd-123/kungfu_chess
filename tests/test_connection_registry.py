from kungfu_chess.app import build_game_engine
from kungfu_chess.config import GameConfig
from kungfu_chess.server.connection_registry import ConnectionRegistry
from kungfu_chess.server.session.game_session import GameSession, PlayerRole
from kungfu_chess.server.config import NetworkConfig
from kungfu_chess.ui.events.event_bus import EventBus


def make_session():
    engine = build_game_engine([['.'] * 8 for _ in range(8)], GameConfig())

    async def send_to_connection(connection, envelope):
        pass

    return GameSession(game_id="g1", engine=engine, event_bus=EventBus(),
                        network_config=NetworkConfig(), send_to_connection=send_to_connection)


def test_lookup_returns_none_for_unknown_connection():
    registry = ConnectionRegistry()
    assert registry.lookup(object()) is None


def test_register_and_lookup_round_trip():
    registry = ConnectionRegistry()
    session = make_session()
    connection = object()
    registry.register(connection, session, PlayerRole.WHITE)
    assert registry.lookup(connection) == (session, PlayerRole.WHITE)
    assert connection in registry
    assert len(registry) == 1


def test_unregister_removes_entry():
    registry = ConnectionRegistry()
    session = make_session()
    connection = object()
    registry.register(connection, session, PlayerRole.BLACK)
    registry.unregister(connection)
    assert registry.lookup(connection) is None
    assert connection not in registry


def test_unregister_unknown_connection_is_noop():
    registry = ConnectionRegistry()
    registry.unregister(object())  # should not raise
