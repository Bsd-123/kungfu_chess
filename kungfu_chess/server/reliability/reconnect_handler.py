"""Token-based reconnection binding (Decision 7): on a new connection
presenting a session token, checks whether that token's account matches
a pending disconnect on any live `GameSession`; if so, rebinds the new
socket to that session's existing player slot (same color, same
`GameEngine` reference) and cancels the pending forfeit timer -- the
player resumes exactly where the game currently is. If no pending
disconnect matches, this isn't a reconnection at all, just an ordinary
fresh login (Phase 3's flow), and the caller proceeds accordingly.

`list_active_sessions` is injected rather than this module owning a
registry itself -- Play and Room sessions currently live in different
places (`QueueManager`-created sessions, `RoomManager._rooms`), and
this handler shouldn't need to know that split; whoever composes the
real server supplies one callable that covers both."""
from __future__ import annotations

from typing import Callable, Iterable, Optional, Tuple

from kungfu_chess.server.auth.session_manager import SessionManager
from kungfu_chess.server.messaging.application_message_bus import ApplicationMessageBus
from kungfu_chess.server.messaging.transport_events import ReconnectedEvent
from kungfu_chess.server.protocol import make_envelope
from kungfu_chess.server.session.game_session import GameSession, PlayerRole

ListActiveSessions = Callable[[], Iterable[GameSession]]


class ReconnectHandler:
    def __init__(self, session_manager: SessionManager, list_active_sessions: ListActiveSessions,
                 message_bus: Optional[ApplicationMessageBus] = None):
        self._session_manager = session_manager
        self._list_active_sessions = list_active_sessions
        self._message_bus = message_bus

    async def attempt_reconnect(self, token: str,
                                 connection: object) -> Optional[Tuple[GameSession, PlayerRole]]:
        """Returns `(session, role)` on a successful reconnection, or
        None if `token` doesn't resolve to an account with a pending
        disconnect anywhere -- the caller should then fall through to
        normal fresh-connection handling."""
        user_id = self._session_manager.resolve(token)
        if user_id is None:
            return None

        for session in self._list_active_sessions():
            role = self._pending_role_for(session, user_id)
            if role is None:
                continue

            session.cancel_disconnect(role)
            session.rebind_player(role, connection)
            await session.send_snapshot_to(connection)

            envelope = make_envelope("reconnected", {"role": role.value}, session.network_config)
            await session.broadcast(envelope)

            if self._message_bus is not None:
                self._message_bus.publish(ReconnectedEvent(game_id=session.game_id, user_id=user_id))

            return session, role

        return None

    @staticmethod
    def _pending_role_for(session: GameSession, user_id: int) -> Optional[PlayerRole]:
        if session.white_user_id == user_id and session.has_pending_disconnect(PlayerRole.WHITE):
            return PlayerRole.WHITE
        if session.black_user_id == user_id and session.has_pending_disconnect(PlayerRole.BLACK):
            return PlayerRole.BLACK
        return None
