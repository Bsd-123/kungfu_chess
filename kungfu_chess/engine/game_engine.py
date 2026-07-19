from __future__ import annotations

from typing import Callable, List, Optional

from kungfu_chess.model.board import BoardInterface
from kungfu_chess.model.position import Position
from kungfu_chess.io.board_printer import BoardTextView
from kungfu_chess.config import GameConfig
from kungfu_chess.model.game_state import GameState
from kungfu_chess.rules.rule_engine import RuleEngine
from kungfu_chess.rules.win_condition import WinConditionRule, king_capture_win_condition
from kungfu_chess.engine.move_result import MoveResult
from kungfu_chess.engine.move_reasons import MoveReasons
from kungfu_chess.engine.movement_math import squares_traveled
from kungfu_chess.engine.motion_gate import MotionGate
from kungfu_chess.engine.legal_destinations import LegalDestinationsCalculator
from kungfu_chess.engine.settlement_notifier import SettlementNotifier
from kungfu_chess.engine.snapshot_builder import SnapshotBuilder
from kungfu_chess.realtime.collision_handler import CollisionHandler
from kungfu_chess.realtime.motion import SettlementEvent
from kungfu_chess.realtime.settlement_data import SettlementDataInterface
from kungfu_chess.view.game_snapshot import GameSnapshot


class GameEngine:
    """Facade for all game actions (request_move/request_jump/advance_clock/settle/snapshot);
    callers never talk to the RuleEngine, board, or RealTimeArbiter directly.

    Settlement is atomic -- a Motion is either not-yet-arrived (board unchanged) or fully
    applied, never in-between. Whether a settled capture ends the game is delegated to an
    injected `WinConditionRule` (defaults to king-capture)."""

    def __init__(self, state: GameState, rule_engine: RuleEngine, config: GameConfig,
                 win_condition: Optional[WinConditionRule] = None,
                 collision_handler: Optional[CollisionHandler] = None):
        self._state = state
        self._rule_engine = rule_engine
        self._config = config
        self._win_condition = win_condition or king_capture_win_condition()
        # Stateless; defaults to a plain instance.
        self._collision_handler = collision_handler or CollisionHandler()

        self._motion_gate = MotionGate(self._state)
        self._legal_destinations = LegalDestinationsCalculator(
            self._state, self._rule_engine, self._motion_gate)
        self._settlement_notifier = SettlementNotifier()
        self._snapshot_builder = SnapshotBuilder(self._state, self._config, self._collision_handler)

    # -- read-only facade surface used by commands -----------------
    @property
    def board(self) -> BoardInterface:
        return self._state.board

    @property
    def clock_ms(self) -> int:
        return self._state.clock_ms

    @property
    def selected(self) -> Optional[Position]:
        return self._state.selected

    @selected.setter
    def selected(self, value: Optional[Position]) -> None:
        self._state.selected = value

    @property
    def output_chunks(self) -> List[str]:
        return self._state.output_chunks

    @property
    def game_over(self) -> bool:
        return self._state.game_over

    def is_piece_busy(self, pos: Position) -> bool:
        return self._state.is_piece_busy(pos)

    def is_target_busy(self, pos: Position) -> bool:
        return self._state.is_target_busy(pos)

    def is_cooling_down(self, pos: Position) -> bool:
        return self._state.is_cooling_down(pos)

    # -- request_move: application-service entry point --
    def request_move(self, source: Position, destination: Position) -> MoveResult:
        """Checks MotionGate eligibility, then whether `destination` is already targeted
        by another motion, then RuleEngine validation; on success schedules the Motion.
        `bool(result)` reflects acceptance."""
        blocked = self._motion_gate.blocked_reason(source)
        if blocked is not None:
            return MoveResult(False, blocked)

        if self._state.is_target_busy(destination):
            return MoveResult(False, MoveReasons.MOTION_IN_PROGRESS)

        piece = self._state.board.get_piece_at(source)

        validation = self._rule_engine.validate_move(
            self._state.board, piece, source, destination)
        if not validation.is_valid:
            return MoveResult(False, validation.reason)

        duration = self._move_duration_ms(piece, source, destination)
        cooldown = self._config.cooldown_for(piece.type)
        self._state.schedule_move(source, destination, piece, duration, cooldown)
        return MoveResult(True, MoveReasons.OK)

    def _move_duration_ms(self, piece, source: Position, destination: Position) -> int:
        """duration = squares_traveled * per-square ms, from `GameConfig.move_duration_for`
        (defaults to `default_move_duration_ms`)."""
        per_square = self._config.move_duration_for(piece.type)
        return squares_traveled(source, destination) * per_square

    # -- movement-range highlight feature: read-only legality probe -----
    def legal_destinations(self, source: Position) -> List[Position]:
        """Delegates to `LegalDestinationsCalculator`."""
        return self._legal_destinations.compute(source)

    def request_jump(self, position: Position) -> bool:
        """Jumps skip RuleEngine validation and the target-busy check, but still go
        through the same `MotionGate` as `request_move`."""
        if self._motion_gate.blocked_reason(position) is not None:
            return False

        piece = self._state.board.get_piece_at(position)
        if piece is None:
            return False

        cooldown = self._config.jump_cooldown_for(piece.type)
        self._state.schedule_jump(position, piece, self._config.jump_duration_ms, cooldown)
        return True

    # -- optional observer hook; backward-compatible with zero listeners --
    def add_settlement_listener(self, listener: Callable[[SettlementDataInterface], None]) -> None:
        """Registers `listener`, called once per settled motion during `settle()`.
        Typed against `SettlementDataInterface` (read-only), not the internal
        `SettlementEvent`. Jumps land back on their own source square, so they never
        produce a settlement."""
        self._settlement_notifier.add_listener(listener)

    # -- virtual-time advancement and atomic settlement --
    def advance_clock(self, ms: int) -> None:
        self._state.advance_clock(ms)
        self.settle()

    def settle(self) -> None:
        """Resolves each due motion via `CollisionHandler`, then applies the injected
        `WinConditionRule` -- GameEngine is the only place a settled capture is checked
        for a win -- and notifies listeners before clearing expired arbiter state."""
        board = self._state.board
        due_motions = self._state.arbiter.next_due_motions(self._state.clock_ms)
        pending_motions = self._state.arbiter.pending_moves

        for m in due_motions:
            if m.move_type == GameConfig.MOTION_STATE_MOVE:
                event = self._collision_handler.resolve_move(
                    m, board, self._rule_engine, pending_motions)
            else:
                event = self._collision_handler.resolve_jump_landing(
                    m, board, pending_motions)
            if event is None:
                continue

            self._state.arbiter.start_cooldown_for(m, event.dst)
            self._apply_win_condition(event)
            self._settlement_notifier.notify(event)

        self._state.arbiter.clear_expired(self._state.clock_ms)

    def _apply_win_condition(self, event: SettlementEvent) -> None:
        """`event.piece` is the capturing piece, not the captured one; set atomically via
        `GameState.mark_game_over` so `game_over`/`winner_color` can't drift apart."""
        if (event.captured_piece is not None
                and self._win_condition.check(event.piece, event.captured_piece)):
            self._state.mark_game_over(event.piece.color)

    def render(self) -> str:
        return BoardTextView.render_board(self._state.board)

    # -- read-only snapshot for the rendering boundary --
    def snapshot(self) -> GameSnapshot:
        """Delegates to `SnapshotBuilder`."""
        return self._snapshot_builder.build()
