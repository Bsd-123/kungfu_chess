"""Maps a connection to the `(GameSession, role)` it belongs to.
Deliberately capacity-agnostic -- it does not enforce "max 2 players"
or "max 20 spectators" itself; those caps belong to the caller (Play
matchmaking in Phase 4, Room management in Phase 5). Keeping the cap
logic out of the registry keeps it reusable by both flows without a
conditional branching on "which flow am I."

`role` is `None` for a registered spectator -- mirroring the same
None-means-not-a-seated-player convention already used by
`GameSession.role_for` and `RoomManager.join_room`'s return value, so a
caller doesn't need a separate enum member just to route disconnect
cleanup for spectators through this same map."""
from __future__ import annotations

from typing import Dict, Optional, Tuple

from kungfu_chess.server.session.game_session import GameSession, PlayerRole


class ConnectionRegistry:
    def __init__(self) -> None:
        self._entries: Dict[object, Tuple[GameSession, Optional[PlayerRole]]] = {}

    def register(self, connection: object, session: GameSession,
                 role: Optional[PlayerRole]) -> None:
        self._entries[connection] = (session, role)

    def unregister(self, connection: object) -> None:
        self._entries.pop(connection, None)

    def lookup(self, connection: object) -> Optional[Tuple[GameSession, Optional[PlayerRole]]]:
        return self._entries.get(connection)

    def __contains__(self, connection: object) -> bool:
        return connection in self._entries

    def __len__(self) -> int:
        return len(self._entries)
