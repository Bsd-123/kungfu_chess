import io
import sys

from main import main as cli_main


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


def test_main_cli_forwards_to_app(monkeypatch):
    monkeypatch.setattr(sys, 'stdin', io.StringIO(STANDARD_BOARD))
    captured = io.StringIO()
    monkeypatch.setattr(sys, 'stdout', captured)
    cli_main()
    assert 'wK' in captured.getvalue()
