"""The "Play" matchmaking queue (Decisions 5/6/13): enqueue player +
rating, scan for a partner within a fixed +/-ELO band that never widens
while waiting, dequeue on match/timeout/cancel. Knows nothing about
WebSockets or SQLite -- `GameSession` construction and Transport Event
publishing are both injected, so this stays a pure producer/consumer
queue plus a fixed-band scan, reusable regardless of what sits behind
`create_session`/`message_bus`.

Race safety (Decision 1: single-threaded asyncio): both `_match` and
the timeout callback flip `claimed` synchronously, with no `await`
between checking it and setting it, so a match and a same-tick timeout
for the same entry can never both fire -- whichever runs first wins the
entry outright."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from kungfu_chess.server.config import MatchmakingConfig
from kungfu_chess.server.messaging.application_message_bus import ApplicationMessageBus
from kungfu_chess.server.messaging.transport_events import MatchFoundEvent, MatchmakingTimedOutEvent
from kungfu_chess.server.session.game_session import GameSession


@dataclass
class QueueEntry:
    connection: object
    user_id: int
    rating: int
    claimed: bool = field(default=False, repr=False)


CreateSession = Callable[[QueueEntry, QueueEntry], GameSession]


class QueueManager:
    def __init__(self, create_session: CreateSession, message_bus: ApplicationMessageBus,
                 config: Optional[MatchmakingConfig] = None):
        self._create_session = create_session
        self._message_bus = message_bus
        self._config = config or MatchmakingConfig()
        self._queue: List[QueueEntry] = []

    def enqueue(self, connection: object, user_id: int, rating: int) -> QueueEntry:
        """Matches immediately against anyone already waiting within the
        fixed ELO band; otherwise joins the queue and starts this
        entry's own 1-minute timeout clock (Decision 5)."""
        entry = QueueEntry(connection=connection, user_id=user_id, rating=rating)
        partner = self._find_partner(entry)
        if partner is not None:
            self._match(partner, entry)  # partner was waiting first -> White
            return entry

        self._queue.append(entry)
        asyncio.ensure_future(self._timeout_after(entry))
        return entry

    def cancel(self, connection: object) -> bool:
        """Removes a still-waiting entry (player pressed cancel, or
        disconnected while searching). Returns False if the connection
        wasn't queued or was already matched/timed out."""
        for entry in self._queue:
            if entry.connection is connection:
                entry.claimed = True
                self._queue.remove(entry)
                return True
        return False

    def _find_partner(self, entry: QueueEntry) -> Optional[QueueEntry]:
        band = self._config.elo_band
        for candidate in self._queue:
            if not candidate.claimed and abs(candidate.rating - entry.rating) <= band:
                return candidate
        return None

    def _match(self, first: QueueEntry, second: QueueEntry) -> None:
        first.claimed = True
        second.claimed = True
        if first in self._queue:
            self._queue.remove(first)
        session = self._create_session(first, second)
        self._message_bus.publish(MatchFoundEvent(
            game_id=session.game_id, white_user_id=first.user_id, black_user_id=second.user_id))

    async def _timeout_after(self, entry: QueueEntry) -> None:
        await asyncio.sleep(self._config.timeout_s)
        if entry.claimed:
            return
        entry.claimed = True
        if entry in self._queue:
            self._queue.remove(entry)
        self._message_bus.publish(MatchmakingTimedOutEvent(user_id=entry.user_id))
