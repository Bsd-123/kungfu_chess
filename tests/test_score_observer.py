from kungfu_chess.ui.events.event_bus import EventBus
from kungfu_chess.ui.events.events import JumpResolvedEvent, MoveResolvedEvent, ScoreUpdatedEvent
from kungfu_chess.ui.events.observers.score_observer import ScoreObserver


def make_move_event(color='w', captured='P'):
    return MoveResolvedEvent(piece_color=color, piece_kind='Q',
                              src_row=0, src_col=0, dst_row=1, dst_col=1,
                              captured_piece_kind=captured)


def test_capture_increments_capturing_color_score():
    observer = ScoreObserver(piece_values={'P': 1})
    observer.on_move_resolved(make_move_event(color='w', captured='P'))
    assert observer.score == {'w': 1, 'b': 0}


def test_non_capture_move_leaves_score_unchanged():
    observer = ScoreObserver(piece_values={'P': 1})
    observer.on_move_resolved(make_move_event(color='w', captured=None))
    assert observer.score == {'w': 0, 'b': 0}


def test_jump_capture_increments_score():
    observer = ScoreObserver(piece_values={'P': 1})
    observer.on_jump_resolved(JumpResolvedEvent(
        piece_color='b', piece_kind='N', row=2, col=2, captured_piece_kind='P'))
    assert observer.score == {'w': 0, 'b': 1}


def test_capture_publishes_score_updated_event_when_bus_given():
    bus = EventBus()
    received = []
    bus.subscribe(ScoreUpdatedEvent, received.append)
    observer = ScoreObserver(piece_values={'P': 1}, event_bus=bus)
    observer.on_move_resolved(make_move_event(color='w', captured='P'))
    assert received == [ScoreUpdatedEvent(color='w', score=1)]


def test_non_capture_does_not_publish_score_updated_event():
    bus = EventBus()
    received = []
    bus.subscribe(ScoreUpdatedEvent, received.append)
    observer = ScoreObserver(piece_values={'P': 1}, event_bus=bus)
    observer.on_move_resolved(make_move_event(color='w', captured=None))
    assert received == []


def test_no_event_bus_does_not_raise():
    observer = ScoreObserver(piece_values={'P': 1})
    observer.on_move_resolved(make_move_event(color='w', captured='P'))  # should not raise
