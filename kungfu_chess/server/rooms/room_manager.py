"""Room lifecycle (Decisions 8/9/16): create/join/leave, reusing the
same `GameSession` primitive Phase 2 already built rather than
inventing a parallel connection model -- this module holds only the
room_id -> GameSession mapping. `GameSession` construction is injected
(mirrors `QueueManager`'s `create_session` in Phase 4), so this module
stays decoupled from engine/event-bus wiring specifics; whoever
composes the real server supplies that factory.

Room ID collision handling is atomic by construction (Decision 1:
single-threaded event loop, no `await` between generating the id and
reserving it in `_rooms`), and teardown is immediate rather than
lazy/garbage-collected (Decision 9): the moment `leave_room` finds both
player slots empty, the room is torn down and its id released for
reuse in the same call."""
from __future__ import annotations

from typing import Callable, Dict, Optional

from kungfu_chess.server.config import RoomConfig
from kungfu_chess.server.protocol import make_envelope
from kungfu_chess.server.rooms.room_id_generator import generate_room_id
from kungfu_chess.server.session.game_session import GameSession, PlayerRole

CreateSession = Callable[[str], GameSession]


class RoomNotFoundError(Exception):
    def __init__(self, room_id: str):
        super().__init__(f"no active room with id {room_id!r}")
        self.room_id = room_id


class RoomManager:
    def __init__(self, create_session: CreateSession, room_config: Optional[RoomConfig] = None):
        self._create_session = create_session
        self._room_config = room_config or RoomConfig()
        self._rooms: Dict[str, GameSession] = {}

    def create_room(self, connection: object, user_id: Optional[int] = None) -> str:
        """The creator is seated as White immediately (per the
        directive: creating a room generates and displays its ID for
        the creator right away, not after a second joiner appears)."""
        room_id = generate_room_id(self._rooms.keys(), self._room_config)
        session = self._create_session(room_id)
        session.add_player(connection, user_id)
        self._rooms[room_id] = session
        return room_id

    def get_room(self, room_id: str) -> Optional[GameSession]:
        return self._rooms.get(room_id)

    def list_sessions(self):
        """All currently active rooms' GameSessions -- used by
        ReconnectHandler to scan Room games alongside Play games for a
        pending disconnect matching a reconnecting user."""
        return list(self._rooms.values())

    def join_room(self, room_id: str, connection: object,
                   user_id: Optional[int] = None) -> Optional[PlayerRole]:
        """Second joiner becomes Black; every joiner after that is a
        spectator (up to the cap -- `SpectatorCapError` propagates
        uncaught for the caller to translate into a "room full"
        message). Returns the `PlayerRole` seated, or `None` to mean
        "seated as a spectator", mirroring `GameSession.role_for`'s
        existing None-means-not-a-player convention."""
        session = self._rooms.get(room_id)
        if session is None:
            raise RoomNotFoundError(room_id)
        if not session.is_full():
            return session.add_player(connection, user_id)
        session.add_spectator(connection)
        return None

    async def leave_room(self, room_id: str, connection: object) -> None:
        """A spectator leaving just frees its slot. A player leaving
        frees theirs and then checks Decision 9's teardown condition;
        if both slots are now empty, any remaining spectators are told
        the room closed, the tick loop is stopped, and the room id is
        released back to the pool -- all before returning, so a
        `create_room` call immediately afterward can reuse the id."""
        session = self._rooms.get(room_id)
        if session is None:
            return

        if session.is_spectator(connection):
            session.remove_spectator(connection)
            return

        session.remove_player(connection)
        if session.connections:
            return

        if session.spectators:
            envelope = make_envelope("room_closed", {"room_id": room_id}, session.network_config)
            await session.broadcast(envelope)
        session.stop()
        del self._rooms[room_id]
