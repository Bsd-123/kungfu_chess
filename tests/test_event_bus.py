from dataclasses import dataclass

from kungfu_chess.ui.events.event_bus import EventBus


@dataclass(frozen=True)
class FakeEventA:
    value: int


@dataclass(frozen=True)
class FakeEventB:
    value: int


def test_publish_with_no_subscribers_is_noop():
    bus = EventBus()
    bus.publish(FakeEventA(1))  # should not raise


def test_subscriber_receives_only_its_event_type():
    received_a, received_b = [], []
    bus = EventBus()
    bus.subscribe(FakeEventA, received_a.append)
    bus.subscribe(FakeEventB, received_b.append)
    event = FakeEventA(1)
    bus.publish(event)
    assert received_a == [event]
    assert received_b == []


def test_multiple_subscribers_all_receive_event_in_order():
    order = []
    bus = EventBus()
    bus.subscribe(FakeEventA, lambda e: order.append('a'))
    bus.subscribe(FakeEventA, lambda e: order.append('b'))
    bus.publish(FakeEventA(1))
    assert order == ['a', 'b']


def test_new_event_type_needs_no_bus_change():
    # Registering a type the bus has never seen before must work with
    # zero modifications to EventBus itself (OCP).
    received = []
    bus = EventBus()
    bus.subscribe(FakeEventB, received.append)
    event = FakeEventB(42)
    bus.publish(event)
    assert received == [event]


def test_raising_subscriber_does_not_block_other_subscribers():
    order = []

    def broken(_event):
        raise RuntimeError("boom")

    bus = EventBus()
    bus.subscribe(FakeEventA, broken)
    bus.subscribe(FakeEventA, lambda e: order.append('ok'))
    bus.publish(FakeEventA(1))  # should not raise
    assert order == ['ok']
