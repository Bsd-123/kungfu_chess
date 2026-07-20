"""Watchdog for an unexpected socket close (Decision 7): frees the
seat, starts a 20-second reconnect grace timer stored on the
`GameSession` itself (see `GameSession.mark_disconnected`), and sends a
*single* `player_disconnected` message carrying the total
`grace_period_ms` -- never a repeating per-second tick stream; the
client renders its own local countdown from that one value. The
`GameEngine` is never paused or destroyed while the timer runs -- it
keeps ticking normally, exactly as `master_work_plan.md` requires.

If the timer elapses with no reconnect, the forfeit is expressed as an
ordinary `GameEndedEvent` on the session's own domain bus -- the same
event a real win-condition win publishes -- so Phase 4's
`RatingUpdateService` needs no separate forfeit-specific code path."""
from __future__ import annotations

import asyncio
from typing import Optional

from kungfu_chess.server.config import NetworkConfig
from kungfu_chess.server.messaging.application_message_bus import ApplicationMessageBus
from kungfu_chess.server.messaging.transport_events import (
    PlayerDisconnectedEvent, PlayerForfeitedEvent,
)
from kungfu_chess.server.protocol import make_envelope
from kungfu_chess.server.session.game_session import GameSession, PlayerRole
from kungfu_chess.ui.events.events import GameEndedEvent


class DisconnectMonitor:
    def __init__(self, network_config: Optional[NetworkConfig] = None,
                 grace_period_ms: int = 20_000,
                 message_bus: Optional[ApplicationMessageBus] = None):
        self._network_config = network_config or NetworkConfig()
        self._grace_period_ms = grace_period_ms
        self._message_bus = message_bus

    def handle_disconnect(self, session: GameSession, connection: object) -> Optional[PlayerRole]:
        """Call this the moment `connection`'s socket closes for
        `session`. Returns the now-pending-reconnect role, or None if
        `connection` wasn't a seated player -- a spectator disconnecting
        must never start a forfeit countdown (Phase 5 risk), and this
        early return is exactly how that's enforced: `role_for` only
        ever resolves seated players."""
        role = session.role_for(connection)
        if role is None:
            return None

        session.remove_player(connection)
        session.mark_disconnected(
            role, self._grace_period_ms, on_expire=lambda: self._forfeit(session, role))

        envelope = make_envelope(
            "player_disconnected",
            {"role": role.value, "grace_period_ms": self._grace_period_ms},
            self._network_config)
        asyncio.ensure_future(session.broadcast(envelope))

        if self._message_bus is not None:
            user_id = session.white_user_id if role is PlayerRole.WHITE else session.black_user_id
            self._message_bus.publish(PlayerDisconnectedEvent(
                game_id=session.game_id, user_id=user_id, grace_period_ms=self._grace_period_ms))

        return role

    def _forfeit(self, session: GameSession, role: PlayerRole) -> None:
        winner_color = 'b' if role is PlayerRole.WHITE else 'w'
        session.event_bus.publish(GameEndedEvent(winner=winner_color, timestamp_ms=session.engine.clock_ms))

        if self._message_bus is not None:
            user_id = session.white_user_id if role is PlayerRole.WHITE else session.black_user_id
            self._message_bus.publish(PlayerForfeitedEvent(game_id=session.game_id, user_id=user_id))
