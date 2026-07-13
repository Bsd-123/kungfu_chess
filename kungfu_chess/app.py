# Repository: https://github.com/your-org/your-repo (placeholder)
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


def build_game_engine(rows, config: GameConfig) -> GameEngine:
    board = ArrayBoard(rows, empty_token=config.empty_token)
    state = GameState(board, config)
    rule_registry = create_default_chess_registry()
    promotion_rule = ConditionalPromotionRule(trigger=last_rank_trigger)
    rule_engine = RuleEngine(rule_registry, promotion_rule=promotion_rule)
    return GameEngine(state, rule_engine, config)


def run(data: str, config: Optional["GameConfig"] = None) -> str:
    """Parse input text, run its commands, and return the textual output.
    Kept separate from main() so it can be exercised directly in tests
    without touching stdin/stdout."""
    config = config or GameConfig()
    parser = BoardParser(config)

    try:
        rows, command_lines = parser.parse(data)
    except BoardError as e:
        return f"ERROR {e.code}\n"

    engine = build_game_engine(rows, config)
    command_registry = create_default_command_registry(config)
    command_registry.run(engine, command_lines)

    if engine.output_chunks:
        return '\n'.join(engine.output_chunks) + '\n'

    engine.settle()
    return engine.render() + '\n'


def main():
    data = sys.stdin.read()
    sys.stdout.write(run(data))


if __name__ == '__main__':  # pragma: no cover
    main()
