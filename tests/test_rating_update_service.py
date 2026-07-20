"""Integration test (Testing Strategy's Required "Integration" layer):
a real GameSession + real per-game EventBus + a real SqliteUserRepository,
wired together with no network involved -- proves RatingUpdateService
reacts correctly to a genuine GameEndedEvent regardless of which flow
(matchmaking, or a Room) constructed the GameSession, since this
service only ever looks at the session it was wired to."""
from __future__ import annotations

from kungfu_chess.app import build_game_engine
from kungfu_chess.config import GameConfig
from kungfu_chess.server.auth.credentials_store import SqliteUserRepository
from kungfu_chess.server.auth.db import open_connection
from kungfu_chess.server.config import AuthenticationConfig, NetworkConfig, RatingConfig
from kungfu_chess.server.messaging.application_message_bus import ApplicationMessageBus
from kungfu_chess.server.messaging.transport_events import RatingUpdatedEvent
from kungfu_chess.server.rating.rating_update_service import RatingUpdateService
from kungfu_chess.server.session.game_session import GameSession
from kungfu_chess.ui.events.event_bus import EventBus
from kungfu_chess.ui.events.events import GameEndedEvent

_AUTH_CONFIG = AuthenticationConfig(pbkdf2_iterations=1000)


def make_repository():
    conn = open_connection(":memory:")
    return SqliteUserRepository(conn, _AUTH_CONFIG, RatingConfig(base_rating=1200))


async def _noop_send(connection, envelope):
    pass


def make_session(white_user_id, black_user_id):
    engine = build_game_engine([['.'] * 8 for _ in range(8)], GameConfig())
    session = GameSession(game_id="g1", engine=engine, event_bus=EventBus(),
                           network_config=NetworkConfig(), send_to_connection=_noop_send)
    session.add_player(object(), user_id=white_user_id)
    session.add_player(object(), user_id=black_user_id)
    return session


def test_white_win_updates_both_ratings_per_elo_formula():
    repo = make_repository()
    white = repo.create_user("alice", "hunter2")
    black = repo.create_user("bob", "hunter2")
    session = make_session(white.id, black.id)
    RatingUpdateService(repo, RatingConfig(k_factor=32)).wire(session)

    session.event_bus.publish(GameEndedEvent(winner='w', timestamp_ms=1000))

    assert repo.get_by_id(white.id).rating == 1216
    assert repo.get_by_id(black.id).rating == 1184


def test_black_win_updates_both_ratings_per_elo_formula():
    repo = make_repository()
    white = repo.create_user("alice", "hunter2")
    black = repo.create_user("bob", "hunter2")
    session = make_session(white.id, black.id)
    RatingUpdateService(repo, RatingConfig(k_factor=32)).wire(session)

    session.event_bus.publish(GameEndedEvent(winner='b', timestamp_ms=1000))

    assert repo.get_by_id(white.id).rating == 1184
    assert repo.get_by_id(black.id).rating == 1216


def test_rating_is_applied_at_most_once_for_a_duplicated_event():
    repo = make_repository()
    white = repo.create_user("alice", "hunter2")
    black = repo.create_user("bob", "hunter2")
    session = make_session(white.id, black.id)
    RatingUpdateService(repo, RatingConfig(k_factor=32)).wire(session)

    session.event_bus.publish(GameEndedEvent(winner='w', timestamp_ms=1000))
    session.event_bus.publish(GameEndedEvent(winner='w', timestamp_ms=1001))  # retried/duplicate

    assert repo.get_by_id(white.id).rating == 1216
    assert repo.get_by_id(black.id).rating == 1184
    assert session.rating_applied is True


def test_session_without_identified_players_is_left_unrated():
    repo = make_repository()
    session = make_session(white_user_id=None, black_user_id=None)
    RatingUpdateService(repo, RatingConfig(k_factor=32)).wire(session)

    # Should not raise despite there being no users to look up.
    session.event_bus.publish(GameEndedEvent(winner='w', timestamp_ms=1000))

    assert session.rating_applied is False


def test_rating_update_service_does_not_care_who_created_the_session():
    """RatingUpdateService only ever inspects the GameSession it's wired
    to -- there is nothing matchmaking-specific about it, so a Room-
    constructed session (built the same way, just not via QueueManager)
    is rated identically (Decision 14)."""
    repo = make_repository()
    white = repo.create_user("alice", "hunter2")
    black = repo.create_user("bob", "hunter2")
    room_session = make_session(white.id, black.id)  # stands in for a Room's GameSession
    RatingUpdateService(repo, RatingConfig(k_factor=32)).wire(room_session)

    room_session.event_bus.publish(GameEndedEvent(winner='b', timestamp_ms=1000))

    assert repo.get_by_id(white.id).rating == 1184
    assert repo.get_by_id(black.id).rating == 1216


def test_publishes_rating_updated_events_when_a_message_bus_is_given():
    repo = make_repository()
    white = repo.create_user("alice", "hunter2")
    black = repo.create_user("bob", "hunter2")
    session = make_session(white.id, black.id)
    message_bus = ApplicationMessageBus()
    received = []
    message_bus.subscribe(RatingUpdatedEvent, received.append)
    RatingUpdateService(repo, RatingConfig(k_factor=32), message_bus).wire(session)

    session.event_bus.publish(GameEndedEvent(winner='w', timestamp_ms=1000))

    assert {event.user_id for event in received} == {white.id, black.id}


def test_a_game_ending_without_a_definite_winner_does_not_rate():
    repo = make_repository()
    white = repo.create_user("alice", "hunter2")
    black = repo.create_user("bob", "hunter2")
    session = make_session(white.id, black.id)
    RatingUpdateService(repo, RatingConfig(k_factor=32)).wire(session)

    session.event_bus.publish(GameEndedEvent(winner=None, timestamp_ms=1000))

    assert repo.get_by_id(white.id).rating == 1200
    assert repo.get_by_id(black.id).rating == 1200
    assert session.rating_applied is False
