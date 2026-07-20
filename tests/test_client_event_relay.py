from kungfu_chess.network.client_event_relay import republish_envelope
from kungfu_chess.server.config import NetworkConfig
from kungfu_chess.server.protocol import make_envelope
from kungfu_chess.ui.events.event_bus import EventBus
from kungfu_chess.ui.events.events import MoveResolvedEvent


def test_republishes_known_domain_event_type():
    bus = EventBus()
    received = []
    bus.subscribe(MoveResolvedEvent, received.append)

    envelope = make_envelope("move_resolved", {
        "piece_color": "w", "piece_kind": "P", "src_row": 6, "src_col": 0,
        "dst_row": 5, "dst_col": 0, "captured_piece_kind": None,
        "requested_dst_row": None, "requested_dst_col": None,
    }, NetworkConfig())

    result = republish_envelope(envelope, bus)

    assert result is True
    assert received == [MoveResolvedEvent(
        piece_color="w", piece_kind="P", src_row=6, src_col=0,
        dst_row=5, dst_col=0, captured_piece_kind=None,
        requested_dst_row=None, requested_dst_col=None)]


def test_unknown_type_is_not_republished():
    bus = EventBus()
    envelope = make_envelope("snapshot", {"board_width": 8}, NetworkConfig())
    result = republish_envelope(envelope, bus)
    assert result is False


def test_move_response_type_is_not_republished():
    bus = EventBus()
    envelope = make_envelope("move_response", {"accepted": True, "reason": "ok"}, NetworkConfig())
    result = republish_envelope(envelope, bus)
    assert result is False
