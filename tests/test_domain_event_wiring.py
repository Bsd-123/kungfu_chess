from kungfu_chess.app import build_game_engine
from kungfu_chess.config import GameConfig
from kungfu_chess.engine.domain_event_wiring import wire_engine_domain_events
from kungfu_chess.model.position import Position
from kungfu_chess.ui.events.event_bus import EventBus
from kungfu_chess.ui.events.events import GameEndedEvent, JumpResolvedEvent, MoveResolvedEvent


def test_move_settlement_publishes_move_resolved_event():
    rows = [['.'] * 8 for _ in range(8)]
    rows[6][0] = 'wP'
    config = GameConfig()
    engine = build_game_engine(rows, config)
    bus = EventBus()
    received = []
    bus.subscribe(MoveResolvedEvent, received.append)
    wire_engine_domain_events(engine, bus)

    engine.request_move(Position(6, 0), Position(5, 0))
    engine.advance_clock(config.move_duration_for('P'))

    assert len(received) == 1
    assert received[0].src_row == 6 and received[0].dst_row == 5


def test_jump_settlement_publishes_jump_resolved_event():
    rows = [['.'] * 8 for _ in range(8)]
    rows[6][0] = 'wP'
    config = GameConfig()
    engine = build_game_engine(rows, config)
    bus = EventBus()
    received = []
    bus.subscribe(JumpResolvedEvent, received.append)
    wire_engine_domain_events(engine, bus)

    engine.request_jump(Position(6, 0))
    engine.advance_clock(config.jump_duration_ms)

    assert len(received) == 1
    assert received[0].row == 6 and received[0].col == 0


def test_win_condition_publishes_game_ended_event():
    rows = [['.'] * 8 for _ in range(8)]
    rows[7][0] = 'wR'
    rows[0][0] = 'bK'
    config = GameConfig()
    engine = build_game_engine(rows, config)
    bus = EventBus()
    received = []
    bus.subscribe(GameEndedEvent, received.append)
    wire_engine_domain_events(engine, bus)

    engine.request_move(Position(7, 0), Position(0, 0))
    engine.advance_clock(config.move_duration_for('R') * 7)

    assert len(received) == 1
    assert received[0].winner == 'w'


def test_wiring_itself_publishes_nothing():
    # wire_engine_domain_events only registers listeners; it must not
    # publish GameStartedEvent or anything else on its own -- callers
    # decide when "the game becomes playable" for their own context.
    engine = build_game_engine([['.'] * 8 for _ in range(8)], GameConfig())
    bus = EventBus()
    received = []
    bus.subscribe(MoveResolvedEvent, received.append)
    bus.subscribe(JumpResolvedEvent, received.append)
    bus.subscribe(GameEndedEvent, received.append)

    wire_engine_domain_events(engine, bus)

    assert received == []
