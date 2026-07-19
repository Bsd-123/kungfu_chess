from kungfu_chess.engine.settlement_notifier import SettlementNotifier


def test_no_listeners_notify_is_noop():
    notifier = SettlementNotifier()
    notifier.notify(object())  # should not raise


def test_single_listener_receives_event():
    received = []
    notifier = SettlementNotifier()
    notifier.add_listener(lambda e: received.append(e))
    event = object()
    notifier.notify(event)
    assert received == [event]


def test_multiple_listeners_all_receive_event_in_order():
    order = []
    notifier = SettlementNotifier()
    notifier.add_listener(lambda e: order.append('a'))
    notifier.add_listener(lambda e: order.append('b'))
    notifier.notify(object())
    assert order == ['a', 'b']
