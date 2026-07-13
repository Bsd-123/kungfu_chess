from __future__ import annotations
import re
import sys
from typing import List, Optional, Tuple

from kungfu_chess.io.board_printer import BoardTextView
from kungfu_chess.config import GameConfig


class BoardError(Exception):
    """Raised when the input cannot be parsed into a valid board."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class BoardParser:
    """Parses the 'Board:' / 'Commands:' text format. Purely concerned
    with turning raw text into rows of tokens and a list of command
    lines -- no game logic lives here."""

    def __init__(self, config: GameConfig):
        self._config = config
        self._token_re = re.compile(config.token_pattern)

    def find_sections(self, lines: List[str]) -> Tuple[int, Optional[int]]:
        board_start = None
        commands_start = None
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped == self._config.board_marker:
                board_start = i
            elif stripped == self._config.commands_marker:
                commands_start = i
                break

        if board_start is None:
            raise BoardError("MISSING_BOARD")

        if commands_start is not None and commands_start < board_start:  # pragma: no cover
            # Defensive guard: unreachable via the scan above (which stops
            # at the first Commands marker), kept for robustness if the
            # scan logic ever changes.
            raise BoardError("COMMANDS_BEFORE_BOARD")

        return board_start, commands_start

    def extract_board_lines(self, lines: List[str], board_start: int,
                             commands_start: Optional[int]) -> List[str]:
        end = commands_start if commands_start is not None else len(lines)
        board_lines = lines[board_start + 1:end]

        while board_lines and board_lines[0].strip() == '':
            board_lines.pop(0)
        while board_lines and board_lines[-1].strip() == '':
            board_lines.pop()

        if not board_lines:
            raise BoardError("EMPTY_BOARD")

        return board_lines

    def parse_board(self, board_lines: List[str]) -> List[List[str]]:
        rows: List[List[str]] = []
        ncols = None

        for line in board_lines:
            tokens = line.split()

            if not tokens:
                raise BoardError("BLANK_LINE_IN_BOARD")

            for tok in tokens:
                if not self._token_re.match(tok):
                    raise BoardError("UNKNOWN_TOKEN")

            if ncols is None:
                ncols = len(tokens)
            elif len(tokens) != ncols:
                raise BoardError("ROW_WIDTH_MISMATCH")

            rows.append(tokens)

        return rows

    def parse(self, text: str) -> Tuple[List[List[str]], List[str]]:
        """Convenience method: parse full input text into (rows, command_lines)."""
        lines = text.split('\n')
        board_start, commands_start = self.find_sections(lines)
        board_lines = self.extract_board_lines(lines, board_start, commands_start)
        rows = self.parse_board(board_lines)
        command_lines = lines[commands_start + 1:] if commands_start is not None else []
        return rows, command_lines


def main():
    config = GameConfig()
    try:
        data = sys.stdin.read()
    except UnicodeDecodeError:
        print("ERROR INVALID_INPUT")
        return

    parser = BoardParser(config)
    try:
        rows, _ = parser.parse(data)
    except BoardError as e:
        print(f"ERROR {e.code}")
        return

    sys.stdout.write(BoardTextView.render_rows(rows) + '\n')


if __name__ == '__main__':  # pragma: no cover
    main()
