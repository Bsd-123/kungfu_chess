from __future__ import annotations
import itertools
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from kungfu_chess.model.position import Position
from kungfu_chess.model.piece import Piece


@dataclass
class PendingMove:
    """Value object representing a queued move or jump. Encapsulates the
    field names so no other class needs to know about dict keys, and
    holds the moving Piece as a value object rather than a raw token.

    `start_time` (Phase 4, final_plan_verified.md section 7.5): the
    clock_ms reading at scheduling time. Without it, `0.0 -> 1.0`
    animation progress can't be derived -- only `complete_time` (when a
    motion finishes) was stored before, which only tells you how much
    time is left, not what fraction of the total duration has elapsed.
    Defaults to 0 so this stays backward-compatible with any existing
    caller that constructs a PendingMove positionally without it."""
    move_type: str  # 'move' or 'jump'
    complete_time: int
    src: Position
    piece: Piece
    dst: Optional[Position] = None
    start_time: int = 0

    # Ordered squares from (excluding) src to (including) dst, as
    # produced by `BoardInterface.get_path` at scheduling time. Only
    # meaningful for move_type == 'move' (jumps land back on src, so
    # they have nothing to walk); defaults to an empty list so any
    # existing caller that still constructs a PendingMove positionally
    # keeps working unchanged. Precomputing this once at schedule time
    # (rather than re-deriving geometry inside the Arbiter) keeps
    # RealTimeArbiter a pure timing/collision-resolution service that
    # never has to know piece-shape rules -- it only ever walks a list
    # of squares it was handed.
    path: List[Position] = field(default_factory=list)

    # Monotonically increasing scheduling order, assigned by
    # `MoveScheduler.schedule` -- the tiebreaker for two motions whose
    # complete_time lands on the exact same tick (mirrors the integration
    # plan's heap-tiebreaker idea: first-scheduled settles first).
    # Defaults to 0 so a positionally-constructed PendingMove (tests,
    # existing callers) is unaffected; `MoveScheduler.schedule` always
    # overwrites it with the real sequence number.
    seq: int = 0

    # Post-move cooldown feature: how long, in ms, the landing square
    # should refuse a new motion once *this* motion settles. GameEngine
    # computes this the same way it computes `duration_ms` (per piece
    # type, via GameConfig) and hands it in at scheduling time -- the
    # Arbiter stays a pure timing/collision service that never looks up
    # a piece type itself, it just faithfully starts a cooldown of
    # whatever length it's told once this motion resolves. Defaults to
    # 0 (no cooldown) so any existing caller/test that builds a
    # PendingMove positionally is unaffected.
    cooldown_ms: int = 0


@dataclass
class SettlementEvent:
    """Reports what happened when a single Motion settled. Returned from
    RealTimeArbiter.resolve_due() so GameEngine can apply chess-specific
    *policy* (Rule 11's king-capture -> game_over) without the Arbiter
    itself knowing anything about what a King is.

    `dst` is always the square the piece actually ended up on -- for a
    move truncated mid-path by a same-color near-miss, or stopped short
    by capturing an enemy before reaching its requested destination,
    that's the real landing square, not the one originally requested.
    Every existing consumer (rendering, king-capture check, move log)
    already just reads `event.dst` as "where it ended up", so this needs
    no downstream changes.

    `move_type` ('move' or 'jump') lets a listener distinguish the two
    without importing PendingMove; defaults to 'move' so any existing
    caller/test that builds a SettlementEvent positionally is unaffected.
    Added so hover/jump landings -- previously silent, per the old
    "jumps never produce a SettlementEvent" design -- can flow through
    the exact same listener pipeline UI code already has ready for them
    (`JumpResolvedEvent`/`on_jump_resolved` were declared for this and,
    until now, never actually fired).

    `requested_dst` (move-only; always `None` for a jump): the
    destination the caller originally asked for via `request_move`,
    kept alongside the real settled `dst` purely so a listener can tell
    "landed exactly where asked" apart from "truncated/redirected
    mid-path" without re-deriving it. Defaults to `None` so this stays
    backward-compatible with any existing construction; `_resolve_move`
    always fills it in. The UI's animation layer is the one consumer
    that needs this (the "smooth slide-back correction" feature) -- it
    lets `PieceRenderer` distinguish a truncated landing from a genuine
    mid-flight capture/swallow without guessing from board occupancy.

    `reverted`: True only for the design-decision-#1 defensive fallback
    in `_resolve_jump_landing`, where a friendly piece is found already
    occupying the jumper's home square at landing time. This should be
    unreachable in practice (`_advance_through_path` stops a friendly
    mover one square short of ever landing there), but if it ever does
    happen, `reverted=True` tells a listener "this jump fizzled
    harmlessly, no capture happened, don't award/log a capture" --
    distinct from an ordinary no-op landing (`captured_piece=None,
    reverted=False`) so the two remain individually inspectable."""
    src: Position
    dst: Position
    piece: Piece
    captured_piece: Optional[Piece]
    move_type: str = 'move'
    requested_dst: Optional[Position] = None
    reverted: bool = False


class MoveScheduler:
    """Owns the raw queue of in-flight moves/jumps and answers
    busy/target/airborne membership queries against it. A thin,
    data-only collaborator of RealTimeArbiter: it knows *what* is
    queued, never *when*/*how* motions get resolved into board state."""

    def __init__(self):
        self._pending: List[PendingMove] = []
        self._seq_counter = itertools.count()

        # Post-move cooldown bookkeeping: one entry per square currently
        # cooling down, `(until_ms, duration_ms)`. Keyed by Position
        # (not piece identity -- boards here never have one, see
        # `ArrayBoard.get_piece_at`'s docstring), so a later motion that
        # settles on the same square just overwrites the old entry; the
        # dict can therefore never grow past `nrows * ncols` entries,
        # nothing further needs to actively prune it.
        self._cooldowns: Dict[Position, Tuple[int, int]] = {}

    def _has_expired(self, complete_time:int , clock_ms: int):
        return complete_time > clock_ms

    def schedule(self, pending_move: PendingMove) -> None:
        pending_move.seq = next(self._seq_counter)
        self._pending.append(pending_move)

    def is_piece_busy(self, src: Position, clock_ms: int) -> bool:
        return any(m.src == src and self._has_expired(m.complete_time, clock_ms) for m in self._pending)

    def is_target_busy(self, dst: Position, clock_ms: int) -> bool:
        """True if some in-flight *move* (jumps don't count -- they
        don't occupy a destination) is already headed to dst. Backs
        Rule 8 Step 2: two pieces may never simultaneously converge on
        the same destination cell."""
        return any(
            m.move_type == 'move' and m.dst == dst and self._has_expired(m.complete_time, clock_ms)
            for m in self._pending
        )

    def is_active_airborne_at(self, cell: Position, clock_ms: int) -> bool:
        return any(
            m.move_type == 'jump' and m.src == cell and m.complete_time >= clock_ms
            for m in self._pending
        )

    def due_moves(self, clock_ms: int) -> List[PendingMove]:
        due = [m for m in self._pending if m.move_type == 'move' and not self._has_expired(m.complete_time, clock_ms)]
        due.sort(key=lambda m: m.complete_time)
        return due

    def due_jumps(self, clock_ms: int) -> List[PendingMove]:
        """Mirror of `due_moves` for jump-type motions -- a hover's
        landing instant. Previously nothing ever queried this: jumps
        were only ever removed by `clear_expired`, silently, with no
        board mutation."""
        due = [m for m in self._pending if m.move_type == 'jump' and not self._has_expired(m.complete_time, clock_ms)]
        due.sort(key=lambda m: m.complete_time)
        return due

    def due_motions(self, clock_ms: int) -> List[PendingMove]:
        """Every due motion -- moves *and* jump landings together -- in
        strict chronological order (`complete_time`, then `seq` to break
        an exact tie deterministically: first-scheduled settles first).

        This has to be a single merged, time-ordered pass rather than
        "all due moves, then all due jumps" (which `due_moves`/
        `due_jumps` alone would tempt you into): once a jump landing can
        capture (requirement 3), a coarse tick that leaves both a move
        and a jump due at once needs them interleaved by their *real*
        completion order, not batched by kind -- otherwise a move that
        completes long after a jump already safely landed could still
        "un-happen" that landing by capturing on top of it before the
        landing is ever processed. Sorting by (complete_time, seq) once,
        up front, is what the colleague's plan's per-event heap gives
        you for free; this is the same guarantee without keeping a
        long-lived heap across many small ticks."""
        due = [m for m in self._pending if not self._has_expired(m.complete_time, clock_ms)]
        due.sort(key=lambda m: (m.complete_time, m.seq))
        return due

    def clear_expired(self, clock_ms: int) -> None:
        self._pending = [m for m in self._pending if self._has_expired(m.complete_time, clock_ms)]

    @property
    def pending_moves(self) -> List[PendingMove]:
        return list(self._pending)

    # -- post-move cooldown feature ---------------------------------------
    def start_cooldown(self, pos: Position, until_ms: int, duration_ms: int) -> None:
        """Records that `pos` can't host a new motion until `until_ms`.
        `duration_ms` (the total length of this cooldown) is kept
        alongside so `cooldown_progress` can report an elapsed fraction
        for the animation, not just a plain yes/no."""
        self._cooldowns[pos] = (until_ms, duration_ms)

    def is_cooling_down(self, pos: Position, clock_ms: int) -> bool:
        entry = self._cooldowns.get(pos)
        return entry is not None and entry[0] > clock_ms

    def cooldown_progress(self, pos: Position, clock_ms: int) -> Optional[float]:
        """`0.0` (just settled, full cooldown remaining) -> `1.0`
        (finished) fraction of the cooldown elapsed, or `None` if `pos`
        isn't currently cooling down at all -- mirrors `PendingMove`'s
        own `motion_progress` shape so the rendering side can treat both
        the same way. `duration_ms <= 0` can't happen for an entry that
        was ever actually stored (cooldown-starting call sites only ever
        call `start_cooldown` when `cooldown_ms > 0`), but is guarded
        against anyway rather than trusting that invariant here too."""
        entry = self._cooldowns.get(pos)
        if entry is None:
            return None
        until_ms, duration_ms = entry
        if until_ms <= clock_ms or duration_ms <= 0:
            return None
        remaining_ms = until_ms - clock_ms
        elapsed_ms = duration_ms - remaining_ms
        return max(0.0, min(1.0, elapsed_ms / duration_ms))
