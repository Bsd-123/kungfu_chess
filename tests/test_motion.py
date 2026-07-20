import pytest

from kungfu_chess.model.piece import Piece
from kungfu_chess.model.position import Position
from kungfu_chess.realtime.motion import PendingMove, SettlementEvent, MoveScheduler


def make_move(src=Position(0, 0), dst=Position(0, 1), complete_time=1000, move_type='move', **kw):
    return PendingMove(move_type=move_type, complete_time=complete_time, src=src,
                        piece=Piece(color='w', type='P'), dst=dst, **kw)


def test_pending_move_defaults():
    m = make_move()
    assert m.start_time == 0
    assert m.path == []
    assert m.seq == 0
    assert m.cooldown_ms == 0


def test_extend_completion_to_pushes_later():
    m = make_move(complete_time=1000)
    m.extend_completion_to(2000)
    assert m.complete_time == 2000


def test_extend_completion_to_never_pulls_earlier():
    m = make_move(complete_time=1000)
    m.extend_completion_to(500)
    assert m.complete_time == 1000


def test_settlement_event_dry_view_properties():
    piece = Piece(color='w', type='Q')
    captured = Piece(color='b', type='P')
    event = SettlementEvent(src=Position(0, 0), dst=Position(0, 1), piece=piece,
                             captured_piece=captured)
    assert event.piece_color == 'w'
    assert event.piece_kind == 'Q'
    assert event.captured_piece_kind == 'P'


def test_settlement_event_no_capture_kind_is_none():
    piece = Piece(color='w', type='Q')
    event = SettlementEvent(src=Position(0, 0), dst=Position(0, 1), piece=piece, captured_piece=None)
    assert event.captured_piece_kind is None


def test_settlement_event_defaults():
    piece = Piece(color='w', type='Q')
    event = SettlementEvent(src=Position(0, 0), dst=Position(0, 1), piece=piece, captured_piece=None)
    assert event.move_type == 'move'
    assert event.requested_dst is None
    assert event.reverted is False


# -- MoveScheduler --------------------------------------------------------

def test_schedule_assigns_increasing_seq():
    s = MoveScheduler()
    m1 = make_move()
    m2 = make_move()
    s.schedule(m1)
    s.schedule(m2)
    assert m2.seq > m1.seq


def test_is_piece_busy_true_while_pending():
    s = MoveScheduler()
    s.schedule(make_move(complete_time=1000))
    assert s.is_piece_busy(Position(0, 0), 500) is True
    assert s.is_piece_busy(Position(0, 0), 1000) is False  # due, no longer "still pending"


def test_is_target_busy_only_for_moves_not_jumps():
    s = MoveScheduler()
    s.schedule(make_move(move_type='jump', dst=None, complete_time=1000))
    assert s.is_target_busy(Position(0, 1), 500) is False


def test_is_target_busy_true_for_pending_move():
    s = MoveScheduler()
    s.schedule(make_move(dst=Position(0, 1), complete_time=1000))
    assert s.is_target_busy(Position(0, 1), 500) is True


def test_is_active_airborne_at_true_for_pending_jump():
    s = MoveScheduler()
    s.schedule(make_move(move_type='jump', dst=None, complete_time=1000))
    assert s.is_active_airborne_at(Position(0, 0), 500) is True
    assert s.is_active_airborne_at(Position(0, 0), 1001) is False


def test_due_moves_only_returns_moves_past_complete_time():
    s = MoveScheduler()
    m = make_move(complete_time=1000)
    s.schedule(m)
    assert s.due_moves(999) == []
    assert s.due_moves(1000) == [m]


def test_due_jumps_only_returns_jumps():
    s = MoveScheduler()
    j = make_move(move_type='jump', dst=None, complete_time=1000)
    s.schedule(j)
    assert s.due_jumps(1000) == [j]
    assert s.due_moves(1000) == []


def test_due_motions_merges_moves_and_jumps_chronologically():
    s = MoveScheduler()
    j = make_move(move_type='jump', dst=None, complete_time=1000, src=Position(1, 1))
    m = make_move(complete_time=500)
    s.schedule(j)
    s.schedule(m)
    due = s.due_motions(1000)
    assert due == [m, j]


def test_clear_expired_removes_only_due_ones():
    s = MoveScheduler()
    m1 = make_move(complete_time=500)
    m2 = make_move(complete_time=1500, src=Position(2, 2))
    s.schedule(m1)
    s.schedule(m2)
    s.clear_expired(1000)
    assert s.pending_moves == [m2]


def test_pending_moves_returns_a_copy():
    s = MoveScheduler()
    s.schedule(make_move())
    lst = s.pending_moves
    lst.clear()
    assert len(s.pending_moves) == 1


def test_cooldown_lifecycle():
    s = MoveScheduler()
    assert s.is_cooling_down(Position(0, 0), 0) is False
    assert s.cooldown_progress(Position(0, 0), 0) is None
    s.start_cooldown(Position(0, 0), until_ms=1000, duration_ms=1000)
    assert s.is_cooling_down(Position(0, 0), 500) is True
    assert s.is_cooling_down(Position(0, 0), 1000) is False
    progress = s.cooldown_progress(Position(0, 0), 500)
    assert progress == pytest.approx(0.5)


def test_cooldown_progress_none_once_finished():
    s = MoveScheduler()
    s.start_cooldown(Position(0, 0), until_ms=1000, duration_ms=1000)
    assert s.cooldown_progress(Position(0, 0), 1000) is None


def test_cooldown_progress_guards_nonpositive_duration():
    s = MoveScheduler()
    s.start_cooldown(Position(0, 0), until_ms=1000, duration_ms=0)
    assert s.cooldown_progress(Position(0, 0), 500) is None


def test_has_active_cooldown_false_with_no_cooldowns():
    s = MoveScheduler()
    assert s.has_active_cooldown(0) is False


def test_has_active_cooldown_true_while_any_position_cooling_down():
    s = MoveScheduler()
    s.start_cooldown(Position(0, 0), until_ms=1000, duration_ms=1000)
    assert s.has_active_cooldown(500) is True
    assert s.has_active_cooldown(1000) is False
