from kungfu_chess.model.board import ArrayBoard
from kungfu_chess.model.game_state import GameState
from kungfu_chess.model.position import Position
from kungfu_chess.config import GameConfig
from kungfu_chess.engine.motion_gate import MotionGate
from kungfu_chess.engine.legal_destinations import LegalDestinationsCalculator
from kungfu_chess.rules.rule_engine import RuleEngine
from kungfu_chess.rules.rule_registry import create_default_chess_registry


def make_calc(rows):
    board = ArrayBoard(rows)
    state = GameState(board, GameConfig())
    rule_engine = RuleEngine(create_default_chess_registry())
    gate = MotionGate(state)
    return LegalDestinationsCalculator(state, rule_engine, gate), state


def test_empty_source_returns_no_destinations():
    rows = [['.', '.', '.'], ['.', '.', '.'], ['.', '.', '.']]
    calc, state = make_calc(rows)
    assert calc.compute(Position(0, 0)) == []


def test_king_destinations_include_source_for_jump():
    rows = [['.', '.', '.'], ['.', 'wK', '.'], ['.', '.', '.']]
    calc, state = make_calc(rows)
    dests = calc.compute(Position(1, 1))
    assert Position(1, 1) in dests  # jump-in-place always available
    assert Position(0, 0) in dests
    assert Position(0, 2) in dests
    assert len(dests) == 9  # 8 king moves + itself


def test_blocked_by_motion_gate_returns_empty():
    rows = [['.', '.', '.'], ['.', 'wK', '.'], ['.', '.', '.']]
    calc, state = make_calc(rows)
    piece = state.board.get_piece_at(Position(1, 1))
    state.schedule_move(Position(1, 1), Position(0, 0), piece, duration_ms=1000)
    assert calc.compute(Position(1, 1)) == []


def test_rook_ray_truncates_at_first_blocker():
    rows = [
        ['wR', '.', 'wP', '.'],
    ]
    calc, state = make_calc(rows)
    dests = calc.compute(Position(0, 0))
    # Should reach the square right before the friendly blocker, not past it.
    assert Position(0, 1) in dests
    assert Position(0, 2) not in dests
    assert Position(0, 3) not in dests


def test_rook_ray_includes_enemy_capture_square_but_not_beyond():
    rows = [
        ['wR', '.', 'bP', '.'],
    ]
    calc, state = make_calc(rows)
    dests = calc.compute(Position(0, 0))
    assert Position(0, 2) in dests  # capture square reachable
    assert Position(0, 3) not in dests  # nothing beyond a capture


def test_target_busy_square_excluded():
    rows = [
        ['wR', '.', '.', 'wN'],
        ['.', '.', '.', '.'],
    ]
    calc, state = make_calc(rows)
    knight = state.board.get_piece_at(Position(0, 3))
    # Schedule the knight to move onto (0, 1) -- claiming it as a target.
    state.schedule_move(Position(0, 3), Position(0, 1), knight, duration_ms=1000)
    dests = calc.compute(Position(0, 0))
    assert Position(0, 1) not in dests
