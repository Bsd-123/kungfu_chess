"""Appends `(time, move_text)` per side on settle. `clock_ms_source` is a
zero-arg callable (not a stored engine ref) so it's easily faked in
tests. Move text is "SAN-lite" -- no disambiguation or check/mate
suffixes, since the engine doesn't expose those concepts to the UI. If
an `event_bus` is supplied, each entry also re-publishes a
`MoveLoggedEvent` so other subscribers never need to poll `.entries`
directly."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from kungfu_chess.ui.events.event_bus import EventBus
from kungfu_chess.ui.events.events import MoveLoggedEvent, MoveResolvedEvent
from kungfu_chess.ui.theme import DEFAULT_THEME

_COL_LETTERS = DEFAULT_THEME.board.file_letters


def _square_name(row: int, col: int) -> str:
    # row 0 = rank 8, matching ui/setup.py's row convention.
    return f"{_COL_LETTERS[col]}{8 - row}"


def _move_text(kind: str, src_row: int, src_col: int,
                dst_row: int, dst_col: int, captured_kind) -> str:
    dst = _square_name(dst_row, dst_col)
    if kind == "P":
        # Pawn captures prefix the source file (e.g. "exd5"); quiet
        # moves are just the destination square.
        if captured_kind:
            return f"{_COL_LETTERS[src_col]}x{dst}"
        return dst
    return f"{kind}x{dst}" if captured_kind else f"{kind}{dst}"


def format_time_ms(time_ms: int) -> str:
    """`mm:ss.mmm` (e.g. "00:04.105"). Module-level so `PanelRenderer`
    can format a `LoggedMove.time_ms` without a `MoveLogObserver` ref."""
    total_ms = max(0, int(time_ms))
    minutes, rest_ms = divmod(total_ms, 60_000)
    seconds, millis = divmod(rest_ms, 1000)
    return f"{minutes:02d}:{seconds:02d}.{millis:03d}"


@dataclass(frozen=True)
class LoggedMove:
    time_ms: int
    text: str


class MoveLogObserver:
    def __init__(self, clock_ms_source: Callable[[], int],
                 event_bus: Optional[EventBus] = None):
        self._clock_ms_source = clock_ms_source
        self._event_bus = event_bus
        self.entries: Dict[str, List[LoggedMove]] = {"w": [], "b": []}

    def on_move_resolved(self, event: MoveResolvedEvent) -> None:
        text = _move_text(event.piece_kind, event.src_row, event.src_col,
                           event.dst_row, event.dst_col, event.captured_piece_kind)
        time_ms = self._clock_ms_source()
        self.entries[event.piece_color].append(LoggedMove(time_ms, text))
        if self._event_bus is not None:
            self._event_bus.publish(
                MoveLoggedEvent(color=event.piece_color, text=text, time_ms=time_ms))

    def recent(self, color: str, n: int = 8) -> List[LoggedMove]:
        return self.entries[color][-n:]
