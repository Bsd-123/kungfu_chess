from kungfu_chess.engine.game_lifecycle_notifier import GameLifecycleNotifier


def test_no_listeners_notify_is_noop():
    notifier = GameLifecycleNotifier()
    notifier.notify_game_ended('w', 1000)  # should not raise


def test_single_listener_receives_winner_and_clock_ms():
    received = []
    notifier = GameLifecycleNotifier()
    notifier.add_listener(lambda winner, clock_ms: received.append((winner, clock_ms)))
    notifier.notify_game_ended('b', 4200)
    assert received == [('b', 4200)]


def test_multiple_listeners_all_receive_event_in_order():
    order = []
    notifier = GameLifecycleNotifier()
    notifier.add_listener(lambda winner, clock_ms: order.append('a'))
    notifier.add_listener(lambda winner, clock_ms: order.append('b'))
    notifier.notify_game_ended('w', 0)
    assert order == ['a', 'b']
