from __future__ import annotations

from typing import Callable, List, Optional

from kungfu_chess.model.board import BoardInterface
from kungfu_chess.model.position import Position
from kungfu_chess.io.board_printer import BoardTextView
from kungfu_chess.config import GameConfig
from kungfu_chess.model.game_state import GameState
from kungfu_chess.rules.rule_engine import RuleEngine
from kungfu_chess.engine.move_result import MoveResult
from kungfu_chess.realtime.motion import PendingMove, SettlementEvent
from kungfu_chess.view.game_snapshot import GameSnapshot, PieceSnapshot


def _squares_traveled(src: Position, dst: Position) -> int:
    """Chebyshev distance in cells: the number of discrete grid steps a
    sliding/king-like move covers. Spec section 10: 'Moving N squares takes
    N x 1000ms' -- N is this value. Using max(|dr|, |dc|) rather than
    Manhattan distance is what makes a 3-square diagonal bishop move
    come out to 3 (one step per diagonal cell), matching the spec's own
    bishop example, rather than double-counting row+col."""
    dr = abs(dst[0] - src[0])
    dc = abs(dst[1] - src[1])
    return max(dr, dc, 1)


class GameEngine:
    """Central Orchestration Layer (Rule 8): the single facade through
    which every game action is requested. Callers (commands/Controller)
    never talk to the RuleEngine, the board, or the RealTimeArbiter
    directly -- they go through `request_move` / `request_jump` /
    `advance_clock` / `settle` / `snapshot`.

    Validation (RuleEngine) is strictly decoupled from action (Rule 5):
    `request_move` only ever *asks* the RuleEngine whether a move is
    legal, it never decides legality itself. Scheduling is likewise
    decoupled from resolution: GameEngine hands motions to the
    RealTimeArbiter and only reacts to the SettlementEvents it reports
    back when a motion resolves.

    Settlement is atomic (Rule 10): a Motion has no observable
    in-between state. A pending move either hasn't arrived yet (the
    board still shows the old state) or it has arrived and the board
    is updated immediately -- there is no partial/intermediate render.
    """

    def __init__(self, state: GameState, rule_engine: RuleEngine, config: GameConfig):
        self._state = state
        self._rule_engine = rule_engine
        self._config = config
        self._settlement_listeners: List[Callable[[SettlementEvent], None]] = []

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

    # -- Rule 8: request_move as the application-service entry point --
    def request_move(self, source: Position, destination: Position) -> MoveResult:
        """Sequential checks, in the exact order mandated by Rule 8/section 9:
        1. Is the game already over?                  -> "game_over"
        2. Is there already an active motion involving
           this piece as its source (busy), OR another
           motion already converging on this exact
           destination cell (target-busy)?             -> "motion_in_progress"
        3. Does the RuleEngine validate and approve
           the move?                                   -> its own reason
        4. If approved: schedule the Motion with the
           RealTimeArbiter, with a duration computed
           from squares traveled (Spec section 10).            -> "ok"
        Returns a MoveResult; `bool(result)` still works exactly like
        the old plain-bool return for any caller that doesn't care about
        the reason."""
        if self._state.game_over:
            return MoveResult(False, "game_over")

        if self._state.is_piece_busy(source) or self._state.is_target_busy(destination):
            return MoveResult(False, "motion_in_progress")

        piece = self._state.board.get_piece_at(source)

        validation = self._rule_engine.validate_move(
            self._state.board, piece, source, destination)
        if not validation.is_valid:
            return MoveResult(False, validation.reason)

        duration = self._move_duration_ms(piece, source, destination)
        self._state.schedule_move(source, destination, piece, duration)
        return MoveResult(True, "ok")

    def _move_duration_ms(self, piece, source: Position, destination: Position) -> int:
        """duration = squares_traveled * per_square_ms (Spec section 10). The
        per-square rate defaults to `default_move_duration_ms` (1000ms,
        i.e. PIECE_SPEED = 1 cell/sec) and can still be overridden per
        piece type via `move_duration_ms`, e.g. for a custom variant
        where knights move faster per square than pawns."""
        per_square = self._config.move_duration_ms.get(
            piece.type, self._config.default_move_duration_ms)
        return _squares_traveled(source, destination) * per_square

    def request_jump(self, position: Position) -> bool:
        """Jumps bypass RuleEngine validation (there is no destination
        to validate against) and are exempt from the target-busy check
        (an airborne piece isn't converging on a shared destination
        square the way a move is) but still respect the game-over and
        busy-piece checks, mirroring the same ordering as request_move."""
        if self._state.game_over:
            return False

        if self._state.is_piece_busy(position):
            return False

        piece = self._state.board.get_piece_at(position)
        if piece is None:
            return False

        self._state.schedule_jump(position, piece, self._config.jump_duration_ms)
        return True

    # -- Phase 5 (final_plan_verified.md section 4A): optional observer
    # hook. Small, additive, backward-compatible -- an engine with zero
    # listeners registered behaves exactly as before this was added.
    def add_settlement_listener(self, listener: Callable[[SettlementEvent], None]) -> None:
        """Registers `listener` to be called once per SettlementEvent as
        `settle()` resolves it -- this is how the UI layer (Phase 5's
        EventBus/observers) learns "a capture just happened" without
        GameEngine importing anything UI-side, and without exposing the
        RealTimeArbiter itself. Ordering matches section 1's table:
        only settled *moves* ever produce a SettlementEvent; jumps never
        do (they land back on their own src square, so there's nothing
        to settle)."""
        self._settlement_listeners.append(listener)

    # -- Rule 9/10: virtual-time advancement and atomic settlement ----
    def advance_clock(self, ms: int) -> None:
        self._state.clock_ms += ms
        self.settle()

    def settle(self) -> None:
        """Ask the RealTimeArbiter to resolve every Motion whose travel
        duration has elapsed, then apply the one piece of chess-specific
        policy that lives at this layer: Rule 11's King-capture
        game-over trigger. The Arbiter itself has no notion of what a
        King is -- it only reports SettlementEvents; GameEngine is the
        only place that turns a captured King into game_over."""
        events = self._state.arbiter.resolve_due(
            self._state.clock_ms, self._state.board, self._rule_engine)

        for event in events:
            if event.captured_piece is not None and event.captured_piece.type == 'K':
                self._state.game_over = True
            for listener in self._settlement_listeners:
                listener(event)

    def render(self) -> str:
        return BoardTextView.render_board(self._state.board)

    # -- Phase 4 (final_plan_verified.md section 7.5): derive per-piece
    # animation state from the arbiter's own pending-motions list, since
    # `piece.state` itself is dead (ArrayBoard.get_piece_at reconstructs a
    # fresh Piece via Piece.parse on every call, which never sets state) --
    def _pending_motion_at(self, pos: Position) -> Optional[PendingMove]:
        return next((m for m in self._state.arbiter.pending_moves if m.src == pos), None)

    # -- Spec section 12/20: read-only snapshot for the rendering boundary ---
    def snapshot(self) -> GameSnapshot:
        """Builds the read-only GameSnapshot DTO handed to a renderer.
        Deliberately does not expose live Board/Piece objects (Spec section 12:
        "live domain objects increase coupling and create opportunities
        for accidental mutation from the view layer"). Only logical
        (settled) positions are reflected here; a renderer that wants to
        interpolate an in-flight motion does so using `motion_progress`/
        `dst_pixel_x`/`dst_pixel_y` below, not by reaching past this DTO."""
        board = self._state.board
        cell = self._config.cell_pixel_size
        pieces: List[PieceSnapshot] = []
        for row in range(board.nrows):
            for col in range(board.ncols):
                piece = board.get_piece_at(Position(row, col))
                if piece is None:
                    continue

                motion = self._pending_motion_at(Position(row, col))
                if motion is None:
                    state, progress = "idle", 1.0
                    dst_x, dst_y = None, None
                else:
                    state = motion.move_type  # "move" or "jump"
                    span = motion.complete_time - motion.start_time
                    progress = 1.0 if span <= 0 else min(1.0, max(0.0,
                        (self._state.clock_ms - motion.start_time) / span))
                    if motion.move_type == "move" and motion.dst is not None:
                        dst_x = motion.dst[1] * cell
                        dst_y = motion.dst[0] * cell
                    else:
                        dst_x, dst_y = None, None

                pieces.append(PieceSnapshot(
                    kind=piece.kind,
                    color=piece.color,
                    pixel_x=col * cell,
                    pixel_y=row * cell,
                    state=state,
                    motion_progress=progress,
                    dst_pixel_x=dst_x,
                    dst_pixel_y=dst_y,
                ))

        return GameSnapshot(
            board_width=board.ncols,
            board_height=board.nrows,
            pieces=pieces,
            selected=self._state.selected,
            game_over=self._state.game_over,
        )
