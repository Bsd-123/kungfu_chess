import io
import sys

import pytest

from kungfu_chess.config import GameConfig
from kungfu_chess.io.board_parser import BoardParser, BoardError, main


def parser():
    return BoardParser(GameConfig())


def test_find_sections_basic():
    p = parser()
    lines = ['Board:', 'wK .', 'Commands:', 'click 0 0']
    board_start, commands_start = p.find_sections(lines)
    assert board_start == 0
    assert commands_start == 2


def test_find_sections_no_commands():
    p = parser()
    lines = ['Board:', 'wK .']
    board_start, commands_start = p.find_sections(lines)
    assert board_start == 0
    assert commands_start is None


def test_find_sections_missing_board_raises():
    p = parser()
    with pytest.raises(BoardError) as exc:
        p.find_sections(['Commands:', 'click 0 0'])
    assert exc.value.code == 'MISSING_BOARD'


def test_find_sections_lone_commands_marker_reported_as_missing_board():
    p = parser()
    with pytest.raises(BoardError) as exc:
        p.find_sections(['Commands:'])
    assert exc.value.code == 'MISSING_BOARD'


def test_extract_board_lines_trims_blank_lines():
    p = parser()
    lines = ['Board:', '', 'wK .', '', 'Commands:']
    board_lines = p.extract_board_lines(lines, 0, 4)
    assert board_lines == ['wK .']


def test_extract_board_lines_no_commands_marker():
    p = parser()
    lines = ['Board:', 'wK .', '']
    board_lines = p.extract_board_lines(lines, 0, None)
    assert board_lines == ['wK .']


def test_extract_board_lines_empty_raises():
    p = parser()
    lines = ['Board:', '', '', 'Commands:']
    with pytest.raises(BoardError) as exc:
        p.extract_board_lines(lines, 0, 3)
    assert exc.value.code == 'EMPTY_BOARD'


def test_parse_board_valid():
    p = parser()
    rows = p.parse_board(['wK . bK', '. . .'])
    assert rows == [['wK', '.', 'bK'], ['.', '.', '.']]


def test_parse_board_blank_line_in_middle_raises():
    p = parser()
    with pytest.raises(BoardError) as exc:
        p.parse_board(['wK .', '', '. .'])
    assert exc.value.code == 'BLANK_LINE_IN_BOARD'


def test_parse_board_unknown_token_raises():
    p = parser()
    with pytest.raises(BoardError) as exc:
        p.parse_board(['wX .'])
    assert exc.value.code == 'UNKNOWN_TOKEN'


def test_parse_board_row_width_mismatch_raises():
    p = parser()
    with pytest.raises(BoardError) as exc:
        p.parse_board(['wK . .', 'wK .'])
    assert exc.value.code == 'ROW_WIDTH_MISMATCH'


def test_parse_full_text_with_commands():
    p = parser()
    text = "Board:\nwK .\nCommands:\nclick 0 0\nwait 10"
    rows, command_lines = p.parse(text)
    assert rows == [['wK', '.']]
    assert command_lines == ['click 0 0', 'wait 10']


def test_parse_full_text_without_commands():
    p = parser()
    text = "Board:\nwK ."
    rows, command_lines = p.parse(text)
    assert rows == [['wK', '.']]
    assert command_lines == []


def test_board_error_carries_code():
    err = BoardError('SOME_CODE')
    assert err.code == 'SOME_CODE'
    assert str(err) == 'SOME_CODE'


def test_main_success(monkeypatch, capsys):
    monkeypatch.setattr(sys, 'stdin', io.StringIO('Board:\nwK .\n'))
    main()
    out = capsys.readouterr().out
    assert out == 'wK .\n'


def test_main_error(monkeypatch, capsys):
    monkeypatch.setattr(sys, 'stdin', io.StringIO('Commands:\n'))
    main()
    out = capsys.readouterr().out
    assert out == 'ERROR MISSING_BOARD\n'


def test_main_invalid_unicode(monkeypatch, capsys):
    class BadStdin:
        def read(self):
            raise UnicodeDecodeError('utf-8', b'\xff', 0, 1, 'bad byte')

    monkeypatch.setattr(sys, 'stdin', BadStdin())
    main()
    out = capsys.readouterr().out
    assert out == 'ERROR INVALID_INPUT\n'
