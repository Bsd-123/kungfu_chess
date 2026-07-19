from kungfu_chess.model.board import ArrayBoard
from kungfu_chess.model.game_state import GameState
from kungfu_chess.model.position import Position
from kungfu_chess.config import GameConfig
from kungfu_chess.engine.motion_gate import MotionGate
from kungfu_chess.engine.move_reasons import MoveReasons


def make_state():
    board = ArrayBoard([['wR', '.', '.'], ['.', '.', '.'], ['.', '.', 'bK']])
    return GameState(board, GameConfig())


def test_blocked_reason_none_when_clear():
    state = make_state()
    gate = MotionGate(state)
    assert gate.blocked_reason(Position(0, 0)) is None


def test_blocked_reason_game_over():
    state = make_state()
    state.mark_game_over('w')
    gate = MotionGate(state)
    assert gate.blocked_reason(Position(0, 0)) == MoveReasons.GAME_OVER


def test_blocked_reason_motion_in_progress():
    state = make_state()
    piece = state.board.get_piece_at(Position(0, 0))
    state.schedule_move(Position(0, 0), Position(0, 1), piece, duration_ms=1000)
    gate = MotionGate(state)
    assert gate.blocked_reason(Position(0, 0)) == MoveReasons.MOTION_IN_PROGRESS


def test_blocked_reason_cooldown():
    state = make_state()
    piece = state.board.get_piece_at(Position(0, 0))
    state.schedule_move(Position(0, 0), Position(0, 1), piece, duration_ms=100, cooldown_ms=1000)
    state.advance_clock(101)
    due = state.arbiter.next_due_motions(state.clock_ms)
    state.arbiter.start_cooldown_for(due[0], Position(0, 1))
    gate = MotionGate(state)
    assert gate.blocked_reason(Position(0, 1)) == MoveReasons.COOLDOWN


def test_game_over_takes_priority_over_busy():
    state = make_state()
    piece = state.board.get_piece_at(Position(0, 0))
    state.schedule_move(Position(0, 0), Position(0, 1), piece, duration_ms=1000)
    state.mark_game_over('w')
    gate = MotionGate(state)
    assert gate.blocked_reason(Position(0, 0)) == MoveReasons.GAME_OVER
