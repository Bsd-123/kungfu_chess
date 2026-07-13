from __future__ import annotations
from typing import List

from kungfu_chess.model.board import BoardInterface


class BoardTextView:
    """View Adapter / DTO layer (Phase 6): the single place responsible
    for turning board data into the space-separated, newline-delimited
    wire/display text format. Neither the Model (GameState) nor the
    parser's own helpers format text themselves -- both hand off to this
    class, so the on-the-wire text representation can change (e.g.
    padding, a different delimiter, colorized output) without touching
    model or parsing code."""

    @staticmethod
    def render_rows(rows: List[List[str]]) -> str:
        return '\n'.join(' '.join(row) for row in rows)

    @staticmethod
    def render_board(board: BoardInterface) -> str:
        return BoardTextView.render_rows(board.to_rows())


# Spec §5/§13 names this component `BoardPrinter`. Kept as an alias
# rather than a rename so nothing that already imports `BoardTextView`
# (or its `render_rows`/`render_board` methods) has to change.
BoardPrinter = BoardTextView
