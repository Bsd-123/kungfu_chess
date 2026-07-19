import pytest

from kungfu_chess.model.board import ArrayBoard
from kungfu_chess.model.piece import Piece
from kungfu_chess.model.position import Position
from kungfu_chess.realtime.motion import PendingMove
from kungfu_chess.realtime.collision_handler import CollisionHandler
from kungfu_chess.rules.rule_engine import RuleEngine
from kungfu_chess.rules.rule_registry import create_default_chess_registry


class NoPromotion:
    def resolve_arrival_piece(self, piece, dst, board):
        return piece


def board_from(rows):
    return ArrayBoard(rows)


def move(src, dst, piece, board, complete_time=1000, cooldown_ms=0):
    m = PendingMove(move_type='move', complete_time=complete_time, src=src, piece=piece, dst=dst,
                     path=board.get_path(src, dst), cooldown_ms=cooldown_ms)
    return m


def test_resolve_move_lands_cleanly_no_obstruction():
    board = board_from([['wR', '.', '.']])
    piece = board.get_piece_at(Position(0, 0))
    m = move(Position(0, 0), Position(0, 2), piece, board)
    handler = CollisionHandler()
    event = handler.resolve_move(m, board, NoPromotion(), [])
    assert event.dst == Position(0, 2)
    assert event.captured_piece is None
    assert board.get_piece_at(Position(0, 2)) is not None
    assert board.get_piece_at(Position(0, 0)) is None


def test_resolve_move_captures_first_enemy_in_path():
    board = board_from([['wR', 'bP', '.']])
    piece = board.get_piece_at(Position(0, 0))
    m = move(Position(0, 0), Position(0, 2), piece, board)
    handler = CollisionHandler()
    event = handler.resolve_move(m, board, NoPromotion(), [])
    assert event.dst == Position(0, 1)
    assert event.captured_piece.type == 'P'
    assert board.get_piece_at(Position(0, 2)) is None


def test_resolve_move_truncates_before_friendly_blocker():
    board = board_from([['wR', 'wP', '.']])
    piece = board.get_piece_at(Position(0, 0))
    m = move(Position(0, 0), Position(0, 2), piece, board)
    handler = CollisionHandler()
    event = handler.resolve_move(m, board, NoPromotion(), [])
    assert event.dst == Position(0, 0)  # stuck immediately behind
    assert event.captured_piece is None
    assert board.get_piece_at(Position(0, 0)) is not None


def test_resolve_move_source_already_vacated_returns_none():
    board = board_from([['.', '.', '.']])  # nothing at src anymore
    piece = Piece(color='w', type='R', cell=Position(0, 0))
    m = move(Position(0, 0), Position(0, 2), piece, board)
    handler = CollisionHandler()
    event = handler.resolve_move(m, board, NoPromotion(), [])
    assert event is None


def test_resolve_move_applies_promotion_on_full_arrival():
    class QueenPromotion:
        def resolve_arrival_piece(self, piece, dst, board):
            return Piece(color=piece.color, type='Q', id=piece.id, cell=dst)

    board = board_from([['wP'], ['.'], ['.']])
    piece = board.get_piece_at(Position(0, 0))
    m = move(Position(0, 0), Position(2, 0), piece, board)
    handler = CollisionHandler()
    event = handler.resolve_move(m, board, QueenPromotion(), [])
    assert event.piece.type == 'Q'
    assert board.get_piece_at(Position(2, 0)).type == 'Q'


def test_resolve_move_no_promotion_when_truncated():
    class QueenPromotion:
        def resolve_arrival_piece(self, piece, dst, board):
            return Piece(color=piece.color, type='Q', id=piece.id, cell=dst)

    board = board_from([['wR', 'wP', '.']])
    piece = board.get_piece_at(Position(0, 0))
    m = move(Position(0, 0), Position(0, 2), piece, board)
    handler = CollisionHandler()
    event = handler.resolve_move(m, board, QueenPromotion(), [])
    assert event.piece.type == 'R'  # never reached dst, so no promotion


def test_resolve_move_walks_through_airborne_square_as_vacant():
    board = board_from([['wR', '.', '.']])
    piece = board.get_piece_at(Position(0, 0))
    m = move(Position(0, 0), Position(0, 2), piece, board)
    jumper = PendingMove(move_type='jump', complete_time=2000, src=Position(0, 1),
                          piece=Piece(color='b', type='N'))
    handler = CollisionHandler()
    event = handler.resolve_move(m, board, NoPromotion(), [jumper])
    assert event.dst == Position(0, 2)  # sailed straight through the hover


def test_resolve_move_does_not_land_on_friendly_hover_backs_up():
    board = board_from([['wR', '.', '.']])
    piece = board.get_piece_at(Position(0, 0))
    m = move(Position(0, 0), Position(0, 1), piece, board)
    jumper = PendingMove(move_type='jump', complete_time=2000, src=Position(0, 1),
                          piece=Piece(color='w', type='N'))
    handler = CollisionHandler()
    event = handler.resolve_move(m, board, NoPromotion(), [jumper])
    assert event.dst == Position(0, 0)  # can't land on friendly hover; stays put


def test_resolve_jump_landing_no_op_when_piece_still_there():
    board = board_from([['wN']])
    piece = board.get_piece_at(Position(0, 0))
    m = PendingMove(move_type='jump', complete_time=1000, src=Position(0, 0), piece=piece)
    handler = CollisionHandler()
    event = handler.resolve_jump_landing(m, board, [])
    assert event.dst == Position(0, 0)
    assert event.captured_piece is None
    assert event.reverted is False


def test_resolve_jump_landing_captures_enemy_occupant():
    piece = Piece(color='w', type='N', cell=Position(0, 0))
    board = board_from([['bP']])
    m = PendingMove(move_type='jump', complete_time=1000, src=Position(0, 0), piece=piece)
    handler = CollisionHandler()
    event = handler.resolve_jump_landing(m, board, [])
    assert event.captured_piece.type == 'P'
    assert board.get_piece_at(Position(0, 0)).type == 'N'


def test_resolve_jump_landing_reverted_when_friendly_occupies():
    piece = Piece(color='w', type='N', cell=Position(0, 0))
    board = board_from([['wP']])
    m = PendingMove(move_type='jump', complete_time=1000, src=Position(0, 0), piece=piece)
    handler = CollisionHandler()
    event = handler.resolve_jump_landing(m, board, [])
    assert event.reverted is True
    assert event.captured_piece is None
    assert board.get_piece_at(Position(0, 0)).type == 'P'  # untouched


def test_preview_landing_square_for_jump_returns_src():
    board = board_from([['wN']])
    piece = board.get_piece_at(Position(0, 0))
    m = PendingMove(move_type='jump', complete_time=1000, src=Position(0, 0), piece=piece)
    handler = CollisionHandler()
    assert handler.preview_landing_square(m, board, []) == Position(0, 0)


def test_preview_landing_square_for_move_matches_resolution():
    board = board_from([['wR', 'bP', '.']])
    piece = board.get_piece_at(Position(0, 0))
    m = move(Position(0, 0), Position(0, 2), piece, board)
    handler = CollisionHandler()
    assert handler.preview_landing_square(m, board, []) == Position(0, 1)


def test_preview_landing_square_move_with_no_dst_returns_src():
    board = board_from([['wR']])
    piece = board.get_piece_at(Position(0, 0))
    m = PendingMove(move_type='move', complete_time=1000, src=Position(0, 0), piece=piece, dst=None)
    handler = CollisionHandler()
    assert handler.preview_landing_square(m, board, []) == Position(0, 0)
