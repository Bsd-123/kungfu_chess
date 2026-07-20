from kungfu_chess.model.position import Position
from kungfu_chess.network.network_sync import drain_network_client
from kungfu_chess.network.remote_game_proxy import RemoteGameProxy
from kungfu_chess.server.config import NetworkConfig
from kungfu_chess.server.protocol import make_envelope
from kungfu_chess.server.snapshot_codec import snapshot_to_dict
from kungfu_chess.ui.events.event_bus import EventBus
from kungfu_chess.ui.events.events import MoveResolvedEvent
from kungfu_chess.view.game_snapshot import GameSnapshot


class FakeNetworkClient:
    def __init__(self, envelopes):
        self._envelopes = envelopes

    def poll_incoming(self):
        drained, self._envelopes = self._envelopes, []
        return drained


def make_snapshot(game_over=False):
    return GameSnapshot(board_width=800, board_height=800, pieces=[],
                         selected=None, game_over=game_over, winner=None)


def test_snapshot_envelope_updates_proxy_without_touching_bus():
    initial = make_snapshot()
    updated = make_snapshot(game_over=True)
    envelope = make_envelope("snapshot", snapshot_to_dict(updated), NetworkConfig())
    client = FakeNetworkClient([envelope])
    proxy = RemoteGameProxy(client, initial)
    bus = EventBus()
    received = []
    bus.subscribe(MoveResolvedEvent, received.append)

    drain_network_client(client, proxy, bus)

    assert proxy.snapshot().game_over is True
    assert received == []


def test_domain_event_envelope_is_republished_onto_bus():
    client = FakeNetworkClient([make_envelope("move_resolved", {
        "piece_color": "w", "piece_kind": "P", "src_row": 6, "src_col": 0,
        "dst_row": 5, "dst_col": 0, "captured_piece_kind": None,
        "requested_dst_row": None, "requested_dst_col": None,
    }, NetworkConfig())])
    proxy = RemoteGameProxy(client, make_snapshot())
    bus = EventBus()
    received = []
    bus.subscribe(MoveResolvedEvent, received.append)

    drain_network_client(client, proxy, bus)

    assert len(received) == 1
    assert received[0].src_row == 6


def test_ack_type_is_silently_skipped():
    client = FakeNetworkClient([make_envelope(
        "move_response", {"accepted": True, "reason": "ok"}, NetworkConfig())])
    proxy = RemoteGameProxy(client, make_snapshot())
    bus = EventBus()
    drain_network_client(client, proxy, bus)  # should not raise


def test_updates_board_mirror_when_subscribed():
    client = FakeNetworkClient([make_envelope("move_resolved", {
        "piece_color": "w", "piece_kind": "P", "src_row": 6, "src_col": 0,
        "dst_row": 5, "dst_col": 0, "captured_piece_kind": None,
        "requested_dst_row": None, "requested_dst_col": None,
    }, NetworkConfig())])
    proxy = RemoteGameProxy(client, make_snapshot())
    bus = EventBus()
    bus.subscribe(MoveResolvedEvent, proxy.board.on_move_resolved)

    drain_network_client(client, proxy, bus)

    assert proxy.board.get_piece_at(Position(6, 0)) is None
    assert proxy.board.get_piece_at(Position(5, 0)).type == 'P'
