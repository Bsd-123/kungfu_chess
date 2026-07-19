from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple

from kungfu_chess.model.position import Position
from kungfu_chess.input.board_mapper import BoardMapper
from kungfu_chess.input.controller import Controller
from kungfu_chess.config import GameConfig
from kungfu_chess.engine.game_engine import GameEngine


class CommandError(Exception):
    """Raised on malformed command arguments; caught centrally by CommandRegistry.run and turned into an
    'ERROR <code>' output line."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class PositionArgParser:
    """Shared helper for commands taking '<x> <y>' pixel-coordinate args; raises CommandError on malformed input
    rather than returning a sentinel. Delegates coordinate conversion to BoardMapper."""

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
        """Parses '<x> <y>' into raw ints without any bounds check; used by ClickCommand, which delegates
        bounds/selection handling to Controller."""
        if len(args) != 2:
            raise CommandError("INVALID_ARGS")
        try:
            return int(args[0]), int(args[1])
        except ValueError:
            raise CommandError("INVALID_COORDINATES")


class Command(ABC):
    """Command pattern interface; commands only talk to the GameEngine facade or Controller, never the
    RuleEngine, board, or move scheduler directly."""

    @abstractmethod
    def execute(self, engine: GameEngine, args: List[str]) -> None:
        ...


class ClickCommand(Command):
    """Thin DSL adapter over Controller; all click interpretation lives in Controller. Keeps one Controller
    instance per engine so selection state persists across a script's click lines."""

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
            # Rejected rather than clamped to 0: the virtual clock is monotonic and can't run backward.
            raise CommandError("INVALID_DURATION")
        engine.advance_clock(ms)


class PrintBoardCommand(Command):
    def execute(self, engine, args):
        engine.settle()
        engine.output_chunks.append(engine.render())


class CommandRegistry:
    """Owns command-name -> Command dispatch and line-level parsing; the single place malformed-command errors
    are caught and reported."""

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
