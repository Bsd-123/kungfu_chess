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


def make_snapshot(game_over=False, winner=None):
    return GameSnapshot(board_width=800, board_height=800, pieces=[],
                         selected=None, game_over=game_over, winner=winner)


def test_request_move_forwards_to_network_client():
    client = FakeNetworkClient()
    proxy = RemoteGameProxy(client, make_snapshot())
    proxy.request_move(Position(6, 0), Position(5, 0))
    assert client.move_requests == [(Position(6, 0), Position(5, 0))]


def test_request_jump_forwards_to_network_client():
    client = FakeNetworkClient()
    proxy = RemoteGameProxy(client, make_snapshot())
    proxy.request_jump(Position(6, 0))
    assert client.jump_requests == [Position(6, 0)]


def test_snapshot_returns_latest_applied_snapshot():
    client = FakeNetworkClient()
    initial = make_snapshot()
    proxy = RemoteGameProxy(client, initial)
    assert proxy.snapshot() is initial

    updated = make_snapshot(game_over=True, winner='w')
    proxy.apply_snapshot(updated)
    assert proxy.snapshot() is updated
    assert proxy.game_over is True
    assert proxy.winner_color == 'w'


def test_advance_clock_is_a_noop():
    client = FakeNetworkClient()
    proxy = RemoteGameProxy(client, make_snapshot())
    proxy.advance_clock(1000)  # should not raise, should not change state
    assert proxy.clock_ms == 0


def test_legal_destinations_returns_empty():
    client = FakeNetworkClient()
    proxy = RemoteGameProxy(client, make_snapshot())
    assert proxy.legal_destinations(Position(6, 0)) == []


def test_board_starts_at_standard_position():
    client = FakeNetworkClient()
    proxy = RemoteGameProxy(client, make_snapshot())
    piece = proxy.board.get_piece_at(Position(6, 0))
    assert piece.color == 'w' and piece.type == 'P'


def test_selected_is_plain_readwrite_attribute():
    client = FakeNetworkClient()
    proxy = RemoteGameProxy(client, make_snapshot())
    assert proxy.selected is None
    proxy.selected = Position(1, 1)
    assert proxy.selected == Position(1, 1)
