"""Proves Controller needs zero code changes to drive a RemoteGameProxy
instead of a local GameEngine (Strict Encapsulation) -- it only ever
touched board.is_within_bounds/get_piece_at and
request_move/request_jump, all of which RemoteGameProxy duck-types."""
from kungfu_chess.input.controller import Controller
from kungfu_chess.model.position import Position
from kungfu_chess.network.remote_game_proxy import RemoteGameProxy
from kungfu_chess.view.game_snapshot import GameSnapshot


class FakeNetworkClient:
    def __init__(self):
        self.move_requests = []
        self.jump_requests = []

    def request_move(self, source, destination):
        self.move_requests.append((source, destination))

    def request_jump(self, position):
        self.jump_requests.append(position)


def make_proxy():
    client = FakeNetworkClient()
    snapshot = GameSnapshot(board_width=800, board_height=800, pieces=[],
                             selected=None, game_over=False, winner=None)
    return RemoteGameProxy(client, snapshot), client


def test_click_own_piece_then_destination_sends_move_request():
    proxy, client = make_proxy()
    controller = Controller(proxy, cell_pixel_size=100)

    # Row 6, col 0 -> pixel center roughly (50, 650) given row 0 at top.
    controller.click(x=50, y=650)  # select white pawn at (6, 0)
    assert controller.selected == Position(6, 0)

    controller.click(x=50, y=550)  # click (5, 0), an empty square ahead
    assert client.move_requests == [(Position(6, 0), Position(5, 0))]
    assert controller.selected is None


def test_click_same_square_twice_sends_jump_request():
    proxy, client = make_proxy()
    controller = Controller(proxy, cell_pixel_size=100)

    controller.click(x=50, y=650)
    controller.click(x=50, y=650)
    assert client.jump_requests == [Position(6, 0)]


def test_click_outside_board_cancels_selection():
    proxy, client = make_proxy()
    controller = Controller(proxy, cell_pixel_size=100)

    controller.click(x=50, y=650)
    assert controller.selected is not None
    controller.click(x=-10, y=-10)
    assert controller.selected is None
