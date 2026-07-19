"""Standard 8x8 starting position as `rows` tokens (`'.'` empty,
`'<color><kind>'` e.g. `'wP'`) for `build_game_engine(rows, config)`.
Row 0 is Black's back rank, row 7 White's -- an arbitrary but consistent
convention; the engine itself has no notion of "top"/"bottom"."""
from __future__ import annotations
from typing import List

EMPTY_ROW: List[str] = ['.'] * 8

standard_start_rows: List[List[str]] = [
    ['bR', 'bN', 'bB', 'bQ', 'bK', 'bB', 'bN', 'bR'],
    ['bP', 'bP', 'bP', 'bP', 'bP', 'bP', 'bP', 'bP'],
    list(EMPTY_ROW),
    list(EMPTY_ROW),
    list(EMPTY_ROW),
    list(EMPTY_ROW),
    ['wP', 'wP', 'wP', 'wP', 'wP', 'wP', 'wP', 'wP'],
    ['wR', 'wN', 'wB', 'wQ', 'wK', 'wB', 'wN', 'wR'],
]
