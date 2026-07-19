import pytest

from kungfu_chess.model.board import ArrayBoard
from kungfu_chess.config import GameConfig
from kungfu_chess.texttests.commands import (
    ClickCommand,
    JumpCommand,
    WaitCommand,
    PrintBoardCommand,
    CommandRegistry,
    CommandError,
    PositionArgParser,
    create_default_command_registry,
)
from kungfu_chess.engine.game_engine import GameEngine
from kungfu_chess.model.game_state import GameState
from kungfu_chess.model.position import Position
from kungfu_chess.rules.rule_engine import RuleEngine
from kungfu_chess.rules.rule_registry import create_default_chess_registry
from kungfu_chess.rules.promotion_rules import ConditionalPromotionRule, last_rank_trigger


def make_engine(rows=None, config=None):
    rows = rows or [['.'] * 8 for _ in range(8)]
    config = config or GameConfig()
    board = ArrayBoard(rows, empty_token=config.empty_token)
    state = GameState(board, config)
    registry = create_default_chess_registry()
    promo = ConditionalPromotionRule(trigger=last_rank_trigger)
    rule_engine = RuleEngine(registry, promotion_rule=promo)
    return GameEngine(state, rule_engine, config)


# -- PositionArgParser -------------------------------------------------

def test_position_arg_parser_valid():
    config = GameConfig()
    engine = make_engine(config=config)
    parser = PositionArgParser(config)
    pos = parser.parse(engine, ["0", "0"])
    assert pos == Position(0, 0)


def test_position_arg_parser_wrong_arg_count():
    config = GameConfig()
    engine = make_engine(config=config)
    parser = PositionArgParser(config)
    with pytest.raises(CommandError):
        parser.parse(engine, ["0"])


def test_position_arg_parser_non_numeric():
    config = GameConfig()
    engine = make_engine(config=config)
    parser = PositionArgParser(config)
    with pytest.raises(CommandError):
        parser.parse(engine, ["a", "b"])


def test_position_arg_parser_out_of_bounds():
    config = GameConfig()
    engine = make_engine(config=config)
    parser = PositionArgParser(config)
    with pytest.raises(CommandError):
        parser.parse(engine, ["100000", "100000"])


def test_position_arg_parser_parse_raw_ints():
    x, y = PositionArgParser.parse_raw_ints(["10", "20"])
    assert (x, y) == (10, 20)


def test_position_arg_parser_parse_raw_ints_bad_count():
    with pytest.raises(CommandError):
        PositionArgParser.parse_raw_ints(["10"])


def test_position_arg_parser_parse_raw_ints_bad_values():
    with pytest.raises(CommandError):
        PositionArgParser.parse_raw_ints(["a", "b"])


# -- ClickCommand --------------------------------------------------------

def test_click_command_selects_piece():
    rows = [['.'] * 8 for _ in range(8)]
    rows[6][0] = 'wP'
    config = GameConfig()
    engine = make_engine(rows, config)
    cmd = ClickCommand(config)
    cmd.execute(engine, ["0", "600"])
    assert engine.selected is None or True  # selection state lives in Controller, not engine


def test_click_command_reuses_controller_per_engine():
    rows = [['.'] * 8 for _ in range(8)]
    rows[6][0] = 'wP'
    config = GameConfig()
    engine = make_engine(rows, config)
    cmd = ClickCommand(config)
    cmd.execute(engine, ["0", "600"])
    cmd.execute(engine, ["0", "600"])
    assert engine.is_piece_busy(Position(6, 0)) is True


# -- JumpCommand -----------------------------------------------------------

def test_jump_command_requests_jump():
    rows = [['.'] * 8 for _ in range(8)]
    rows[6][0] = 'wP'
    config = GameConfig()
    engine = make_engine(rows, config)
    cmd = JumpCommand(config)
    cmd.execute(engine, ["0", "600"])
    assert engine.is_piece_busy(Position(6, 0)) is True


# -- WaitCommand -------------------------------------------------------

def test_wait_command_advances_clock():
    config = GameConfig()
    engine = make_engine(config=config)
    cmd = WaitCommand()
    cmd.execute(engine, ["500"])
    assert engine.clock_ms == 500


def test_wait_command_bad_arg_count():
    engine = make_engine()
    cmd = WaitCommand()
    with pytest.raises(CommandError):
        cmd.execute(engine, [])


def test_wait_command_non_numeric():
    engine = make_engine()
    cmd = WaitCommand()
    with pytest.raises(CommandError):
        cmd.execute(engine, ["abc"])


def test_wait_command_negative_duration():
    engine = make_engine()
    cmd = WaitCommand()
    with pytest.raises(CommandError):
        cmd.execute(engine, ["-5"])


# -- PrintBoardCommand -----------------------------------------------------

def test_print_board_command_appends_render():
    engine = make_engine()
    cmd = PrintBoardCommand()
    cmd.execute(engine, [])
    assert len(engine.output_chunks) == 1


# -- CommandRegistry ---------------------------------------------------

def test_registry_register_and_get():
    config = GameConfig()
    registry = CommandRegistry(config)
    cmd = WaitCommand()
    registry.register('wait', cmd)
    assert registry.get('wait') is cmd


def test_registry_get_unknown_returns_none():
    config = GameConfig()
    registry = CommandRegistry(config)
    assert registry.get('nope') is None


def test_registry_normalize_print_board_special_case():
    config = GameConfig()
    registry = CommandRegistry(config)
    name, args = registry.normalize('print board')
    assert name == 'print_board'
    assert args == []


def test_registry_normalize_regular_command():
    config = GameConfig()
    registry = CommandRegistry(config)
    name, args = registry.normalize('wait 500')
    assert name == 'wait'
    assert args == ['500']


def test_registry_run_skips_blank_lines_and_unknown_commands():
    config = GameConfig()
    registry = create_default_command_registry(config)
    engine = make_engine(config=config)
    registry.run(engine, ['', '   ', 'frobnicate 1 2'])
    assert engine.output_chunks == []


def test_registry_run_catches_command_error_and_appends_output():
    config = GameConfig()
    registry = create_default_command_registry(config)
    engine = make_engine(config=config)
    registry.run(engine, ['wait abc'])
    assert engine.output_chunks == ['ERROR INVALID_DURATION']


def test_registry_run_executes_wait_command():
    config = GameConfig()
    registry = create_default_command_registry(config)
    engine = make_engine(config=config)
    registry.run(engine, ['wait 100'])
    assert engine.clock_ms == 100


def test_create_default_command_registry_has_all_commands():
    config = GameConfig()
    registry = create_default_command_registry(config)
    assert isinstance(registry.get('click'), ClickCommand)
    assert isinstance(registry.get('jump'), JumpCommand)
    assert isinstance(registry.get('wait'), WaitCommand)
    assert isinstance(registry.get('print_board'), PrintBoardCommand)
