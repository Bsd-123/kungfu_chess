"""Pure UI-side event DTOs (plan section 7.1 directory tree). Plain
values only (strings/ints), matching the same read-only-DTO philosophy
as `GameSnapshot`/`PieceSnapshot` -- deliberately NOT the engine's own
`SettlementEvent` (which carries live `Piece` values). Nothing in this
module, `event_bus.py`, or `observers/` ever imports from
`kungfu_chess.realtime` or `kungfu_chess.model`: the translation from
the engine's `SettlementEvent` into these types happens in exactly one
place, `ui/app.py`'s composition root, which is the one part of the UI
package that's allowed to know the engine's internal types exist."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class MoveResolvedEvent:
    """`dst_row`/`dst_col` is always where the piece actually ended up.
    `requested_dst_row`/`requested_dst_col` (new: animation snap-back
    feature) carry what was originally asked for -- `None` when the two
    already agree (or for any producer that hasn't been updated to know
    the difference, keeping this additive/backward-compatible). A
    listener that only cares about "where did it end up" can keep
    ignoring these two fields entirely; `PieceRenderer` is the one
    consumer that uses them, to distinguish a truncated/redirected
    landing (needs a quick corrective slide) from an ordinary one (no
    correction needed) or a genuine mid-flight capture (already handled
    by its existing fade-out)."""
    piece_color: str
    piece_kind: str
    src_row: int
    src_col: int
    dst_row: int
    dst_col: int
    captured_piece_kind: Optional[str]
    requested_dst_row: Optional[int] = None
    requested_dst_col: Optional[int] = None


@dataclass(frozen=True)
class JumpResolvedEvent:
    """Published when a hover/jump lands (real-time collision/sync
    integration: requirement 3). Originally declared for API symmetry
    with the plan's section 7.6 blueprint and never published, because
    jumps didn't produce a SettlementEvent at all under the pre-
    integration engine. They do now -- see
    `kungfu_chess.realtime.motion.SettlementEvent.move_type` and
    `RealTimeArbiter._resolve_jump_landing` -- so this is live."""
    piece_color: str
    piece_kind: str
    row: int
    col: int
    captured_piece_kind: Optional[str]
