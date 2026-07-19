import io
import sys

import pytest

from kungfu_chess.app import run, main, build_game_engine
from kungfu_chess.config import GameConfig
from kungfu_chess.model.board import ArrayBoard


STANDARD_BOARD = """Board:
bR bN bB bQ bK bB bN bR
bP bP bP bP bP bP bP bP
. . . . . . . .
. . . . . . . .
. . . . . . . .
. . . . . . . .
wP wP wP wP wP wP wP wP
wR wN wB wQ wK wB wN wR
Commands:
"""


def test_build_game_engine_returns_working_engine():
    config = GameConfig()
    rows = [['.'] * 8 for _ in range(8)]
    engine = build_game_engine(rows, config)
    assert engine.board.nrows == 8
    assert engine.board.ncols == 8


def test_run_with_print_board_command_returns_rendered_board():
    text = STANDARD_BOARD.replace("Commands:\n", "Commands:\nprint board\n")
    output = run(text)
    assert 'wK' in output
    assert 'bK' in output


def test_run_with_no_commands_still_renders_board():
    output = run(STANDARD_BOARD)
    assert 'wK' in output


def test_run_with_malformed_board_returns_error():
    output = run("no board marker here")
    assert output.startswith("ERROR")


def test_run_with_bad_command_appends_error_line():
    text = STANDARD_BOARD.replace("Commands:\n", "Commands:\njump abc def\n")
    output = run(text)
    assert 'ERROR' in output


def test_main_reads_stdin_writes_stdout(monkeypatch):
    monkeypatch.setattr(sys, 'stdin', io.StringIO(STANDARD_BOARD))
    captured = io.StringIO()
    monkeypatch.setattr(sys, 'stdout', captured)
    main()
    assert 'wK' in captured.getvalue()
