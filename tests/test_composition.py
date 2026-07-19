from kungfu_chess.app import build_game_engine
from kungfu_chess.config import GameConfig
from kungfu_chess.model.position import Position
from kungfu_chess.ui import composition
from kungfu_chess.ui.events.event_bus import EventBus
from kungfu_chess.ui.events.events import GameEndedEvent, GameStartedEvent, MoveResolvedEvent


class RecordingEventBus(EventBus):
    """Captures every published event on top of real dispatch, so tests
    can assert on wiring without composition.py exposing its internal
    bus instance."""
    instances = []

    def __init__(self):
        super().__init__()
        self.published = []
        RecordingEventBus.instances.append(self)

    def publish(self, event):
        self.published.append(event)
        super().publish(event)


def _wire(monkeypatch, rows, config=None):
    monkeypatch.setattr(composition, "EventBus", RecordingEventBus)
    RecordingEventBus.instances.clear()
    config = config or GameConfig()
    engine = build_game_engine(rows, config)
    move_log, score = composition.wire_event_observers(engine, config=config)
    bus = RecordingEventBus.instances[-1]
    return engine, move_log, score, bus


def test_game_started_event_published_exactly_once_at_wiring(monkeypatch):
    rows = [['.'] * 8 for _ in range(8)]
    _, _, _, bus = _wire(monkeypatch, rows)
    started = [e for e in bus.published if isinstance(e, GameStartedEvent)]
    assert len(started) == 1
    assert started[0].timestamp_ms == 0


def test_move_resolution_updates_score_and_move_log_via_bus(monkeypatch):
    rows = [['.'] * 8 for _ in range(8)]
    rows[6][0] = 'wP'
    rows[5][1] = 'bP'
    config = GameConfig()
    engine, move_log, score, bus = _wire(monkeypatch, rows, config)

    engine.request_move(Position(6, 0), Position(5, 1))
    engine.advance_clock(config.move_duration_for('P'))

    assert len(move_log.entries['w']) == 1
    assert score.score['w'] > 0
    resolved = [e for e in bus.published if isinstance(e, MoveResolvedEvent)]
    assert len(resolved) == 1
    assert resolved[0].captured_piece_kind == 'P'


def test_win_condition_publishes_game_ended_event(monkeypatch):
    rows = [['.'] * 8 for _ in range(8)]
    rows[7][0] = 'wR'
    rows[0][0] = 'bK'
    config = GameConfig()
    engine, _, _, bus = _wire(monkeypatch, rows, config)

    engine.request_move(Position(7, 0), Position(0, 0))
    engine.advance_clock(config.move_duration_for('R') * 7)

    ended = [e for e in bus.published if isinstance(e, GameEndedEvent)]
    assert len(ended) == 1
    assert ended[0].winner == 'w'
    assert engine.game_over is True
