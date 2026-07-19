from kungfu_chess.model.board import ArrayBoard
from kungfu_chess.model.game_state import GameState
from kungfu_chess.model.position import Position
from kungfu_chess.config import GameConfig
from kungfu_chess.engine.snapshot_builder import SnapshotBuilder
from kungfu_chess.realtime.collision_handler import CollisionHandler


def make_builder(rows, config=None):
    board = ArrayBoard(rows)
    state = GameState(board, config or GameConfig())
    handler = CollisionHandler()
    return SnapshotBuilder(state, config or GameConfig(), handler), state


def test_build_snapshot_dimensions_and_selection():
    rows = [['wK', '.'], ['.', 'bK']]
    builder, state = make_builder(rows)
    state.selected = Position(0, 0)
    snap = builder.build()
    assert snap.board_width == 2
    assert snap.board_height == 2
    assert snap.selected == Position(0, 0)
    assert snap.game_over is False
    assert snap.winner is None


def test_build_snapshot_idle_piece_state():
    rows = [['wK', '.'], ['.', '.']]
    builder, state = make_builder(rows)
    snap = builder.build()
    assert len(snap.pieces) == 1
    p = snap.pieces[0]
    assert p.kind == 'K'
    assert p.color == 'w'
    assert p.state == GameConfig.MOTION_STATE_IDLE
    assert p.motion_progress == 1.0
    assert p.dst_pixel_x is None
    assert p.cooldown_progress is None


def test_build_snapshot_pending_move_progress_and_preview():
    rows = [['wR', '.', '.']]
    config = GameConfig()
    builder, state = make_builder(rows, config)
    piece = state.board.get_piece_at(Position(0, 0))
    state.schedule_move(Position(0, 0), Position(0, 2), piece, duration_ms=1000)
    state.advance_clock(500)
    snap = builder.build()
    moving = [p for p in snap.pieces if p.state == GameConfig.MOTION_STATE_MOVE][0]
    assert 0.0 < moving.motion_progress < 1.0
    assert moving.dst_pixel_x == 2 * config.cell_pixel_size
    assert moving.dst_pixel_y == 0


def test_build_snapshot_pending_jump_state():
    rows = [['wK']]
    builder, state = make_builder(rows)
    piece = state.board.get_piece_at(Position(0, 0))
    state.schedule_jump(Position(0, 0), piece, duration_ms=1000)
    snap = builder.build()
    jumping = snap.pieces[0]
    assert jumping.state == GameConfig.MOTION_STATE_JUMP
    assert jumping.dst_pixel_x is None


def test_build_snapshot_cooldown_progress_reflected():
    rows = [['wR', '.']]
    builder, state = make_builder(rows)
    piece = state.board.get_piece_at(Position(0, 0))
    state.schedule_move(Position(0, 0), Position(0, 1), piece, duration_ms=100, cooldown_ms=1000)
    state.advance_clock(101)
    due = state.arbiter.next_due_motions(state.clock_ms)
    state.arbiter.start_cooldown_for(due[0], Position(0, 1))
    state.arbiter.clear_expired(state.clock_ms)
    board = state.board
    board.set_piece_at(Position(0, 1), piece)
    board.set_piece_at(Position(0, 0), None)
    builder2 = SnapshotBuilder(state, GameConfig(), CollisionHandler())
    snap = builder2.build()
    p = [p for p in snap.pieces][0]
    assert p.cooldown_progress is not None


def test_build_snapshot_game_over_and_winner_reflected():
    rows = [['wK']]
    builder, state = make_builder(rows)
    state.mark_game_over('b')
    snap = builder.build()
    assert snap.game_over is True
    assert snap.winner == 'b'
