from __future__ import annotations
from typing import List

from kungfu_chess.model.board import BoardInterface


class BoardTextView:
    """Turns board data into the space-separated, newline-delimited wire/display text format."""

    @staticmethod
    def render_rows(rows: List[List[str]]) -> str:
        return '\n'.join(' '.join(row) for row in rows)

    @staticmethod
    def render_board(board: BoardInterface) -> str:
        return BoardTextView.render_rows(board.to_rows())


# Alias: this component is also referred to as `BoardPrinter`.
BoardPrinter = BoardTextView
