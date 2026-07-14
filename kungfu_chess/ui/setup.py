"""Phase 0 (final_plan_verified.md §4B / Phase 0 step 4): the standard
8x8 chess starting position, hardcoded as `rows` tokens matching
`GameConfig.token_pattern` (`'.'` for empty, `'<color><kind>'` e.g.
`'wP'`/`'bK'` for a piece).

This bypasses the text DSL (`BoardParser`) entirely -- that format stays
exclusive to the `texttests/` harness, per the plan's design decision.
`standard_start_rows` is fed straight into the *already-existing*
`kungfu_chess.app.build_game_engine(rows, config)` factory.

Row 0 is the back/pawn ranks for Black, row 7 for White -- an arbitrary
but internally consistent convention (the engine has no notion of "top"
or "bottom"; only pixel_y = row * cell_pixel_size, which a renderer is
free to flip later if desired).
"""
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
