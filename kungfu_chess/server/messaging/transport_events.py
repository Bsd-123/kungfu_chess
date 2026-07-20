"""Transport Events (see master_work_plan.md's Event & Message
Architecture): carried on the server-wide `ApplicationMessageBus`, may
name a `user_id`/`game_id` since they describe something happening
*across* games or connections, unlike the per-game `EventBus`'s Domain
Events. Frozen dataclasses of primitives only, same convention as
`ui/events/events.py`."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class MatchFoundEvent:
    game_id: str
    white_user_id: int
    black_user_id: int


@dataclass(frozen=True)
class MatchmakingTimedOutEvent:
    user_id: int


@dataclass(frozen=True)
class RatingUpdatedEvent:
    user_id: int
    old_rating: int
    new_rating: int


@dataclass(frozen=True)
class PlayerDisconnectedEvent:
    game_id: str
    user_id: Optional[int]
    grace_period_ms: int


@dataclass(frozen=True)
class ReconnectedEvent:
    game_id: str
    user_id: int


@dataclass(frozen=True)
class PlayerForfeitedEvent:
    game_id: str
    user_id: Optional[int]
