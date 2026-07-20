"""Observer/pub-sub core for per-game Domain Events. Pure UI-side --
only publishes/subscribes the plain-value events in `events.py`;
`ui/composition.py` is the sole caller of `publish`. A single instance
already belongs to exactly one game, so events on this bus never carry
a `game_id`/`room_id`/`user_id` -- that's the server-wide
`ApplicationMessageBus`'s job (server/messaging/)."""
from __future__ import annotations

from kungfu_chess.common.pubsub import GenericBus


class EventBus(GenericBus):
    pass
