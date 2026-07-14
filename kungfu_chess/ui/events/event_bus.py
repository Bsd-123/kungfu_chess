"""Observer/pub-sub core (plan section 7.1/7.6). Pure UI-side: no
import of anything from `kungfu_chess.realtime`/`kungfu_chess.model` --
only ever publishes/subscribes the plain-value events in `events.py`.
`ui/app.py`'s composition root is the sole caller of `publish_*`, fed
by a small bridge function that translates the engine's own
`SettlementEvent` into these types."""
from __future__ import annotations

from typing import Callable, List

from kungfu_chess.ui.events.events import JumpResolvedEvent, MoveResolvedEvent

MoveResolvedHandler = Callable[[MoveResolvedEvent], None]
JumpResolvedHandler = Callable[[JumpResolvedEvent], None]


class EventBus:
    def __init__(self) -> None:
        self._move_subscribers: List[MoveResolvedHandler] = []
        self._jump_subscribers: List[JumpResolvedHandler] = []

    def subscribe_move_resolved(self, handler: MoveResolvedHandler) -> None:
        self._move_subscribers.append(handler)

    def subscribe_jump_resolved(self, handler: JumpResolvedHandler) -> None:
        self._jump_subscribers.append(handler)

    def publish_move_resolved(self, event: MoveResolvedEvent) -> None:
        for handler in self._move_subscribers:
            handler(event)

    def publish_jump_resolved(self, event: JumpResolvedEvent) -> None:
        for handler in self._jump_subscribers:
            handler(event)
