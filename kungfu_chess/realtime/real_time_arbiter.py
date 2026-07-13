from __future__ import annotations
from typing import List, Optional, Protocol

from kungfu_chess.model.board import BoardInterface
from kungfu_chess.model.position import Position
from kungfu_chess.model.piece import Piece
from kungfu_chess.realtime.motion import MoveScheduler, PendingMove, SettlementEvent

__all__ = ["RealTimeArbiter", "PendingMove", "SettlementEvent", "MoveScheduler"]


class PromotionResolver(Protocol):
    """Structural type for whatever collaborator can resolve a piece's
    post-arrival transformation -- in practice RuleEngine. Declared here
    only so the Arbiter can type-hint against a capability instead of
    importing RuleEngine and coupling timing/scheduling to validation."""

    def resolve_arrival_piece(self, piece: Piece, dst: Position,
                               board: BoardInterface) -> Piece:
        ...


class RealTimeArbiter:
    """Phase 6 - Real-Time Arbiter: the single component responsible for
    every parallel-action / time-synchronization concern:

      - scheduling new motions (moves and jumps) with a duration that is
        computed by the caller (GameEngine owns "how long does this
        particular move take" -- see Spec §10's N x 1000ms rule; the
        Arbiter just faithfully counts down whatever duration it's given)
      - answering busy / target-busy / airborne queries, used up front
        to reject conflicting requests before they're ever scheduled
        (Rule 8, including the target-cell-conflict check)
      - resolving every motion whose travel time has elapsed as of a
        given clock reading, in complete_time order, applying board
        mutations atomically (Rule 10) and reporting what happened

    It stays a pure timing/scheduling service: promotion is delegated to
    an injected PromotionResolver (structurally, RuleEngine) rather than
    imported, and it has no notion of "game over" -- it just reports
    SettlementEvents and leaves policy decisions like Rule 11's
    king-capture trigger to GameEngine. This keeps validation (Rule 7),
    orchestration/policy (Rule 8/11) and time-sync (this class) each in
    exactly one place."""

    def __init__(self, scheduler: Optional[MoveScheduler] = None):
        self._scheduler = scheduler or MoveScheduler()

    # -- conflict queries, consulted before scheduling anything --------
    def is_piece_busy(self, src: Position, clock_ms: int) -> bool:
        return self._scheduler.is_piece_busy(src, clock_ms)

    def is_target_busy(self, dst: Position, clock_ms: int) -> bool:
        return self._scheduler.is_target_busy(dst, clock_ms)

    def is_active_airborne_at(self, cell: Position, clock_ms: int) -> bool:
        return self._scheduler.is_active_airborne_at(cell, clock_ms)

    # -- scheduling ------------------------------------------------------
    def schedule_move(self, src: Position, dst: Position, piece: Piece,
                       clock_ms: int, duration_ms: int) -> None:
        self._scheduler.schedule(PendingMove(
            move_type='move',
            complete_time=clock_ms + duration_ms,
            src=src, dst=dst, piece=piece,
        ))

    def schedule_jump(self, src: Position, piece: Piece,
                       clock_ms: int, duration_ms: int) -> None:
        self._scheduler.schedule(PendingMove(
            move_type='jump',
            complete_time=clock_ms + duration_ms,
            src=src, piece=piece,
        ))

    @property
    def pending_moves(self) -> List[PendingMove]:
        return self._scheduler.pending_moves

    # -- time-synchronized resolution ------------------------------------
    def resolve_due(self, clock_ms: int, board: BoardInterface,
                     promotion_resolver: PromotionResolver) -> List[SettlementEvent]:
        """Settle every motion due as of clock_ms, in complete_time order.
        Each settlement is atomic (Rule 10): board mutation for a given
        Motion happens in one uninterrupted step, there is no partial
        state observable between src-clear and dst-write."""
        events: List[SettlementEvent] = []

        for m in self._scheduler.due_moves(clock_ms):
            # Defensive check: only apply if the moving piece is still
            # at its source square.
            if board.get_piece_at(m.src) != m.piece:
                continue

            if self._scheduler.is_active_airborne_at(m.dst, clock_ms):
                # An airborne piece occupies the destination: the
                # arriving piece is swallowed instead of landing.
                board.set_piece_at(m.src, None)
                continue

            captured_piece = board.get_piece_at(m.dst)
            settled_piece = promotion_resolver.resolve_arrival_piece(m.piece, m.dst, board)
            board.set_piece_at(m.dst, settled_piece)
            board.set_piece_at(m.src, None)

            events.append(SettlementEvent(
                src=m.src, dst=m.dst, piece=settled_piece,
                captured_piece=captured_piece,
            ))

        self._scheduler.clear_expired(clock_ms)
        return events
