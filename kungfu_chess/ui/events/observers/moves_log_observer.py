"""Phase 5 step 2 (final_plan_verified.md): appends `(time, move_text)`
per side on settle. Pure UI-side -- only ever touches `MoveResolvedEvent`
(plain strings/ints), never an engine type.

`clock_ms_source` is injected as a zero-arg callable rather than a
stored `GameEngine` reference, so this observer stays decoupled from
the engine object itself (plan section 7.7 DI/testability philosophy)
and is trivially driven by a fake clock in headless tests.

Task 17 rework, to match the reference mockup's two side panels (one
move list per color, no color prefix needed since panel placement
already implies it) and its `mm:ss.mmm` time column: `entries` is now
split per color, and move text is "SAN-lite" -- close to real algebraic
notation (`Nc6`, `Bxc6`, `e4`, `exd5`) without full disambiguation
(never checks whether a second like piece could also reach the same
square) or check/checkmate suffixes, since the engine doesn't expose
either of those concepts to the UI layer at all."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List

from kungfu_chess.ui.events.events import MoveResolvedEvent

_COL_LETTERS = "abcdefgh"


def _square_name(row: int, col: int) -> str:
    # row 0 = rank 8 (black's back rank), matching ui/setup.py's own
    # row-ordering convention for the standard starting position.
    return f"{_COL_LETTERS[col]}{8 - row}"


def _move_text(kind: str, src_row: int, src_col: int,
                dst_row: int, dst_col: int, captured_kind) -> str:
    dst = _square_name(dst_row, dst_col)
    if kind == "P":
        # Real SAN only prefixes a pawn capture with its *source file*
        # letter (e.g. "exd5"); a quiet pawn move is just the
        # destination square ("e4"), no "P" prefix.
        if captured_kind:
            return f"{_COL_LETTERS[src_col]}x{dst}"
        return dst
    return f"{kind}x{dst}" if captured_kind else f"{kind}{dst}"


def format_time_ms(time_ms: int) -> str:
    """`mm:ss.mmm`, matching the reference mockup's Time column
    (e.g. "00:04.105"). A plain module-level function (not a method)
    so `PanelRenderer` can format a `LoggedMove.time_ms` without having
    to hold a `MoveLogObserver` reference just to reach it."""
    total_ms = max(0, int(time_ms))
    minutes, rest_ms = divmod(total_ms, 60_000)
    seconds, millis = divmod(rest_ms, 1000)
    return f"{minutes:02d}:{seconds:02d}.{millis:03d}"


@dataclass(frozen=True)
class LoggedMove:
    time_ms: int
    text: str


class MoveLogObserver:
    def __init__(self, clock_ms_source: Callable[[], int]):
        self._clock_ms_source = clock_ms_source
        self.entries: Dict[str, List[LoggedMove]] = {"w": [], "b": []}

    def on_move_resolved(self, event: MoveResolvedEvent) -> None:
        text = _move_text(event.piece_kind, event.src_row, event.src_col,
                           event.dst_row, event.dst_col, event.captured_piece_kind)
        self.entries[event.piece_color].append(
            LoggedMove(self._clock_ms_source(), text))

    def recent(self, color: str, n: int = 8) -> List[LoggedMove]:
        return self.entries[color][-n:]
