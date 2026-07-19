from kungfu_chess.input.controller import Controller
from kungfu_chess.model.board import ArrayBoard
from kungfu_chess.config import GameConfig
from kungfu_chess.model.game_state import GameState
from kungfu_chess.model.position import Position
from kungfu_chess.rules.rule_engine import RuleEngine
from kungfu_chess.rules.rule_registry import create_default_chess_registry
from kungfu_chess.rules.promotion_rules import ConditionalPromotionRule, last_rank_trigger
from kungfu_chess.engine.game_engine import GameEngine


def make_engine(rows=None):
    rows = rows or [['.'] * 8 for _ in range(8)]
    config = GameConfig()
    board = ArrayBoard(rows, empty_token=config.empty_token)
    state = GameState(board, config)
    registry = create_default_chess_registry()
    promo = ConditionalPromotionRule(trigger=last_rank_trigger)
    rule_engine = RuleEngine(registry, promotion_rule=promo)
    return GameEngine(state, rule_engine, config)


def test_click_outside_board_when_nothing_selected():
    engine = make_engine()
    controller = Controller(engine, 100)
    controller.click(-50, -50)
    assert controller.selected is None


def test_click_empty_cell_selects_nothing():
    engine = make_engine()
    controller = Controller(engine, 100)
    controller.click(0, 0)
    assert controller.selected is None


def test_click_piece_selects_it():
    rows = [['.'] * 8 for _ in range(8)]
    rows[6][0] = 'wP'
    engine = make_engine(rows)
    controller = Controller(engine, 100)
    controller.click(0, 600)  # x=0 -> col 0, y=600 -> row 6
    assert controller.selected == Position(6, 0)


def test_click_same_cell_twice_requests_jump():
    rows = [['.'] * 8 for _ in range(8)]
    rows[6][0] = 'wP'
    engine = make_engine(rows)
    controller = Controller(engine, 100)
    controller.click(0, 600)
    controller.click(0, 600)
    assert controller.selected is None
    assert engine.is_piece_busy(Position(6, 0)) is True


def test_click_different_own_piece_reselects():
    rows = [['.'] * 8 for _ in range(8)]
    rows[6][0] = 'wP'
    rows[6][1] = 'wP'
    engine = make_engine(rows)
    controller = Controller(engine, 100)
    controller.click(0, 600)
    controller.click(100, 600)
    assert controller.selected == Position(6, 1)


def test_click_enemy_or_empty_cell_requests_move():
    rows = [['.'] * 8 for _ in range(8)]
    rows[6][0] = 'wP'
    engine = make_engine(rows)
    controller = Controller(engine, 100)
    controller.click(0, 600)  # select (6,0)
    controller.click(0, 500)  # click (5,0), empty -> move
    assert controller.selected is None
    assert engine.is_piece_busy(Position(6, 0)) is True


def test_click_outside_board_with_selection_cancels():
    rows = [['.'] * 8 for _ in range(8)]
    rows[6][0] = 'wP'
    engine = make_engine(rows)
    controller = Controller(engine, 100)
    controller.click(0, 600)
    assert controller.selected == Position(6, 0)
    controller.click(-100, -100)
    assert controller.selected is None


def test_click_selected_piece_disappeared_clears_selection():
    rows = [['.'] * 8 for _ in range(8)]
    rows[6][0] = 'wP'
    engine = make_engine(rows)
    controller = Controller(engine, 100)
    controller.click(0, 600)
    assert controller.selected == Position(6, 0)
    # simulate piece vanishing from source
    engine.board.set_piece_at(Position(6, 0), None)
    controller.click(0, 500)
    assert controller.selected is None
