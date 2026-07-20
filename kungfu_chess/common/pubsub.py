"""Generic publish/subscribe dispatch, shared by the per-game domain
`EventBus` (ui/events/event_bus.py) and the server-wide
`ApplicationMessageBus` (server/messaging/application_message_bus.py).
Those two stay distinct *types* -- this module only factors out the
identical dispatch mechanics (DRY) so the two-namespace boundary
between Domain Events and Transport Events is enforced by which class
a module imports, never by divergent bus implementations."""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Callable, DefaultDict, List, Type, TypeVar

EventT = TypeVar("EventT")
Handler = Callable[[EventT], None]

_logger = logging.getLogger(__name__)


class GenericBus:
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
