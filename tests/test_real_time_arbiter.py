import pytest

from kungfu_chess.config import GameConfig
from kungfu_chess.model.board import ArrayBoard
from kungfu_chess.model.piece import Piece
from kungfu_chess.model.position import Position
from kungfu_chess.realtime.motion import PendingMove
from kungfu_chess.realtime.real_time_arbiter import RealTimeArbiter


def board3():
    return ArrayBoard([['.'] * 3 for _ in range(3)])


def test_schedule_move_and_queries():
    arb = RealTimeArbiter()
    board = board3()
    piece = Piece(color='w', type='R')
    arb.schedule_move(Position(0, 0), Position(0, 2), piece, clock_ms=0, duration_ms=1000, board=board)
    assert arb.is_piece_busy(Position(0, 0), 500) is True
    assert arb.is_target_busy(Position(0, 2), 500) is True
    assert arb.is_piece_busy(Position(0, 0), 1000) is False


def test_schedule_jump_and_airborne_query():
    arb = RealTimeArbiter()
    piece = Piece(color='w', type='K')
    arb.schedule_jump(Position(1, 1), piece, clock_ms=0, duration_ms=1000)
    assert arb.is_active_airborne_at(Position(1, 1), 500) is True


def test_cooldown_queries_delegate():
    arb = RealTimeArbiter()
    assert arb.is_cooling_down(Position(0, 0), 0) is False
    assert arb.cooldown_progress(Position(0, 0), 0) is None


def test_start_cooldown_for_noop_when_zero():
    arb = RealTimeArbiter()
    board = board3()
    piece = Piece(color='w', type='R')
    arb.schedule_move(Position(0, 0), Position(0, 1), piece, clock_ms=0, duration_ms=100, board=board)
    m = arb.next_due_motions(100)[0]
    arb.start_cooldown_for(m, Position(0, 1))
    assert arb.is_cooling_down(Position(0, 1), 100) is False


def test_start_cooldown_for_applies_when_positive():
    arb = RealTimeArbiter()
    board = board3()
    piece = Piece(color='w', type='R')
    arb.schedule_move(Position(0, 0), Position(0, 1), piece, clock_ms=0, duration_ms=100,
                       board=board, cooldown_ms=500)
    m = arb.next_due_motions(100)[0]
    arb.start_cooldown_for(m, Position(0, 1))
    assert arb.is_cooling_down(Position(0, 1), 100) is True
    assert arb.is_cooling_down(Position(0, 1), 600) is False


def test_pending_moves_property():
    arb = RealTimeArbiter()
    board = board3()
    piece = Piece(color='w', type='R')
    assert arb.pending_moves == []
    arb.schedule_move(Position(0, 0), Position(0, 1), piece, clock_ms=0, duration_ms=100, board=board)
    assert len(arb.pending_moves) == 1


def test_has_pending_motions_reflects_scheduled_moves():
    arb = RealTimeArbiter()
    board = board3()
    piece = Piece(color='w', type='R')
    assert arb.has_pending_motions() is False
    arb.schedule_move(Position(0, 0), Position(0, 1), piece, clock_ms=0, duration_ms=100, board=board)
    assert arb.has_pending_motions() is True


def test_has_active_cooldown_delegates():
    arb = RealTimeArbiter()
    assert arb.has_active_cooldown(0) is False
    m = PendingMove(move_type=GameConfig.MOTION_STATE_MOVE, complete_time=100,
                     src=Position(0, 0), piece=Piece(color='w', type='R'), cooldown_ms=500)
    arb.start_cooldown_for(m, Position(0, 1))
    assert arb.has_active_cooldown(100) is True
    assert arb.has_active_cooldown(600) is False


def test_next_due_motions_and_clear_expired():
    arb = RealTimeArbiter()
    board = board3()
    piece = Piece(color='w', type='R')
    arb.schedule_move(Position(0, 0), Position(0, 1), piece, clock_ms=0, duration_ms=100, board=board)
    assert arb.next_due_motions(50) == []
    due = arb.next_due_motions(100)
    assert len(due) == 1
    assert len(arb.pending_moves) == 1  # still visible until clear_expired
    arb.clear_expired(100)
    assert arb.pending_moves == []


def test_extend_hovers_for_crossings_pushes_out_friendly_jump():
    arb = RealTimeArbiter()
    board = board3()
    mover = Piece(color='w', type='R')
    jumper = Piece(color='w', type='N')
    # Jump at (0,1); a friendly rook slides from (0,0) to (0,2), passing through (0,1).
    arb.schedule_jump(Position(0, 1), jumper, clock_ms=0, duration_ms=100)
    arb.schedule_move(Position(0, 0), Position(0, 2), mover, clock_ms=0, duration_ms=500, board=board)
    # jump gets extended because the mover's path crosses its square
    assert arb.next_due_motions(100) == []
    due = arb.next_due_motions(500)
    move_types = sorted(m.move_type for m in due)
    assert move_types == ['jump', 'move']


def test_extend_hovers_ignores_enemy_crossings():
    arb = RealTimeArbiter()
    board = board3()
    mover = Piece(color='b', type='R')  # enemy of the jumper
    jumper = Piece(color='w', type='N')
    arb.schedule_jump(Position(0, 1), jumper, clock_ms=0, duration_ms=100)
    arb.schedule_move(Position(0, 0), Position(0, 2), mover, clock_ms=0, duration_ms=500, board=board)
    due = arb.next_due_motions(100)
    assert len(due) == 1
    assert due[0].move_type == 'jump'


def test_extend_hovers_ignores_terminal_square_of_mover_path():
    arb = RealTimeArbiter()
    board = board3()
    mover = Piece(color='w', type='R')
    jumper = Piece(color='w', type='N')
    # jumper sits on the mover's terminal square, not mid-path -- no extension
    arb.schedule_jump(Position(0, 2), jumper, clock_ms=0, duration_ms=100)
    arb.schedule_move(Position(0, 0), Position(0, 2), mover, clock_ms=0, duration_ms=500, board=board)
    due = arb.next_due_motions(100)
    assert len(due) == 1
    assert due[0].move_type == 'jump'


def test_next_due_motions_noop_when_no_jumps_pending():
    arb = RealTimeArbiter()
    board = board3()
    mover = Piece(color='w', type='R')
    arb.schedule_move(Position(0, 0), Position(0, 2), mover, clock_ms=0, duration_ms=100, board=board)
    due = arb.next_due_motions(100)
    assert len(due) == 1
