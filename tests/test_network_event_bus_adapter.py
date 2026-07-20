import asyncio

from kungfu_chess.app import build_game_engine
from kungfu_chess.config import GameConfig
from kungfu_chess.server.config import NetworkConfig
from kungfu_chess.server.network_event_bus_adapter import NetworkEventBusAdapter
from kungfu_chess.server.session.game_session import GameSession
from kungfu_chess.ui.events.event_bus import EventBus
from kungfu_chess.ui.events.events import GameStartedEvent, MoveResolvedEvent, SoundTriggeredEvent


class FakeConnection:
    pass


def make_session(sent):
    engine = build_game_engine([['.'] * 8 for _ in range(8)], GameConfig())

    async def send_to_connection(connection, envelope):
        sent.append((connection, envelope))

    return GameSession(game_id="g1", engine=engine, event_bus=EventBus(),
                        network_config=NetworkConfig(), send_to_connection=send_to_connection)


async def test_move_resolved_domain_event_is_relayed_to_connections():
    sent = []
    session = make_session(sent)
    NetworkEventBusAdapter(session)
    conn_a, conn_b = FakeConnection(), FakeConnection()
    session.add_player(conn_a)
    session.add_player(conn_b)

    session.event_bus.publish(MoveResolvedEvent(
        piece_color='w', piece_kind='P', src_row=6, src_col=0,
        dst_row=5, dst_col=0, captured_piece_kind=None))
    await asyncio.sleep(0.01)

    assert len(sent) == 2
    recipients = {c for c, _ in sent}
    assert recipients == {conn_a, conn_b}
    assert sent[0][1].type == "move_resolved"
    assert sent[0][1].payload["piece_color"] == 'w'


async def test_game_started_event_is_relayed():
    sent = []
    session = make_session(sent)
    NetworkEventBusAdapter(session)
    session.add_player(FakeConnection())

    session.event_bus.publish(GameStartedEvent(timestamp_ms=0))
    await asyncio.sleep(0.01)

    assert len(sent) == 1
    assert sent[0][1].type == "game_started"


async def test_sound_triggered_event_is_relayed():
    sent = []
    session = make_session(sent)
    NetworkEventBusAdapter(session)
    session.add_player(FakeConnection())

    session.event_bus.publish(SoundTriggeredEvent(sound_name="capture"))
    await asyncio.sleep(0.01)

    assert len(sent) == 1
    assert sent[0][1].payload == {"sound_name": "capture"}


async def test_no_connections_means_no_send_but_no_crash():
    sent = []
    session = make_session(sent)
    NetworkEventBusAdapter(session)

    session.event_bus.publish(GameStartedEvent(timestamp_ms=0))
    await asyncio.sleep(0.01)

    assert sent == []
