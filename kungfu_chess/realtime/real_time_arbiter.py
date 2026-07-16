from __future__ import annotations
from typing import List, Optional, Protocol, Tuple

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
        particular move take" -- see Spec section 10's N x 1000ms rule; the
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

    # -- post-move cooldown feature ---------------------------------------
    def is_cooling_down(self, pos: Position, clock_ms: int) -> bool:
        return self._scheduler.is_cooling_down(pos, clock_ms)

    def cooldown_progress(self, pos: Position, clock_ms: int) -> Optional[float]:
        return self._scheduler.cooldown_progress(pos, clock_ms)

    # -- scheduling ------------------------------------------------------
    def schedule_move(self, src: Position, dst: Position, piece: Piece,
                       clock_ms: int, duration_ms: int,
                       board: BoardInterface, cooldown_ms: int = 0) -> None:
        # The ordered list of squares this move will pass through is
        # geometry, not timing -- computed once, here, from the board's
        # own `get_path` (the single source of truth for "what squares
        # does this move cross", shared with any future path-preview UI)
        # and carried on the PendingMove so resolution never has to
        # re-derive piece-shape rules. `cooldown_ms` (0 by default, fully
        # backward compatible) rides along the same way `duration_ms`
        # does -- GameEngine decides how long, per piece type, via
        # GameConfig; this class just faithfully starts that cooldown on
        # the landing square once the move settles.
        self._scheduler.schedule(PendingMove(
            move_type='move',
            complete_time=clock_ms + duration_ms,
            src=src, dst=dst, piece=piece,
            start_time=clock_ms,
            path=board.get_path(src, dst),
            cooldown_ms=cooldown_ms,
        ))

    def schedule_jump(self, src: Position, piece: Piece,
                       clock_ms: int, duration_ms: int,
                       cooldown_ms: int = 0) -> None:
        self._scheduler.schedule(PendingMove(
            move_type='jump',
            complete_time=clock_ms + duration_ms,
            src=src, piece=piece,
            start_time=clock_ms,
            cooldown_ms=cooldown_ms,
        ))

    @property
    def pending_moves(self) -> List[PendingMove]:
        return self._scheduler.pending_moves

    # -- rendering support: live (non-authoritative) landing preview ------
    def preview_landing_square(self, m: PendingMove, board: BoardInterface) -> Position:
        """Read-only preview of where `m` would land if it resolved against
        the board's *current* occupancy right now -- purely a rendering
        aid, never a source of game-logic truth (only `resolve_due` /
        `_resolve_move` ever mutate the board or produce a
        SettlementEvent). Added because a sliding piece's on-screen
        position was, before this, always interpolated straight toward
        its *originally requested* destination for its entire flight,
        regardless of anything sitting in its path -- so a queen sliding
        at a pawn visually glided straight over it and only snapped back
        to the truncated/capture square at the very last instant, when
        the motion actually settled. That's confusing to watch even
        though the *logical* outcome (Rule 1/2 truncation or capture) was
        always correct.

        `_advance_through_path` already never mutates anything -- it only
        ever calls `board.get_piece_at`, the same read-only query this
        preview needs -- so this is simply exposing that existing walk as
        a named, public capability, rather than duplicating its logic.
        Calling it every frame while a piece is mid-flight lets the
        renderer's interpolation target track "where this would land if
        it settled right now" instead of the fixed original request, so
        the piece visually stops at (or captures) whatever's actually in
        its way as soon as the animation reaches it -- matching what
        `resolve_due` will authoritatively do once `m.complete_time`
        actually arrives. A blocker that shows up late (a concurrent
        motion that only lands moments before this one settles) can still
        make the true settlement differ from the last-previewed square;
        that gap is exactly what the animation snap-back correction
        (`PieceRenderer.on_move_resolved`) is for -- this preview just
        makes that correction a no-op in the common case instead of the
        only source of truth."""
        if m.move_type != 'move' or m.dst is None:
            return m.src
        landing_square, _captured_piece = self._advance_through_path(m, board)
        return landing_square

    # -- time-synchronized resolution ------------------------------------
    def resolve_due(self, clock_ms: int, board: BoardInterface,
                     promotion_resolver: PromotionResolver) -> List[SettlementEvent]:
        """Settle every motion due as of clock_ms -- moves *and* jump
        landings together, in one strict chronological pass
        (`MoveScheduler.due_motions`: complete_time, then scheduling
        order to break an exact tie). Each settlement is still atomic
        (Rule 10) -- one uninterrupted board mutation per motion, no
        partial state ever observable -- but a move's mutation is no
        longer necessarily a simple src-clear/dst-write: `_resolve_move`
        may find the path blocked before the requested destination and
        land the piece somewhere short of it (requirements 1 & 2).

        Moves and jump landings must be interleaved by true completion
        order, not resolved as "all due moves, then all due jump
        landings": once a jump landing can capture (requirement 3), a
        single coarse tick that leaves both due at once needs them
        settled in the order they actually happened, or a move that
        completes long after a jump already safely landed could
        "un-happen" that landing by capturing on top of it before the
        landing is ever processed -- exactly the kind of bug the
        colleague's plan's single time-ordered event queue is designed
        to prevent, and exactly the failure mode a naive "moves batch,
        then jumps batch" split reintroduces.

        Before any of that: `_extend_hovers_for_crossings` runs as a
        pre-pass, pushing out any pending jump's landing time that would
        otherwise land while a friendly slider is still (per that
        slider's own constant-speed timing) mid-transit across the
        jumper's square. This has to happen before `due_motions` is
        snapshotted, so an extended jump correctly drops out of "due"
        for this call instead of landing prematurely."""
        self._extend_hovers_for_crossings()

        events: List[SettlementEvent] = []

        for m in self._scheduler.due_motions(clock_ms):
            if m.move_type == 'move':
                event = self._resolve_move(m, board, promotion_resolver)
            else:
                event = self._resolve_jump_landing(m, board)
            if event is not None:
                events.append(event)

        self._scheduler.clear_expired(clock_ms)
        return events

    # ---- design decision #1a: friendly transit dynamically extends a hover --
    def _extend_hovers_for_crossings(self) -> None:
        """A hovering piece's square is never truly "vacated" for its own
        side (design decision #1): a friendly slider may still cross
        *beneath* it, but the jumper must not land back down while that
        crossing is still in progress. So, for every currently pending
        jump, look at every currently pending *same-color* move whose
        planned path crosses the jumper's home square as a pass-through
        (non-terminal) square, and push the jump's `complete_time` out
        to at least that mover's own `complete_time`.

        Why the *whole* mover's completion, not just its narrow transit
        window over that one square: this engine settles a motion
        atomically, once, at its own single `complete_time` (Rule 10) --
        there is no continuous simulation, no intermediate instant at
        which a mover's relationship to a mid-path square is ever
        separately checked. `_advance_through_path` only ever asks "is
        the jumper's square airborne" at the single moment the *mover's
        own* motion resolves. So the only way to guarantee that check
        sees "still airborne, still passable" is to keep the jump alive
        at least that long -- extending to a narrower per-square instant
        would (and, in testing, did) let the jumper land in between,
        turn into an ordinary settled occupant, and then get the mover
        wrongly truncated by requirement 2's ordinary same-color rule
        when the mover's own completion finally arrived. This is a
        direct, deliberate consequence of keeping this codebase's
        single-instant settlement architecture intact rather than
        moving to the colleague's original per-square continuous event
        model -- documented here since it's the one place the coarser
        architecture visibly trades off precision for simplicity.

        This is deliberately re-run at the top of every `resolve_due`
        call (not computed once at scheduling time): new same-color
        moves can be scheduled after the jump already exists, and each
        one that crosses the jumper's square must extend it again.

        Enemy pieces never trigger this: they always treat an airborne
        square as vacant to pass under, with no timing consequence for
        the jumper (requirement 3) -- only a *friendly* crossing does,
        per design decision #1's explicit "friendly piece" wording.

        The *terminal* square of a friendly mover's path (where it would
        actually land) is deliberately excluded here -- that case isn't
        a timing question at all, it's handled by `_advance_through_path`
        treating the jumper's square as a normal same-color occupant for
        landing purposes, so the mover simply never lands there in the
        first place (see that method's docstring)."""
        pending = self._scheduler.pending_moves
        jumps = [m for m in pending if m.move_type == 'jump']
        if not jumps:
            return  # nothing airborne, nothing to extend

        movers = [m for m in pending if m.move_type == 'move']

        for jump in jumps:
            for mover in movers:
                if mover.piece.color != jump.piece.color:
                    continue  # only a friendly crossing extends the hover
                if jump.src not in mover.path:
                    continue
                index = mover.path.index(jump.src)
                if index == len(mover.path) - 1:
                    continue  # terminal square: a landing question, not a timing one
                if mover.complete_time > jump.complete_time:
                    # PendingMove is a plain mutable dataclass -- this is
                    # the same in-place-field-update style
                    # `MoveScheduler.schedule` already uses for `seq`.
                    jump.complete_time = mover.complete_time

    # ---- requirements 1 & 2: square-by-square arrival resolution -------
    def _resolve_move(self, m: PendingMove, board: BoardInterface,
                       promotion_resolver: PromotionResolver) -> Optional[SettlementEvent]:
        if board.get_piece_at(m.src) != m.piece:
            # Captured (or otherwise removed) before its own move could
            # complete -- e.g. an enemy motion with an earlier
            # (complete_time, seq) already landed on m.src. Nothing to
            # settle; this is "later arrival captures earlier occupant"
            # applied to the *source* square, which falls out for free
            # from resolving due_motions in chronological order.
            return None

        landing_square, captured_piece = self._advance_through_path(m, board)

        settled_piece = m.piece
        if landing_square == m.dst:
            # Promotion only fires for a move that actually reaches its
            # originally-requested destination -- one truncated early by
            # a same-color near-miss never got there.
            settled_piece = promotion_resolver.resolve_arrival_piece(m.piece, m.dst, board)

        board.set_piece_at(landing_square, settled_piece)
        if landing_square != m.src:
            board.set_piece_at(m.src, None)

        self._maybe_start_cooldown(m, landing_square)

        return SettlementEvent(
            src=m.src, dst=landing_square, piece=settled_piece,
            captured_piece=captured_piece, move_type='move',
            requested_dst=m.dst,
        )

    def _maybe_start_cooldown(self, m: PendingMove, landing_square: Position) -> None:
        """Post-move cooldown feature: as soon as `m` actually settles
        (on whatever square it truly landed on -- `landing_square`, not
        necessarily `m.dst`, since a truncated/captured landing still
        starts the cooldown right where the piece ended up), that square
        can't host another motion for `m.cooldown_ms`. A no-op when
        `cooldown_ms` is 0 (the default), so this is fully inert for any
        caller that never opted into the feature."""
        if m.cooldown_ms > 0:
            self._scheduler.start_cooldown(
                landing_square, m.complete_time + m.cooldown_ms, m.cooldown_ms)

    def _advance_through_path(self, m: PendingMove,
                               board: BoardInterface) -> Tuple[Position, Optional[Piece]]:
        """Walks `m.path` (precomputed by `BoardInterface.get_path` at
        scheduling time) in travel order against the *current* board --
        already mutated by every earlier-completing motion resolved so
        far this call. That ordering is what makes "later arrival
        captures/blocks earlier occupant" fall out for free: whichever
        occupant is found on a square when this event fires necessarily
        claimed it at an earlier completion time than this one, so there
        is never a need to compare two timestamps against each other --
        only to ask "who/what is on S right now."

        A square airborne as of *this move's own* completion time is
        always treated as vacant while merely walking *through* it here,
        regardless of what token still physically sits in the board grid
        there (requirement 3: the hovering piece stays on the board
        purely so it keeps rendering -- see `GameState.schedule_jump` --
        it is not actually "there" for collision purposes until it
        lands). Using `m.complete_time` rather than the outer
        settle-call's clock reading matters when a single coarse tick
        leaves both a long-overdue jump and a long-overdue move due at
        once: "was it airborne when *this* mover actually arrived" is
        the only question that produces the right answer regardless of
        how much later the engine happened to get around to processing
        it.

        "Vacant to walk through" is not the same as "a friendly mover
        may actually land there", though (design decision #1) -- see
        `_respect_hover_claim`, applied once below to whatever square
        this walk would otherwise land the mover on. That's a separate,
        final check rather than something decided square-by-square
        inside this loop, because the mover's *actual* landing square
        isn't known until the walk finishes: it could be `m.dst` (no
        obstruction at all) or a square reached only because something
        *later* in the path forced a same-color truncation back onto
        it -- and either way, if that square turns out to be a friendly
        jumper's home square, the same "not vacated for landing" rule
        has to apply.

        Returns `(landing_square, captured_piece)`:
        - first square in the path occupied by a different color: the
          mover lands there and captures the occupant (requirement 1),
          even when that square isn't the requested destination.
          (Never a same-color hover claim -- an airborne square is
          always walked through as vacant, never treated as a capture.)
        - first square occupied by the *same* color (including a
          same-color jumper's square, once `_respect_hover_claim` backs
          off it): the mover never reaches it and lands on the square
          immediately before it in the path (or stays at `m.src` if
          that's the very first square) -- requirement 2's "stuck one
          square behind".
        - no obstruction anywhere along the path: lands on `m.dst`,
          unless `_respect_hover_claim` backs that off too.
        """
        previous = m.src
        for square in m.path:
            if self._airborne_piece_at(square, m.complete_time) is not None:
                previous = square
                continue
            occupant = board.get_piece_at(square)
            if occupant is None:
                previous = square
                continue
            if occupant.color != m.piece.color:
                return square, occupant
            return self._respect_hover_claim(m, previous), None
        return self._respect_hover_claim(m, m.dst), None

    def _respect_hover_claim(self, m: PendingMove, landing_square: Position) -> Position:
        """Design decision #1: even though a friendly piece may freely
        walk *through* a hovering square (`_advance_through_path`
        above), it may never actually *land* on one -- the square is
        "not vacated" for its own side's landing purposes, only for
        transit. If `landing_square` (wherever the ordinary path walk
        concluded the mover should stop, whether that's `m.dst` reached
        cleanly or a square it was truncated onto by something later in
        its path) turns out to be a square a same-color piece is
        currently hovering over, back up one more square -- and keep
        backing up if that square is *also* claimed, though in practice
        that second step should never be reachable. Backing up (rather
        than, say, capturing or erroring) is exactly the same
        "requirement 2" truncation semantics already used everywhere
        else a same-color occupant blocks a mover; a friendly hover
        claim is just one more same-color occupant, geometrically."""
        while True:
            hoverer = self._airborne_piece_at(landing_square, m.complete_time)
            if hoverer is None or hoverer.color != m.piece.color:
                return landing_square
            if landing_square == m.src:
                return m.src  # nowhere further back to retreat to
            index = m.path.index(landing_square)
            landing_square = m.path[index - 1] if index > 0 else m.src

    def _airborne_piece_at(self, square: Position,
                            as_of_time: int) -> Optional[Piece]:
        """The piece currently mid-hover over `square`, as of
        `as_of_time`, or `None` if nothing is airborne there. A small
        superset of `is_active_airborne_at` (kept as a public
        boolean-only query elsewhere) that also hands back *who* is
        hovering, which `_respect_hover_claim` needs to tell a friendly
        jumper's square apart from an enemy one."""
        for m in self._scheduler.pending_moves:
            if m.move_type == 'jump' and m.src == square and m.complete_time >= as_of_time:
                return m.piece
        return None

    # ---- requirement 3: jump / hover landing ----------------------------
    def _resolve_jump_landing(self, m: PendingMove,
                               board: BoardInterface) -> Optional[SettlementEvent]:
        """A hover always lands back on its own takeoff square (`m.src`).
        The board there was never actually cleared (see
        `GameState.schedule_jump`), so three distinct situations can be
        found at the landing instant:

        - the square still holds exactly the piece that jumped (nothing
          else settled there during the hover): a no-op landing, no
          capture.
        - it holds a *different* piece of the same color: design
          decision #1's defensive fallback. `_extend_hovers_for_crossings`
          (delaying the landing while a friendly is merely transiting)
          plus `_advance_through_path`'s terminal-square rule (a
          friendly mover is truncated one square short rather than ever
          landing here) together mean this branch *should* be
          unreachable through normal play -- but if some path I haven't
          thought of ever gets here anyway, the rule is explicit: "the
          hovering jumper cannot land; it is returned safely... reverting
          the jump." Since the square is physically already occupied
          (one token per cell), "returned safely" can only mean: no
          capture, no board mutation, the friendly piece that's already
          there keeps it, and the jump is reported as harmlessly
          reverted (`reverted=True`) rather than as a capture in either
          direction -- nobody's score should change over a friendly-fire
          bookkeeping corner case.
        - it holds a different-color piece: captured, and the jumper
          lands in its place (requirement 3's landing-capture case).
        """
        occupant = board.get_piece_at(m.src)

        if occupant == m.piece:
            self._maybe_start_cooldown(m, m.src)
            return SettlementEvent(
                src=m.src, dst=m.src, piece=m.piece,
                captured_piece=None, move_type='jump',
            )

        if occupant is not None and occupant.color == m.piece.color:
            # Defensive fallback only -- see docstring. No board
            # mutation: the friendly piece already there keeps the
            # square, and nothing is captured in either direction.
            self._maybe_start_cooldown(m, m.src)
            return SettlementEvent(
                src=m.src, dst=m.src, piece=m.piece,
                captured_piece=None, move_type='jump', reverted=True,
            )

        board.set_piece_at(m.src, m.piece)
        self._maybe_start_cooldown(m, m.src)
        return SettlementEvent(
            src=m.src, dst=m.src, piece=m.piece,
            captured_piece=occupant, move_type='jump',
        )
