from __future__ import annotations
from typing import List, Optional, Protocol, Tuple

from kungfu_chess.config import GameConfig
from kungfu_chess.model.board import BoardInterface
from kungfu_chess.model.position import Position
from kungfu_chess.model.piece import Piece
from kungfu_chess.realtime.motion import PendingMove, SettlementEvent

__all__ = ["CollisionHandler", "PromotionResolver"]


class PromotionResolver(Protocol):
    """Structural type for resolving a piece's post-arrival transformation (in practice RuleEngine)."""

    def resolve_arrival_piece(self, piece: Piece, dst: Position,
                               board: BoardInterface) -> Piece:
        ...


class CollisionHandler:
    """Decides who blocks or captures whom when a motion settles; called by GameEngine.settle() for each due motion.
    Stateless: board and pending motions are passed explicitly rather than read from an Arbiter."""

    # ---- square-by-square arrival resolution ----------------------------
    def resolve_move(self, m: PendingMove, board: BoardInterface,
                      promotion_resolver: PromotionResolver,
                      pending_motions: List[PendingMove]) -> Optional[SettlementEvent]:
        """Walks the move's path against current board occupancy, mutates the board, and returns the outcome.
        Returns None if the piece was already removed from src by an earlier-settling motion this pass."""
        if board.get_piece_at(m.src) != m.piece:
            return None

        landing_square, captured_piece = self._advance_through_path(m, board, pending_motions)

        settled_piece = m.piece
        if landing_square == m.dst:
            # Promotion only fires on reaching the originally requested destination.
            settled_piece = promotion_resolver.resolve_arrival_piece(m.piece, m.dst, board)

        board.set_piece_at(landing_square, settled_piece)
        if landing_square != m.src:
            board.set_piece_at(m.src, None)

        return SettlementEvent(
            src=m.src, dst=landing_square, piece=settled_piece,
            captured_piece=captured_piece, move_type=GameConfig.MOTION_STATE_MOVE,
            requested_dst=m.dst,
        )

    # ---- jump / hover landing ---------------------------------------
    def resolve_jump_landing(self, m: PendingMove, board: BoardInterface,
                              pending_motions: List[PendingMove]) -> Optional[SettlementEvent]:
        """A hover lands back on its takeoff square (m.src, never cleared while airborne). Same piece there:
        no-op. Same-color piece there: unreachable in normal play, reported as reverted=True with no mutation.
        Different-color piece: captured, jumper takes the square."""
        occupant = board.get_piece_at(m.src)

        if occupant == m.piece:
            return SettlementEvent(
                src=m.src, dst=m.src, piece=m.piece,
                captured_piece=None, move_type=GameConfig.MOTION_STATE_JUMP,
            )

        if occupant is not None and occupant.color == m.piece.color:
            # Defensive fallback only; no mutation, no capture.
            return SettlementEvent(
                src=m.src, dst=m.src, piece=m.piece,
                captured_piece=None, move_type=GameConfig.MOTION_STATE_JUMP, reverted=True,
            )

        board.set_piece_at(m.src, m.piece)
        return SettlementEvent(
            src=m.src, dst=m.src, piece=m.piece,
            captured_piece=occupant, move_type=GameConfig.MOTION_STATE_JUMP,
        )

    # -- rendering support: live (non-authoritative) landing preview ------
    def preview_landing_square(self, m: PendingMove, board: BoardInterface,
                                pending_motions: List[PendingMove]) -> Position:
        """Read-only preview of where `m` would land; never mutates the board. Lets a sliding piece's on-screen
        position track its would-be landing square instead of the requested destination."""
        if m.move_type != GameConfig.MOTION_STATE_MOVE or m.dst is None:
            return m.src
        landing_square, _captured_piece = self._advance_through_path(m, board, pending_motions)
        return landing_square

    def _advance_through_path(self, m: PendingMove, board: BoardInterface,
                               pending_motions: List[PendingMove]
                               ) -> Tuple[Position, Optional[Piece]]:
        """Walks `m.path` against the current board, already mutated by earlier-settling motions this pass --
        this ordering is what makes "later arrival captures/blocks earlier occupant" work without timestamp
        comparisons. A square airborne as of `m.complete_time` is treated as vacant to walk through (not a
        collision target until it lands). Returns `(landing_square, captured_piece)`: stops and captures on the
        first different-color occupant; stops one square short of the first same-color occupant (via
        `_respect_hover_claim`); else lands on `m.dst`."""
        previous = m.src
        for square in m.path:
            if self._airborne_piece_at(square, m.complete_time, pending_motions) is not None:
                previous = square
                continue
            occupant = board.get_piece_at(square)
            if occupant is None:
                previous = square
                continue
            if occupant.color != m.piece.color:
                return square, occupant
            return self._respect_hover_claim(m, previous, pending_motions), None
        return self._respect_hover_claim(m, m.dst, pending_motions), None

    def _respect_hover_claim(self, m: PendingMove, landing_square: Position,
                              pending_motions: List[PendingMove]) -> Position:
        """A friendly piece may pass through a hovering square but never land on one; backs up one square in
        the path (repeating if needed, though a second step should be unreachable in practice)."""
        while True:
            hoverer = self._airborne_piece_at(landing_square, m.complete_time, pending_motions)
            if hoverer is None or hoverer.color != m.piece.color:
                return landing_square
            if landing_square == m.src:
                return m.src  # nowhere further back to retreat to
            index = m.path.index(landing_square)
            landing_square = m.path[index - 1] if index > 0 else m.src

    def _airborne_piece_at(self, square: Position, as_of_time: int,
                            pending_motions: List[PendingMove]) -> Optional[Piece]:
        """The piece currently mid-hover over `square` as of `as_of_time`, or None. Like
        `RealTimeArbiter.is_active_airborne_at` but also returns *who* is hovering."""
        for pending in pending_motions:
            if (pending.move_type == GameConfig.MOTION_STATE_JUMP
                    and pending.src == square and pending.complete_time >= as_of_time):
                return pending.piece
        return None
