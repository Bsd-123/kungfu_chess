from kungfu_chess.model.position import Position
from kungfu_chess.network.remote_board_mirror import RemoteBoardMirror
from kungfu_chess.ui.events.events import JumpResolvedEvent, MoveResolvedEvent


def test_starts_from_standard_start_position():
    board = RemoteBoardMirror()
    piece = board.get_piece_at(Position(6, 0))
    assert piece.color == 'w'
    assert piece.type == 'P'
    assert board.get_piece_at(Position(4, 4)) is None


def test_move_resolved_moves_piece_from_src_to_dst():
    board = RemoteBoardMirror()
    board.on_move_resolved(MoveResolvedEvent(
        piece_color='w', piece_kind='P', src_row=6, src_col=0,
        dst_row=5, dst_col=0, captured_piece_kind=None))
    assert board.get_piece_at(Position(6, 0)) is None
    dst_piece = board.get_piece_at(Position(5, 0))
    assert dst_piece.color == 'w'
    assert dst_piece.type == 'P'


def test_move_resolved_with_capture_overwrites_destination():
    board = RemoteBoardMirror()
    # White pawn e2-e4-ish scenario: place a black piece at the destination first.
    board.on_move_resolved(MoveResolvedEvent(
        piece_color='w', piece_kind='P', src_row=6, src_col=0,
        dst_row=1, dst_col=1, captured_piece_kind='P'))
    dst_piece = board.get_piece_at(Position(1, 1))
    assert dst_piece.color == 'w'
    assert dst_piece.type == 'P'
    assert board.get_piece_at(Position(6, 0)) is None


def test_jump_resolved_places_piece_at_its_own_square():
    board = RemoteBoardMirror()
    board.on_jump_resolved(JumpResolvedEvent(
        piece_color='w', piece_kind='N', row=7, col=1, captured_piece_kind=None))
    piece = board.get_piece_at(Position(7, 1))
    assert piece.color == 'w'
    assert piece.type == 'N'


def test_jump_resolved_with_capture_overwrites_own_square():
    board = RemoteBoardMirror()
    board.on_jump_resolved(JumpResolvedEvent(
        piece_color='w', piece_kind='N', row=7, col=1, captured_piece_kind='B'))
    piece = board.get_piece_at(Position(7, 1))
    assert piece.color == 'w'
    assert piece.type == 'N'


def test_is_within_bounds_and_get_piece_at_satisfy_board_interface():
    board = RemoteBoardMirror()
    assert board.is_within_bounds(Position(0, 0)) is True
    assert board.is_within_bounds(Position(8, 0)) is False
    assert board.get_piece_at(Position(8, 0)) is None
