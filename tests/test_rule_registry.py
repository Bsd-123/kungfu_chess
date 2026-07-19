from kungfu_chess.model.board import ArrayBoard
from kungfu_chess.model.piece import Piece
from kungfu_chess.model.position import Position
from kungfu_chess.rules.rule_registry import RuleRegistry, create_default_chess_registry
from kungfu_chess.rules.piece_rules import KingMovementRule


def board3():
    return ArrayBoard([['.'] * 3 for _ in range(3)])


def test_register_and_get_rule():
    registry = RuleRegistry()
    rule = KingMovementRule()
    registry.register('K', rule)
    assert registry.get_rule('K') is rule


def test_get_rule_missing_returns_none():
    registry = RuleRegistry()
    assert registry.get_rule('Z') is None


def test_constructor_accepts_initial_rules_dict():
    rule = KingMovementRule()
    registry = RuleRegistry(rules={'K': rule})
    assert registry.get_rule('K') is rule


def test_constructor_copies_input_dict():
    rule = KingMovementRule()
    original = {'K': rule}
    registry = RuleRegistry(rules=original)
    registry.register('Q', KingMovementRule())
    assert 'Q' not in original


def test_is_legal_move_delegates_to_registered_rule():
    registry = RuleRegistry()
    registry.register('K', KingMovementRule())
    board = board3()
    piece = Piece(color='w', type='K')
    assert registry.is_legal_move(board, piece, Position(0, 0), Position(1, 1)) is True
    assert registry.is_legal_move(board, piece, Position(0, 0), Position(2, 2)) is False


def test_is_legal_move_returns_false_when_no_rule_registered():
    registry = RuleRegistry()
    board = board3()
    piece = Piece(color='w', type='Z')
    assert registry.is_legal_move(board, piece, Position(0, 0), Position(1, 1)) is False


def test_create_default_chess_registry_has_all_piece_types():
    registry = create_default_chess_registry()
    for t in ('K', 'Q', 'R', 'B', 'N', 'P'):
        assert registry.get_rule(t) is not None
