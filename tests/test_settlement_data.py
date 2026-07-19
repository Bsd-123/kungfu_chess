from kungfu_chess.model.piece import Piece
from kungfu_chess.model.position import Position
from kungfu_chess.realtime.motion import SettlementEvent
from kungfu_chess.realtime.settlement_data import SettlementDataInterface


def test_settlement_event_structurally_satisfies_interface():
    piece = Piece(color='w', type='Q')
    event = SettlementEvent(src=Position(0, 0), dst=Position(0, 1), piece=piece, captured_piece=None)
    assert isinstance(event, SettlementDataInterface)


def test_plain_object_without_attributes_does_not_satisfy_interface():
    class NotAnEvent:
        pass

    assert isinstance(NotAnEvent(), SettlementDataInterface) is False
