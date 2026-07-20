"""Translates `GameEngine`'s engine-level settlement/lifecycle
callbacks into the UI's plain-value Domain Events and publishes them
onto a given `EventBus`. Shared by `ui/composition.py` (local
single-process wiring) and `server/app.py` (networked wiring) so this
translation lives in exactly one place (DRY) -- callers still control
who else subscribes, and never let the engine's live objects leak onto
the bus."""
from __future__ import annotations

from kungfu_chess.engine.game_engine import GameEngine
from kungfu_chess.realtime.settlement_data import SettlementDataInterface
from kungfu_chess.ui.events.event_bus import EventBus
from kungfu_chess.ui.events.events import GameEndedEvent, JumpResolvedEvent, MoveResolvedEvent


def wire_engine_domain_events(engine: GameEngine, event_bus: EventBus) -> None:
    """Subscribes translated `MoveResolvedEvent`/`JumpResolvedEvent`/
    `GameEndedEvent` onto `event_bus` from `engine`'s settlement/
    lifecycle callbacks. Does not publish `GameStartedEvent` -- callers
    publish that once, at whatever moment "the game becomes playable"
    means for them (immediately after construction locally; once both
    players have joined, over the network)."""

    def on_settlement(event: SettlementDataInterface) -> None:
        if event.move_type == 'jump':
            event_bus.publish(JumpResolvedEvent(
                piece_color=event.piece_color,
                piece_kind=event.piece_kind,
                row=event.dst[0], col=event.dst[1],
                captured_piece_kind=event.captured_piece_kind,
            ))
            return

        event_bus.publish(MoveResolvedEvent(
            piece_color=event.piece_color,
            piece_kind=event.piece_kind,
            src_row=event.src[0], src_col=event.src[1],
            dst_row=event.dst[0], dst_col=event.dst[1],
            captured_piece_kind=event.captured_piece_kind,
            requested_dst_row=event.requested_dst[0] if event.requested_dst else None,
            requested_dst_col=event.requested_dst[1] if event.requested_dst else None,
        ))

    engine.add_settlement_listener(on_settlement)
    engine.add_game_ended_listener(
        lambda winner, clock_ms: event_bus.publish(
            GameEndedEvent(winner=winner, timestamp_ms=clock_ms)))
