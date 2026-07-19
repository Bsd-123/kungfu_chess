from kungfu_chess.io.board_printer import BoardTextView, BoardPrinter
from kungfu_chess.model.board import ArrayBoard


def test_render_rows():
    rows = [['wK', '.'], ['.', 'bK']]
    assert BoardTextView.render_rows(rows) == 'wK .\n. bK'


def test_render_rows_empty():
    assert BoardTextView.render_rows([]) == ''


def test_render_board_delegates_to_to_rows():
    board = ArrayBoard([['wK', '.'], ['.', 'bK']])
    assert BoardTextView.render_board(board) == 'wK .\n. bK'


def test_board_printer_is_alias():
    assert BoardPrinter is BoardTextView
