# Real-Time Collision & Hover: Integration Report

Your colleague's plan and your codebase solve the same three requirements (cross-color
latency capture, same-color near-miss truncation, jump/hover pass-through + landing
capture) with two genuinely different architectures. Their plan models the board as
`Square` objects carrying live occupancy/timestamp state, with `Piece` as a mutable object
holding a back-reference to its square, and a single global min-heap of per-square arrival
events. Your codebase models the board as a token grid (`ArrayBoard`), `Piece` as an
**immutable** value object reconstructed fresh on every read, and motions as **whole-move**
`PendingMove` entries (src → dst over one total duration) resolved atomically at
`complete_time`, not leg-by-leg.

Per your instruction, nothing below introduces `Square`, makes `Piece` mutable, or changes
any class's role in the Strategy/Facade/DI structure. Every change is a change to what a
method's body computes, not to who talks to whom. All changes described here have already
been applied directly to your files and verified with a standalone test harness (see
"Verification" at the end).

---

## 1. What was already correct, before touching anything

Before changing anything, it's worth being precise about what your architecture already
gave you for free, because it's more than it looks:

- **Requirement 1 at the destination square** was already fully correct. `RealTimeArbiter.resolve_due`
  sorted `due_moves` by `complete_time` and mutated the board as it went, so a later-completing
  move already saw whatever an earlier-completing move had just placed at a shared destination,
  and captured it. The defensive check `board.get_piece_at(m.src) != m.piece` already meant a
  piece captured *in place* (its square taken by someone else) correctly cancels its own
  pending move when that move's turn to resolve comes up.
- **Two movers converging on the same destination** was already fully prevented before
  scheduling, via `is_target_busy`.
- **What was never implemented at all**: anything about the squares a move passes *through*.
  `is_target_busy`/`resolve_due` only ever looked at a move's final destination. A rook e1→e8
  and a queen a4→h4 crossing at e4 simply never interacted — neither one's `PendingMove` even
  mentions e4. This is the actual gap requirement 2 is about, and it's a bigger gap than "missing
  a special case": there was no data structure anywhere holding "what squares does this move
  cross" for a sliding piece.
- **Jump/hover was documented as intentionally inert.** Your own `final_plan_verified.md`
  states outright: a jump never mutates the board (the piece token just sits there the whole
  time) and never produces a `SettlementEvent`, "not a bug, just worth knowing." The UI layer
  had `JumpResolvedEvent`/`ScoreObserver.on_jump_resolved`/`EventBus.publish_jump_resolved`
  already declared and wired for exactly this case, explicitly commented as "never actually
  invoked... there is currently no source event to build one from." Requirement 3 is that
  missing source event.

---

## 2. Requirement-by-requirement mapping

### Requirement 2 (same-color near-miss) and Requirement 1 (mid-path capture)

These turned out to be the same mechanism, which is exactly your colleague's core insight
("who/what is on S" is the only question you ever need to ask) — just realized differently
because your architecture resolves a whole move atomically at one instant instead of
leg-by-leg:

- **`BoardInterface` gained `get_path(src, dst) -> List[Position]`**, sitting right next to
  the existing `path_clear`, implemented in `ArrayBoard` with the same direction-stepping loop
  `path_clear` already used. For a knight (or anything non-straight-line) it degenerates to
  `[dst]`. This is the single source of truth for "what squares does this move cross" your
  colleague's plan also calls for — it just lives on `Board` (next to `path_clear`) rather than
  on `RuleEngine`, since geometry-over-storage was already `Board`'s job here.
- **`PendingMove` gained a `path: List[Position]` field**, computed once via `board.get_path`
  at scheduling time in `RealTimeArbiter.schedule_move`. This keeps the Arbiter from ever having
  to know piece-shape rules — it only ever walks a list it was handed, same separation of
  concerns your colleague's plan calls for between Motion and RuleEngine.
- **`RookMovementRule`/`BishopMovementRule`/`QueenMovementRule`/pawn's two-square opening**
  dropped their `board.path_clear`/mid-square-emptiness gate. They now validate shape only —
  exactly your colleague's "keep geometry, remove 'is path clear'" instruction. `path_clear`
  itself is untouched on `BoardInterface`, in case anything else still wants a static read.
- **`RealTimeArbiter._resolve_move`/`_advance_through_path`** replaced the old
  src-clear/dst-write with a walk of `m.path` against the live board: the first square with a
  different-color occupant becomes the landing square and that occupant is captured
  (requirement 1, even mid-path); the first square with a same-color occupant means the mover
  lands on the square *before* it, or stays put if the very first square is blocked
  (requirement 2); no obstruction at all lands on `m.dst` exactly as before. Promotion only
  fires when the mover actually reaches `m.dst` — a truncated move never promotes.

Because `due_motions` (see below) still resolves in strict completion order and mutates the
board as it goes, "later arrival captures/blocks earlier occupant" needs no timestamp
comparison anywhere in this code — same as your colleague's plan, just phrased as "walk the
path against whatever's already been mutated this pass" instead of "pop the next heap event."

### Requirement 3 (jump / hover)

- **`GameState.schedule_jump` deliberately does NOT clear the board cell.** Your snapshot/
  rendering layer only ever draws what `board.get_piece_at` returns, so clearing the token
  would make the hovering piece invisible mid-jump — a real regression I caught in testing and
  reverted (see "A bug I found and fixed" below).
- Instead, **"vacant while airborne" is a property `RealTimeArbiter._advance_through_path` asks
  for explicitly**, via the existing `is_active_airborne_at` query, layered on top of the
  literal board content. A passing move's path-walk treats an airborne square as vacant
  regardless of what token is still sitting there.
- **`RealTimeArbiter._resolve_jump_landing` is new** — jumps previously never had a landing
  resolution at all. At the landing instant it asks who's actually standing on the home square:
  nobody-changed → no-op; a different-color piece moved in during the hover → captured, jumper
  lands in its place (requirement 3's actual ask); a *same-color* piece moved in → flagged as an
  open question below, since your requirements don't specify it.
- **`SettlementEvent` gained `move_type: str = 'move'`** (default preserves any existing
  positional construction) so a listener can tell a jump-landing settlement from a move
  settlement without importing `PendingMove`.
- **`ui/app.py`'s `wire_event_observers`** now branches on `event.move_type` and publishes
  `JumpResolvedEvent` for jump landings — the event type and `ScoreObserver.on_jump_resolved`
  handler were already sitting there, declared and wired, waiting for exactly this source event.

---

## 3. A bug I found and fixed while testing this

My first implementation processed `due_moves` and `due_jumps` as two separate batches per
tick (moves, then jump landings) — reasoning that a jump landing only ever touches its own
home square. Testing against a **single large `advance_clock` call** (as opposed to many
small ones) surfaced a real bug: a knight hovers over e4 and safely lands back at t=1000; a
black rook slides a4→h4 (7 squares, 7000ms), passing through e4 well after the knight's
already back. With one coarse tick from t=0 straight to t=10000, both motions are "due" in
the same `resolve_due` call. Processing moves first let the rook capture the knight at e4 —
correct — but then the jump-landing pass ran *afterward* and saw an enemy (the rook) now
sitting on the knight's home square, and "recaptured" it right back, silently undoing the
capture. Stepping the same scenario in ten separate 1000ms ticks gave the correct answer
(rook keeps the capture), which is precisely the kind of tick-granularity-dependent bug your
colleague's plan's single time-ordered event queue is designed to prevent.

Fix: `MoveScheduler.due_motions(clock_ms)` now merges moves and jump landings into one list
sorted by `(complete_time, seq)` — `seq` a new monotonically increasing field on
`PendingMove`, assigned at scheduling time, breaking exact-timestamp ties by
scheduling order (first-scheduled settles first). `resolve_due` walks this single merged,
chronologically ordered list instead of two batches. `_advance_through_path`'s airborne check
also switched from asking "is it airborne as of the outer clock reading" to "is it airborne
as of *this specific mover's own* `complete_time`" — otherwise a long-overdue jump processed
in the same oversized tick as a long-overdue move would still get the ordering wrong. I
verified this fix makes single-big-tick and many-small-tick advancement produce identical
results (see Verification).

This is worth internalizing beyond this one fix: **any coarse, "settle whatever's due"
resolution model needs a single chronologically-merged event list across every motion kind
that can mutate the board on completion.** The moment you add a second kind of event with
board-mutating consequences (as requirement 3 does to jumps), splitting resolution into
"batch A, then batch B" reintroduces exactly the ordering bug your colleague's unified
priority queue exists to prevent — it isn't just a stylistic preference, it's a correctness
requirement your own codebase would have violated without the fix above.

---

## 4. Gaps and edge cases — some the plan flagged, one it didn't need to (different architecture), plus a few new ones from this codebase specifically

**From the colleague's own "edge cases worth deciding explicitly" list:**

- **Exact-timestamp ties**: resolved the same way they suggested — deterministic, via
  scheduling order (`seq`), not a "mutual capture" rule. Flag if you'd rather have a different
  policy.
- **Enemy present when a hover begins**: not currently blocked (a piece can still jump even if
  contested at takeoff) — this would be a check in `GameEngine.request_jump`, not the Arbiter,
  if you want it.
- **Friendly piece occupies the landing square**: implemented as "jumper is displaced" (see
  `_resolve_jump_landing`'s three-way branch above) — the least destructive default without
  inventing new state, but genuinely your call. In practice this branch is close to
  unreachable today, since a same-color piece can never *request* a move whose destination is
  the jumper's home square in the first place (that's rejected upfront by the existing
  `friendly_destination` check, which still sees the jumper's token there) — it could only be
  reached via some other same-color motion truncating mid-path onto that exact square. Worth
  knowing rather than assuming it's dead code.

**New, specific to this codebase's architecture (not applicable to the colleague's Square-based design):**

- **Animation snap-back on truncation.** `PendingMove.dst` still holds the *originally
  requested* destination for the whole duration (used by `GameSnapshot`/`PieceRenderer` to
  interpolate a smooth slide). A move that gets truncated mid-path only discovers its real
  landing square at the single atomic settle instant — so the piece will visually glide toward
  the original destination the whole time, then snap backward to the true (earlier) landing
  square the instant it settles. Fixing this properly means the renderer would need to know a
  move might not reach its `dst` before that's actually decided, which is a real UI/animation
  question, not a logic one. Flagging rather than silently picking an answer.
- **A truncated-to-zero-squares move still fires a `SettlementEvent`** (`src == dst == m.src`,
  no capture). Harmless today (no crash, `captured_piece=None`), but the move log will show a
  slightly odd "moved to its own square" entry. Easy to suppress if you'd rather it stayed
  silent — I left it in since `GameEngine`'s king-capture check and other listeners still need
  *some* signal that the motion resolved.
- **`MoveScheduler._has_expired` is misleadingly named** — it returns `True` when a motion is
  *not yet* expired (`complete_time > clock_ms`, i.e., still pending). Pre-existing, not part of
  this change, but worth a rename in a follow-up since it's exactly the kind of inverted
  boolean that causes real bugs later.
- **Request-time rejection UX changed for sliding pieces.** Previously, requesting a rook move
  through a piece that will obviously never move was rejected immediately
  (`illegal_piece_move`). Now it's accepted and only resolves as "stuck" once its duration
  elapses. This is the correct real-time-chess behavior per the plan, but it does mean bad
  requests no longer fail fast — confirm that's the UX you want.

---

## 5. Suggested tests (adapted from the colleague's list to this codebase's API)

All of the following were run against a standalone copy of your engine during this session —
see "Verification" below for exact results. Recommend adding them as permanent tests in
`kungfu_chess/texttests` or a new pytest module:

1. Rook e1→e8 with a same-color pawn at e3: rook ends up at e4 (stuck one square behind), pawn
   untouched, no promotion.
2. Rook e1→e8 with an enemy king at e3: rook captures at e3, `engine.game_over` becomes `True`,
   rook never reaches e8.
3. Knight hovers at e4; enemy rook slides through on a path that crosses e4 well after the
   knight's own (short) hover has already landed: rook continues through/captures based on
   whoever is *actually* there at the rook's own arrival time — verified identical whether
   advanced via one large `advance_clock` call or many small ones (this is the regression test
   for the bug in section 3).
4. Two motions (a jump landing and a move) scheduled to complete at the exact same
   millisecond: verify first-scheduled-wins via `seq`, deterministically, every run.
5. A move truncated before reaching its destination must never trigger promotion, even if the
   truncation point is adjacent to the promotion rank.

---

## 6. Verification performed this session

Since editing files directly on this workspace, I mirrored the edited files into an isolated
sandbox copy and ran them standalone (`python3`, no pytest dependency needed):

- All touched files (`model/board.py`, `model/game_state.py`, `rules/piece_rules.py`,
  `realtime/motion.py`, `realtime/real_time_arbiter.py`, `ui/app.py`, `ui/events/events.py`,
  `ui/events/observers/score_observer.py`) compile cleanly.
- Constructed boards exercising: same-color mid-path truncation, cross-color mid-path capture,
  hover pass-through (both single-big-tick and many-small-tick advancement, confirmed
  identical), hover landing-instant capture under an exact-timestamp tie, king-capture via a
  mid-path interception correctly setting `game_over`, plus regression checks that ordinary
  knight moves, upfront `friendly_destination` rejection, and normal/blocked promotion all
  still behave exactly as before this change.
- All of the above passed after the section-3 fix; the pre-fix version failed the
  single-big-tick hover test specifically, which is what surfaced the bug.

---

## 7. Open questions from the first pass — now resolved (see Part 2 below)

The three items originally listed here were exactly the three design decisions you specified
in your follow-up. All three are implemented; superseded by section 8.

---

# Part 2: The Three Design Decisions + Movement-Range Highlight

This section covers the follow-up round: your three explicit rulings on the open questions
above, plus the new movement-range highlight feature. Same ground rules as Part 1 — existing
class boundaries, interfaces, and the Spec §12 no-live-objects-in-the-view boundary all stay
intact; every change is a change to what a method computes.

## 8. Design decision #1 — friendly-during-hover

Your rule has two halves, and they turned out to need two separate mechanisms:

- **"A friendly piece may pass beneath a hover only while in transit; the jump duration must
  dynamically extend to cover it."** New `RealTimeArbiter._extend_hovers_for_crossings`, run as
  a pre-pass at the top of every `resolve_due` call: for every pending jump, look at every
  pending same-color move whose planned path crosses the jumper's square as a *non-terminal*
  (pass-through) square, and push the jump's `complete_time` out to at least that mover's own
  `complete_time`.

  **Important adaptation, found via testing, not assumed up front:** I first tried extending
  the jump only far enough to cover the crossing piece's narrow transit window over that one
  square (a fine-grained per-square exit time). That's wrong for this architecture, and testing
  caught it directly: a knight hovering at e4, extended just long enough for a same-color rook
  to notionally "pass through" e4 mid-journey, would still let the knight land safely *before*
  the rook's own move actually resolves — and since this engine only ever checks a mover's
  whole path once, at that mover's own single `complete_time` (Rule 10 settlement is atomic),
  the rook's own resolution would then find the knight already landed and settled, and get
  wrongly truncated by ordinary requirement-2 rules, as if the knight had been sitting there
  the whole time. The fix: extend the jump to cover the *entire remainder* of the crossing
  mover's journey (`jump.complete_time = max(jump.complete_time, mover.complete_time)`), not
  just a narrow sub-window. This is a direct, deliberate consequence of keeping your existing
  single-instant-settlement architecture rather than moving to your colleague's continuous
  per-square event model — documented in the code as the one place the coarser architecture
  visibly trades precision for simplicity. Verified with a rook crossing under an extended
  hover and continuing on to its own real destination unharmed (see Verification).

- **"A friendly piece forced to settle exactly on the jumper's square instead lands one square
  short; the jumper stays safe."** `RealTimeArbiter._advance_through_path` now finishes its walk
  by calling `_respect_hover_claim` on whatever square it concluded the mover should land on —
  whether that's `m.dst` reached cleanly or a square reached only because something *later* in
  the path forced a same-color truncation back onto it. If that square is currently claimed by
  a same-color hover, it backs up one further square (recursing, though a second step should
  never be reachable in practice).

  **Second bug caught by testing, not assumed:** my first version only checked this at the
  moment a square was the *geometrically last* entry in the mover's path (i.e., only handled
  "the mover's literal requested destination is the jumper's square"). Testing a rook sliding
  a4→h4 with the jumper at e4 (non-terminal) and a *different* blocking piece at f4 showed the
  rook landing exactly on e4 — the jumper's claimed square — because the truncation-onto-e4 was
  discovered only *after* e4 had already been walked past as "vacant transit." Moving the check
  to run once, after the walk concludes, against whatever square is actually settled on (rather
  than only mid-loop against the current square), fixed it: the rook now correctly backs up to
  d4, one square short of the jumper's claim, in that exact scenario (see Verification).

- **Defensive fallback, `_resolve_jump_landing`**: with both of the above in place, a friendly
  piece should never actually reach the jumper's square in the first place, making your literal
  "cannot land, reverted" rule effectively unreachable. Kept as a defensive branch anyway (no
  board mutation, no capture in either direction, reported via a new `reverted=True` field on
  `SettlementEvent` so a listener can tell "harmless fizzle" apart from either kind of capture)
  in case some path I haven't considered ever reaches it.

## 9. Design decision #2 — smooth slide-back on truncation

`SettlementEvent` gained `requested_dst: Optional[Position]` (move-only, `None` for jumps) —
the destination originally asked for, kept alongside the real settled `dst`. `ui/app.py`'s
bridge threads it into a correspondingly extended `MoveResolvedEvent` (`requested_dst_row`/
`requested_dst_col`, both optional/additive).

`PieceRenderer` (new `on_move_resolved` method, subscribed the same way `MoveLogObserver`/
`ScoreObserver` already are — `wire_event_observers` now optionally takes the renderer, and
`BoardView` grew a thin `piece_renderer` read-only property so `ui/app.py`'s composition root
can reach it without `BoardView` itself knowing anything about events) detects a mismatch
between requested and actual destination and queues a short (180ms) corrective slide — new
`_Correction` dataclass, eased with a cubic ease-out (`1 - (1-t)**3`: fast start, smooth
deceleration into the true landing square, never a linear glide or a bounce) — starting from
wherever the piece was *actually last rendered* (mid-interpolation toward the wrong target),
not from the requested square, so there's no visible pop at either end of the correction.

One correctness wrinkle here too: the existing "swallowed piece" fade-out heuristic (guesses
capture-vs-not by checking whether a matching piece appears at the *requested* destination)
would otherwise misfire on every truncated landing, showing a fading ghost at the wrong square
at the same time as the real piece slides into its correct one. Fixed by having
`on_move_resolved` record the redirect authoritatively (`_redirected_from`), so the vanished-key
pass can skip the heuristic entirely for anything it already knows was a redirect, not a
capture. Verified directly (see Verification) rather than just reasoned through, since this is
exactly the kind of interaction between two independent pieces of animation bookkeeping that's
easy to get subtly wrong.

## 10. Design decision #3 — no fail-fast rejection for blocked slides

No code change needed here — confirmed rather than implemented. `piece_rules.py`'s sliding-piece
rules already validate shape only (from Part 1's integration), so a rook/bishop/queen move
through a currently-blocked path is already accepted at request time and left to the Arbiter to
truncate or capture dynamically, exactly as specified.

## 11. Movement-range highlight (new feature)

- **`GameEngine.legal_destinations(source) -> List[Position]`** (new): every square
  `request_move` would currently accept from `source`, plus `source` itself if `request_jump`
  would currently be accepted. Deliberately re-derives legality through the exact same
  `is_piece_busy`/`is_target_busy`/`RuleEngine.validate_move` gates `request_move` itself uses
  (rather than a cheaper approximation), so the highlighted set can never drift from what a
  click would actually do. Pure query — mutates nothing, safe to call every frame.
- **`InputState` gained `legal_destinations: Sequence[Position] = ()`** (additive/backward
  compatible), populated once per tick in `ui/app.py`'s `run_loop` from
  `engine.legal_destinations(controller.selected)` — the same "loop asks the engine, builds a
  plain-value DTO, hands it to the renderer" pipeline `selected` itself already uses. Never
  bypasses `Controller`'s selection state, per your instruction.
- **`OverlayRenderer.draw`** now also draws a yellow (`(0, 255, 255)` BGR) outline plus a small
  center dot on every square in `legal_destinations`, via `Img`'s existing `draw_rect`/
  `draw_circle` primitives — no new graphics backend. Outline-only (not filled) so a piece
  sitting on a highlighted capture-target square stays fully visible underneath it.

## 12. Verification performed this round

Same standalone-sandbox approach as Part 1, extended to cover the new scenarios:

- Regression: every Part 1 scenario (same-color truncation, cross-color mid-path capture,
  basic knight move, promotion, `friendly_destination` upfront rejection) still passes
  unchanged.
- New: a friendly slider crossing beneath an extended hover reaches its own real destination
  unharmed, and the jumper lands back safely, in a single coarse `advance_clock` call.
- New: a friendly slider whose path is blocked by a *third* piece exactly at the jumper's
  square backs up one further square instead of landing on the jumper's claim (the bug
  described in section 8, confirmed fixed).
- New: `legal_destinations` for an unobstructed rook returns exactly its rank + file + its own
  square, and returns empty while the piece is mid-motion.
- New (UI layer, via a lightweight harness bypassing real sprite assets): `PieceRenderer.
  on_move_resolved` queues a correction only when requested/actual destinations differ, starts
  it from the correct last-rendered pixel, and the ease-out curve is monotonic and lands exactly
  on target; `OverlayRenderer.draw` paints yellow pixels into a real `Img`/`cv2` canvas at every
  legal-destination square and leaves everything else untouched.

## 13. Open questions from this round

1. The "friendly forced onto the jumper's square" fallback (section 8's defensive branch)
   should now be unreachable through normal play with both fixes in place — flag if you ever
   see a `reverted=True` event in practice, since that would mean some path I haven't
   considered still reaches it.
2. Extending a hover to cover an entire crossing mover's remaining journey (section 8) can make
   a jumper stay airborne for a while if a slow-moving friendly slider merely grazes its square
   early in a long journey. This is the correct behavior given your codebase's single-instant
   settlement architecture (there's no cheaper way to guarantee correctness without moving to a
   continuous per-square event model), but it's worth knowing this trade-off exists if a jumper
   ever needs to be reliably available again quickly.
3. Movement-range highlight currently includes the piece's own square (indicating "click again
   to jump") whenever a jump would be accepted — confirm that reads clearly in the UI, or if
   you'd rather the jump option be indicated some other way (e.g. a different color/icon).
