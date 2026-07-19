from kungfu_chess.ui.events.event_bus import EventBus
from kungfu_chess.ui.events.events import (
    GameEndedEvent,
    GameStartedEvent,
    JumpResolvedEvent,
    MoveResolvedEvent,
    SoundTriggeredEvent,
)
from kungfu_chess.ui.events.observers.sound_observer import SoundObserver


def _make_bus_with_capture():
    bus = EventBus()
    received = []
    bus.subscribe(SoundTriggeredEvent, received.append)
    observer = SoundObserver(bus)
    return observer, received


def test_move_without_capture_triggers_move_sound():
    observer, received = _make_bus_with_capture()
    observer.on_move_resolved(MoveResolvedEvent(
        piece_color='w', piece_kind='P', src_row=6, src_col=0,
        dst_row=5, dst_col=0, captured_piece_kind=None))
    assert received == [SoundTriggeredEvent(sound_name='move')]


def test_move_with_capture_triggers_capture_sound():
    observer, received = _make_bus_with_capture()
    observer.on_move_resolved(MoveResolvedEvent(
        piece_color='w', piece_kind='P', src_row=6, src_col=0,
        dst_row=5, dst_col=1, captured_piece_kind='N'))
    assert received == [SoundTriggeredEvent(sound_name='capture')]


def test_jump_without_capture_triggers_jump_sound():
    observer, received = _make_bus_with_capture()
    observer.on_jump_resolved(JumpResolvedEvent(
        piece_color='b', piece_kind='N', row=2, col=2, captured_piece_kind=None))
    assert received == [SoundTriggeredEvent(sound_name='jump')]


def test_game_started_triggers_game_start_sound():
    observer, received = _make_bus_with_capture()
    observer.on_game_started(GameStartedEvent(timestamp_ms=0))
    assert received == [SoundTriggeredEvent(sound_name='game_start')]


def test_game_ended_triggers_game_end_sound():
    observer, received = _make_bus_with_capture()
    observer.on_game_ended(GameEndedEvent(winner='w', timestamp_ms=9000))
    assert received == [SoundTriggeredEvent(sound_name='game_end')]
