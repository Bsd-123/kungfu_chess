"""Tests for GameEngine orchestration layer."""
import pytest

from kungfu_chess.model.board import ArrayBoard
from kungfu_chess.config import GameConfig
from kungfu_chess.model.game_state import GameState
from kungfu_chess.model.piece import Piece
from kungfu_chess.model.position import Position
from kungfu_chess.engine.game_engine import GameEngine
from kungfu_chess.engine.move_reasons import MoveReasons
from kungfu_chess.rules.rule_engine import RuleEngine
from kungfu_chess.rules.rule_registry import create_default_chess_registry
from kungfu_chess.rules.promotion_rules import ConditionalPromotionRule, last_rank_trigger
from kungfu_chess.rules.win_condition import CapturedTypeWinCondition


def make_engine(rows=None, config=None):
    rows = rows or [['.'] * 8 for _ in range(8)]
    config = config or GameConfig()
    board = ArrayBoard(rows, empty_token=config.empty_token)
    state = GameState(board, config)
    registry = create_default_chess_registry()
    promo = ConditionalPromotionRule(trigger=last_rank_trigger)
    rule_engine = RuleEngine(registry, promotion_rule=promo)
    win_condition = CapturedTypeWinCondition(config.win_condition_piece_types)
    return GameEngine(state, rule_engine, config, win_condition=win_condition)


def test_request_move_ok_and_schedules():
    rows = [['.'] * 8 for _ in range(8)]
    rows[6][0] = 'wP'
    engine = make_engine(rows)
    result = engine.request_move(Position(6, 0), Position(5, 0))
    assert bool(result) is True
    assert result.reason == MoveReasons.OK
    # piece hasn't landed yet (motion in flight)
    assert engine.board.get_piece_at(Position(6, 0)) is not None


def test_request_move_illegal_returns_false_with_reason():
    rows = [['.'] * 8 for _ in range(8)]
    rows[6][0] = 'wP'
    engine = make_engine(rows)
    result = engine.request_move(Position(6, 0), Position(3, 0))
    assert bool(result) is False
    assert result.reason != MoveReasons.OK


def test_request_move_no_piece_at_source():
    engine = make_engine()
    result = engine.request_move(Position(0, 0), Position(1, 0))
    assert bool(result) is False


def test_request_move_target_busy_blocks_second_mover():
    rows = [['.'] * 8 for _ in range(8)]
    rows[6][0] = 'wP'
    rows[6][2] = 'wP'
    engine = make_engine(rows)
    r1 = engine.request_move(Position(6, 0), Position(5, 0))
    assert bool(r1) is True
    # same piece can't move again while in flight
    r2 = engine.request_move(Position(6, 0), Position(4, 0))
    assert bool(r2) is False


def test_request_jump_moves_piece_state():
    rows = [['.'] * 8 for _ in range(8)]
    rows[6][0] = 'wP'
    engine = make_engine(rows)
    assert engine.request_jump(Position(6, 0)) is True


def test_request_jump_no_piece_returns_false():
    engine = make_engine()
    assert engine.request_jump(Position(0, 0)) is False


def test_request_jump_while_busy_returns_false():
    rows = [['.'] * 8 for _ in range(8)]
    rows[6][0] = 'wP'
    engine = make_engine(rows)
    assert engine.request_jump(Position(6, 0)) is True
    assert engine.request_jump(Position(6, 0)) is False


def test_legal_destinations_delegates():
    rows = [['.'] * 8 for _ in range(8)]
    rows[6][0] = 'wP'
    engine = make_engine(rows)
    dests = engine.legal_destinations(Position(6, 0))
    assert Position(5, 0) in dests


def test_advance_clock_settles_due_motions():
    rows = [['.'] * 8 for _ in range(8)]
    rows[6][0] = 'wP'
    config = GameConfig()
    engine = make_engine(rows, config)
    engine.request_move(Position(6, 0), Position(5, 0))
    duration = config.move_duration_for('P')
    engine.advance_clock(duration)
    assert engine.board.get_piece_at(Position(5, 0)) is not None
    assert engine.board.get_piece_at(Position(6, 0)) is None


def test_settle_without_due_motions_is_noop():
    engine = make_engine()
    engine.settle()  # should not raise
    assert engine.output_chunks == []


def test_win_condition_sets_game_over():
    rows = [['.'] * 8 for _ in range(8)]
    rows[7][0] = 'wR'
    rows[0][0] = 'bK'
    config = GameConfig()
    engine = make_engine(rows, config)
    # slide rook straight up the file to capture the king
    for src_r in range(7, 0, -1):
        pass
    result = engine.request_move(Position(7, 0), Position(0, 0))
    assert bool(result) is True
    duration = config.move_duration_for('R') * 7
    engine.advance_clock(duration)
    assert engine.game_over is True
    assert engine.snapshot().winner == 'w'


def test_selected_property_getter_setter():
    engine = make_engine()
    assert engine.selected is None
    engine.selected = Position(1, 1)
    assert engine.selected == Position(1, 1)


def test_is_piece_busy_and_target_busy_and_cooling_down():
    rows = [['.'] * 8 for _ in range(8)]
    rows[6][0] = 'wP'
    config = GameConfig()
    engine = make_engine(rows, config)
    assert engine.is_piece_busy(Position(6, 0)) is False
    engine.request_move(Position(6, 0), Position(5, 0))
    assert engine.is_piece_busy(Position(6, 0)) is True
    assert engine.is_target_busy(Position(5, 0)) is True
    assert engine.is_cooling_down(Position(6, 0)) is False


def test_add_settlement_listener_invoked_on_settle():
    rows = [['.'] * 8 for _ in range(8)]
    rows[6][0] = 'wP'
    config = GameConfig()
    engine = make_engine(rows, config)
    events = []
    engine.add_settlement_listener(lambda e: events.append(e))
    engine.request_move(Position(6, 0), Position(5, 0))
    engine.advance_clock(config.move_duration_for('P'))
    assert len(events) == 1


def test_render_returns_text():
    engine = make_engine()
    text = engine.render()
    assert isinstance(text, str)
    assert len(text) > 0


def test_snapshot_returns_game_snapshot():
    engine = make_engine()
    snap = engine.snapshot()
    assert snap is not None


def test_clock_ms_starts_zero():
    engine = make_engine()
    assert engine.clock_ms == 0


def test_game_ended_listener_fires_exactly_once_on_win_never_on_ordinary_move():
    rows = [['.'] * 8 for _ in range(8)]
    rows[7][0] = 'wR'
    rows[0][0] = 'bK'
    rows[6][3] = 'wP'
    config = GameConfig()
    engine = make_engine(rows, config)
    calls = []
    engine.add_game_ended_listener(lambda winner, clock_ms: calls.append((winner, clock_ms)))

    # Ordinary move (no capture) must not fire the listener.
    engine.request_move(Position(6, 3), Position(5, 3))
    engine.advance_clock(config.move_duration_for('P'))
    assert calls == []

    # Rook slides up the file to capture the king -- a real win condition.
    engine.request_move(Position(7, 0), Position(0, 0))
    duration = config.move_duration_for('R') * 7
    engine.advance_clock(duration)
    assert len(calls) == 1
    assert calls[0][0] == 'w'
    assert engine.game_over is True
