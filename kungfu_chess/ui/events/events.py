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
    piece_color: str
    piece_kind: str
    src_row: int
    src_col: int
    dst_row: int
    dst_col: int
    captured_piece_kind: Optional[str]


@dataclass(frozen=True)
class JumpResolvedEvent:
    """Declared for API symmetry with the plan's section 7.6 blueprint.
    Never actually published under the current engine: jumps never
    produce a SettlementEvent at all (plan section 1 -- "a jump lands
    back on its own src square, so there's nothing to settle"), so
    there is currently no source event to build one from."""
    piece_color: str
    piece_kind: str
    row: int
    col: int
    captured_piece_kind: Optional[str]
