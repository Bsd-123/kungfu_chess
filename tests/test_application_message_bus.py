from dataclasses import dataclass

from kungfu_chess.common.pubsub import GenericBus
from kungfu_chess.server.messaging.application_message_bus import ApplicationMessageBus
from kungfu_chess.ui.events.event_bus import EventBus


@dataclass(frozen=True)
class FakeTransportEvent:
    game_id: str


def test_application_message_bus_dispatches_like_generic_bus():
    received = []
    bus = ApplicationMessageBus()
    bus.subscribe(FakeTransportEvent, received.append)
    event = FakeTransportEvent(game_id='abc123')
    bus.publish(event)
    assert received == [event]


def test_application_message_bus_and_event_bus_are_distinct_types():
    # The two-namespace boundary (Domain Events vs. Transport Events) is
    # enforced by these being separate classes, not by shared state.
    assert ApplicationMessageBus is not EventBus
    assert issubclass(ApplicationMessageBus, GenericBus)
    assert issubclass(EventBus, GenericBus)
    assert not isinstance(ApplicationMessageBus(), EventBus)
    assert not isinstance(EventBus(), ApplicationMessageBus)
