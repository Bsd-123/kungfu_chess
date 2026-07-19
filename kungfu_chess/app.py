from __future__ import annotations
import sys
from typing import Optional

from kungfu_chess.model.board import ArrayBoard
from kungfu_chess.io.board_parser import BoardError, BoardParser
from kungfu_chess.texttests.commands import create_default_command_registry
from kungfu_chess.config import GameConfig
from kungfu_chess.engine.game_engine import GameEngine
from kungfu_chess.model.game_state import GameState
from kungfu_chess.rules.promotion_rules import ConditionalPromotionRule, last_rank_trigger
from kungfu_chess.rules.rule_engine import RuleEngine
from kungfu_chess.rules.rule_registry import create_default_chess_registry
from kungfu_chess.rules.win_condition import CapturedTypeWinCondition


def build_game_engine(rows, config: GameConfig) -> GameEngine:
    board = ArrayBoard(rows, empty_token=config.empty_token)
    state = GameState(board, config)
    rule_registry = create_default_chess_registry()
    promotion_rule = ConditionalPromotionRule(trigger=last_rank_trigger)
    rule_engine = RuleEngine(rule_registry, promotion_rule=promotion_rule)
    # Win condition is driven by config (win_condition_piece_types,
    # ('K',) by default) rather than hardcoded inside GameEngine.
    win_condition = CapturedTypeWinCondition(config.win_condition_piece_types)
    return GameEngine(state, rule_engine, config, win_condition=win_condition)


def run(data: str, config: Optional["GameConfig"] = None) -> str:
    """Parse input text, run its commands, and return the textual output.
    Kept separate from main() so it can be tested directly without
    touching stdin/stdout."""
    config = config or GameConfig()
    parser = BoardParser(config)

    try:
        rows, command_lines = parser.parse(data)
    except BoardError as e:
        return f"ERROR {e.code}\n"

    engine = build_game_engine(rows, config)
    command_registry = create_default_command_registry(config)
    command_registry.run(engine, command_lines)

    if not engine.output_chunks:
        engine.output_chunks.append(engine.render())

    return "\n".join(engine.output_chunks) + "\n"


def main() -> None:
    """Reads the full text format from stdin and writes the result to
    stdout."""
    data = sys.stdin.read()
    sys.stdout.write(run(data))
