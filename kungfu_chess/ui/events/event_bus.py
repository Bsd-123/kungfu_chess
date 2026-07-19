"""Observer/pub-sub core. Pure UI-side -- only publishes/subscribes the
plain-value events in `events.py`; `ui/composition.py` is the sole
caller of `publish`. Generic over event type: adding a new event type
never requires modifying this class."""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Callable, DefaultDict, List, Type, TypeVar

EventT = TypeVar("EventT")
Handler = Callable[[EventT], None]

_logger = logging.getLogger(__name__)


class EventBus:
    def __init__(self) -> None:
        self._subscribers: DefaultDict[type, List[Handler]] = defaultdict(list)

    def subscribe(self, event_type: Type[EventT], handler: Handler) -> None:
        self._subscribers[event_type].append(handler)

    def publish(self, event: EventT) -> None:
        """Notifies every subscriber of `type(event)` in registration order.
        A subscriber that raises is logged and skipped -- one broken
        observer can't block the rest of the publish loop."""
        for handler in self._subscribers[type(event)]:
            try:
                handler(event)
            except Exception:
                _logger.exception(
                    "Event subscriber %r raised while handling %s",
                    handler, type(event).__name__)
