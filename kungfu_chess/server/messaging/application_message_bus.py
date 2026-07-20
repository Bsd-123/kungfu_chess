"""Server-wide pub/sub for Transport Events -- events that describe
something happening *across* games or connections (match found, player
disconnected, rating updated, etc.), as opposed to the per-game
`EventBus` (ui/events/event_bus.py). Transport Events may carry
`game_id`/`room_id`/`user_id`; Domain Events on the per-game bus never
do. The two buses are never merged: a module importing both a Domain
Event and a Transport Event type is a signal it's doing two jobs and
should be split (see master_work_plan.md, Event & Message Architecture)."""
from __future__ import annotations

from kungfu_chess.common.pubsub import GenericBus


class ApplicationMessageBus(GenericBus):
    pass
