from kungfu_chess.model.board import ArrayBoard
from kungfu_chess.model.game_state import GameState
from kungfu_chess.model.piece import Piece
from kungfu_chess.model.position import Position
from kungfu_chess.config import GameConfig


def make_state(rows=None, config=None):
    if rows is None:
        rows = [['wR', '.', '.'], ['.', '.', '.'], ['.', '.', 'bK']]
    return GameState(ArrayBoard(rows), config or GameConfig())


def test_nrows_ncols_delegate_to_board():
    s = make_state()
    assert s.nrows == 3
    assert s.ncols == 3


def test_clock_starts_at_zero_and_advances():
    s = make_state()
    assert s.clock_ms == 0
    s.advance_clock(500)
    assert s.clock_ms == 500
    s.advance_clock(250)
    assert s.clock_ms == 750


def test_game_over_defaults_false_and_winner_none():
    s = make_state()
    assert s.game_over is False
    assert s.winner_color is None


def test_mark_game_over_sets_both_atomically():
    s = make_state()
    s.mark_game_over('w')
    assert s.game_over is True
    assert s.winner_color == 'w'


def test_default_arbiter_created_when_none_given():
    s = make_state()
    assert s.arbiter is not None


def test_selected_default_none_and_writable():
    s = make_state()
    assert s.selected is None
    s.selected = Position(0, 0)
    assert s.selected == Position(0, 0)


def test_output_chunks_starts_empty_list():
    s = make_state()
    assert s.output_chunks == []


def test_is_piece_busy_false_when_nothing_scheduled():
    s = make_state()
    assert s.is_piece_busy(Position(0, 0)) is False


def test_is_target_busy_false_when_nothing_scheduled():
    s = make_state()
    assert s.is_target_busy(Position(1, 1)) is False


def test_is_active_airborne_at_false_when_nothing_scheduled():
    s = make_state()
    assert s.is_active_airborne_at(Position(0, 0)) is False


def test_is_cooling_down_false_by_default():
    s = make_state()
    assert s.is_cooling_down(Position(0, 0)) is False


def test_schedule_move_makes_source_busy_and_target_busy():
    s = make_state()
    piece = s.board.get_piece_at(Position(0, 0))
    s.schedule_move(Position(0, 0), Position(0, 1), piece, duration_ms=1000)
    assert s.is_piece_busy(Position(0, 0)) is True
    assert s.is_target_busy(Position(0, 1)) is True


def test_schedule_move_no_longer_busy_after_clock_advances_past_duration():
    s = make_state()
    piece = s.board.get_piece_at(Position(0, 0))
    s.schedule_move(Position(0, 0), Position(0, 1), piece, duration_ms=1000)
    s.advance_clock(1001)
    assert s.is_piece_busy(Position(0, 0)) is False


def test_schedule_jump_makes_position_airborne():
    s = make_state()
    piece = s.board.get_piece_at(Position(0, 0))
    s.schedule_jump(Position(0, 0), piece, duration_ms=1000)
    assert s.is_active_airborne_at(Position(0, 0)) is True


def test_schedule_move_with_cooldown_starts_cooldown_after_arbiter_start_cooldown_for():
    s = make_state()
    piece = s.board.get_piece_at(Position(0, 0))
    s.schedule_move(Position(0, 0), Position(0, 1), piece, duration_ms=100, cooldown_ms=500)
    s.advance_clock(101)
    due = s.arbiter.next_due_motions(s.clock_ms)
    assert len(due) == 1
    s.arbiter.start_cooldown_for(due[0], Position(0, 1))
    assert s.is_cooling_down(Position(0, 1)) is True
