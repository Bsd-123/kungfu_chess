"""Phase 5 step 2 (final_plan_verified.md): appends `(time, move_text)`
per side on settle. Pure UI-side -- only ever touches `MoveResolvedEvent`
(plain strings/ints), never an engine type.

`clock_ms_source` is injected as a zero-arg callable rather than a
stored `GameEngine` reference, so this observer stays decoupled from
the engine object itself (plan section 7.7 DI/testability philosophy)
and is trivially driven by a fake clock in headless tests.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List

from kungfu_chess.ui.events.events import MoveResolvedEvent

_COL_LETTERS = "abcdefgh"


def _square_name(row: int, col: int) -> str:
    # row 0 = rank 8 (black's back rank), matching ui/setup.py's own
    # row-ordering convention for the standard starting position.
    return f"{_COL_LETTERS[col]}{8 - row}"


@dataclass(frozen=True)
class LoggedMove:
    time_ms: int
    text: str


class MoveLogObserver:
    def __init__(self, clock_ms_source: Callable[[], int]):
        self._clock_ms_source = clock_ms_source
        self.entries: List[LoggedMove] = []

    def on_move_resolved(self, event: MoveResolvedEvent) -> None:
        src = _square_name(event.src_row, event.src_col)
        dst = _square_name(event.dst_row, event.dst_col)
        text = f"{event.piece_color}{event.piece_kind} {src}-{dst}"
        if event.captured_piece_kind:
            text += f" x{event.captured_piece_kind}"
        self.entries.append(LoggedMove(self._clock_ms_source(), text))

    def recent(self, n: int = 8) -> List[LoggedMove]:
        return self.entries[-n:]
