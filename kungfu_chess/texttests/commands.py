from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple

from kungfu_chess.model.position import Position
from kungfu_chess.input.board_mapper import BoardMapper
from kungfu_chess.input.controller import Controller
from kungfu_chess.config import GameConfig
from kungfu_chess.engine.game_engine import GameEngine


class CommandError(Exception):
    """Raised when a command's arguments are malformed (wrong count,
    non-numeric, out of bounds, ...). Caught centrally by
    CommandRegistry.run and turned into a standardized, testable
    'ERROR <code>' output line instead of being silently swallowed."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class PositionArgParser:
    """Shared helper for commands that take '<x> <y>' pixel-coordinate
    arguments. Extracted to avoid duplicating parsing logic (DRY).
    Raises CommandError on any malformed input rather than returning a
    sentinel, so callers can't accidentally ignore bad input. Coordinate
    conversion itself is delegated to BoardMapper (Rule 4) -- this class
    only owns argument parsing and bounds validation."""

    def __init__(self, config: GameConfig):
        self._mapper = BoardMapper(config.cell_pixel_size)

    def parse(self, engine: GameEngine, args: List[str]) -> Position:
        if len(args) != 2:
            raise CommandError("INVALID_ARGS")
        try:
            x = int(args[0])
            y = int(args[1])
        except ValueError:
            raise CommandError("INVALID_COORDINATES")
        pos = self._mapper.pixel_to_cell(x, y)
        if not engine.board.is_within_bounds(pos):
            raise CommandError("OUT_OF_BOUNDS")
        return pos

    @staticmethod
    def parse_raw_ints(args: List[str]) -> Tuple[int, int]:
        """Parses '<x> <y>' into raw ints without any bounds check.
        Used by ClickCommand, which now delegates bounds/selection
        handling to Controller (Spec §11) instead of doing it itself."""
        if len(args) != 2:
            raise CommandError("INVALID_ARGS")
        try:
            return int(args[0]), int(args[1])
        except ValueError:
            raise CommandError("INVALID_COORDINATES")


class Command(ABC):
    """Command pattern interface: every user command is one class with
    a single responsibility. Commands only ever talk to the GameEngine
    facade or the Controller (Rule 8) -- they never touch the RuleEngine,
    the board, or the move scheduler directly."""

    @abstractmethod
    def execute(self, engine: GameEngine, args: List[str]) -> None:
        ...


class ClickCommand(Command):
    """Thin DSL adapter over Controller (Spec §11/§20). All click
    interpretation -- selection, outside-board cancellation, jump-on-
    same-cell, move-request-on-different-cell -- lives in Controller now;
    this class only parses the two ints and keeps one Controller instance
    per engine so selection state persists across a script's click
    lines, exactly as it did when that state lived on GameEngine."""

    def __init__(self, config: GameConfig):
        self._config = config
        self._controllers: Dict[int, Controller] = {}

    def _controller_for(self, engine: GameEngine) -> Controller:
        controller = self._controllers.get(id(engine))
        if controller is None:
            controller = Controller(engine, self._config.cell_pixel_size)
            self._controllers[id(engine)] = controller
        return controller

    def execute(self, engine, args):
        x, y = PositionArgParser.parse_raw_ints(args)
        self._controller_for(engine).click(x, y)


class JumpCommand(Command):
    def __init__(self, config: GameConfig):
        self._position_parser = PositionArgParser(config)

    def execute(self, engine, args):
        pos = self._position_parser.parse(engine, args)
        engine.request_jump(pos)


class WaitCommand(Command):
    def execute(self, engine, args):
        if len(args) != 1:
            raise CommandError("INVALID_ARGS")
        try:
            ms = int(args[0])
        except ValueError:
            raise CommandError("INVALID_DURATION")
        if ms < 0:
            # The virtual clock (Rule 9) is monotonic: a negative wait
            # would run it backward, which would in turn make already
            # in-flight Motions un-settle. Reject explicitly rather than
            # silently clamping to 0, so bad input is visible.
            raise CommandError("INVALID_DURATION")
        engine.advance_clock(ms)


class PrintBoardCommand(Command):
    def execute(self, engine, args):
        engine.settle()
        engine.output_chunks.append(engine.render())


class CommandRegistry:
    """Owns command-name -> Command dispatch and line-level parsing.
    Nothing here knows about board storage or movement rules. Also owns
    the single place malformed-command errors are caught and reported,
    so individual commands never need their own error-output logic."""

    def __init__(self, config: GameConfig):
        self._config = config
        self._commands: Dict[str, Command] = {}

    def register(self, name: str, command: Command) -> None:
        self._commands[name] = command

    def get(self, name: str) -> Optional[Command]:
        return self._commands.get(name)

    def normalize(self, stripped_line: str) -> Tuple[str, List[str]]:
        if stripped_line == self._config.print_board_command:
            return 'print_board', []
        parts = stripped_line.split()
        return parts[0], parts[1:]

    def run(self, engine: GameEngine, command_lines: List[str]) -> None:
        for line in command_lines:
            stripped = line.strip()
            if stripped == '':
                continue
            name, args = self.normalize(stripped)
            handler = self.get(name)
            if handler is None:
                continue  # unknown command: silently ignored
            try:
                handler.execute(engine, args)
            except CommandError as e:
                engine.output_chunks.append(f"ERROR {e.code}")


def create_default_command_registry(config: GameConfig) -> CommandRegistry:
    registry = CommandRegistry(config)
    registry.register('click', ClickCommand(config))
    registry.register('jump', JumpCommand(config))
    registry.register('wait', WaitCommand())
    registry.register('print_board', PrintBoardCommand())
    return registry
