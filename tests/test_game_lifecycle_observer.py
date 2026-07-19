from kungfu_chess.ui.events.events import GameEndedEvent, GameStartedEvent
from kungfu_chess.ui.events.observers.game_lifecycle_observer import GameLifecycleObserver


def test_initial_state_is_not_started_or_ended():
    observer = GameLifecycleObserver()
    assert observer.state.started is False
    assert observer.state.ended is False


def test_game_started_sets_started_state():
    observer = GameLifecycleObserver()
    observer.on_game_started(GameStartedEvent(timestamp_ms=123))
    assert observer.state.started is True
    assert observer.state.started_at_ms == 123
    assert observer.state.ended is False


def test_game_ended_preserves_started_info_and_sets_winner():
    observer = GameLifecycleObserver()
    observer.on_game_started(GameStartedEvent(timestamp_ms=0))
    observer.on_game_ended(GameEndedEvent(winner='b', timestamp_ms=5000))
    assert observer.state.started is True
    assert observer.state.started_at_ms == 0
    assert observer.state.ended is True
    assert observer.state.ended_at_ms == 5000
    assert observer.state.winner == 'b'
