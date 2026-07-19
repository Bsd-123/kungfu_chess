from kungfu_chess.ui.events.event_bus import EventBus
from kungfu_chess.ui.events.events import MoveLoggedEvent, MoveResolvedEvent
from kungfu_chess.ui.events.observers.moves_log_observer import MoveLogObserver, format_time_ms


def make_event(color='w', kind='P', captured=None):
    return MoveResolvedEvent(piece_color=color, piece_kind=kind,
                              src_row=6, src_col=4, dst_row=4, dst_col=4,
                              captured_piece_kind=captured)


def test_on_move_resolved_appends_entry_for_color():
    observer = MoveLogObserver(clock_ms_source=lambda: 1000)
    observer.on_move_resolved(make_event(color='w'))
    assert len(observer.entries['w']) == 1
    assert observer.entries['b'] == []


def test_recent_returns_last_n_entries():
    times = iter([0, 100, 200])
    observer = MoveLogObserver(clock_ms_source=lambda: next(times))
    for _ in range(3):
        observer.on_move_resolved(make_event(color='w'))
    recent = observer.recent('w', 2)
    assert len(recent) == 2


def test_format_time_ms_formats_minutes_seconds_millis():
    assert format_time_ms(4105) == "00:04.105"


def test_publishes_move_logged_event_when_bus_given():
    bus = EventBus()
    received = []
    bus.subscribe(MoveLoggedEvent, received.append)
    observer = MoveLogObserver(clock_ms_source=lambda: 500, event_bus=bus)
    observer.on_move_resolved(make_event(color='w'))
    assert len(received) == 1
    assert received[0].color == 'w'
    assert received[0].time_ms == 500


def test_no_event_bus_does_not_raise():
    observer = MoveLogObserver(clock_ms_source=lambda: 0)
    observer.on_move_resolved(make_event())  # should not raise
