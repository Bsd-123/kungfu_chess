"""Applies an ELO update to both players' persisted ratings whenever a
`GameSession` reports `GameEndedEvent` (Decision 14: every server-
created game is rated -- Play and Room alike; this service is wired
per-`GameSession` and never asks who created it, so it naturally covers
both without special-casing either). Idempotent via
`GameSession.rating_applied` (Phase 4 risk: "duplicate rating
application" from a retried/double-fired event) -- applied at most once
per session."""
from __future__ import annotations

from typing import Optional

from kungfu_chess.server.auth.credentials_store import SqliteUserRepository
from kungfu_chess.server.config import RatingConfig
from kungfu_chess.server.messaging.application_message_bus import ApplicationMessageBus
from kungfu_chess.server.messaging.transport_events import RatingUpdatedEvent
from kungfu_chess.server.rating.elo_calculator import expected_score, update_rating
from kungfu_chess.server.session.game_session import GameSession
from kungfu_chess.ui.events.events import GameEndedEvent


class RatingUpdateService:
    def __init__(self, users: SqliteUserRepository, rating_config: Optional[RatingConfig] = None,
                 message_bus: Optional[ApplicationMessageBus] = None):
        self._users = users
        self._rating_config = rating_config or RatingConfig()
        self._message_bus = message_bus

    def wire(self, session: GameSession) -> None:
        """Subscribes this service to one GameSession's domain bus.
        Callers wire this alongside NetworkEventBusAdapter/domain-event
        wiring at session-creation time, whether that session came from
        Play matchmaking or a Room."""
        session.event_bus.subscribe(GameEndedEvent, lambda event: self._on_game_ended(session, event))

    def _on_game_ended(self, session: GameSession, event: GameEndedEvent) -> None:
        if session.rating_applied:
            return
        if session.white_user_id is None or session.black_user_id is None:
            return  # an anonymous/offline-style session -- nothing to rate
        if event.winner not in ('w', 'b'):
            return  # Decision 12: only a definite winner triggers a rating change

        # Flip before writing -- a retried/duplicate GameEndedEvent must
        # never apply the update twice, even if this handler is
        # re-entered synchronously before the writes below complete.
        session.rating_applied = True

        white = self._users.get_by_id(session.white_user_id)
        black = self._users.get_by_id(session.black_user_id)

        white_actual = 1.0 if event.winner == 'w' else 0.0
        black_actual = 1.0 - white_actual

        new_white = round(update_rating(
            white.rating, expected_score(white.rating, black.rating),
            white_actual, self._rating_config.k_factor))
        new_black = round(update_rating(
            black.rating, expected_score(black.rating, white.rating),
            black_actual, self._rating_config.k_factor))

        self._users.update_rating(white.id, new_white)
        self._users.update_rating(black.id, new_black)

        if self._message_bus is not None:
            self._message_bus.publish(RatingUpdatedEvent(white.id, white.rating, new_white))
            self._message_bus.publish(RatingUpdatedEvent(black.id, black.rating, new_black))
