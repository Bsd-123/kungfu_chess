import json

from kungfu_chess.app import build_game_engine
from kungfu_chess.config import GameConfig
from kungfu_chess.model.position import Position
from kungfu_chess.server.snapshot_codec import snapshot_from_dict, snapshot_to_dict


def test_snapshot_round_trips_through_dict_and_json():
    rows = [['.'] * 8 for _ in range(8)]
    rows[6][0] = 'wP'
    rows[1][1] = 'bK'
    engine = build_game_engine(rows, GameConfig())
    engine.selected = Position(6, 0)
    snapshot = engine.snapshot()

    as_dict = snapshot_to_dict(snapshot)
    json.dumps(as_dict)  # must be JSON-safe
    restored = snapshot_from_dict(as_dict)

    assert restored == snapshot


def test_snapshot_with_no_selection_round_trips():
    engine = build_game_engine([['.'] * 8 for _ in range(8)], GameConfig())
    snapshot = engine.snapshot()
    assert snapshot.selected is None

    restored = snapshot_from_dict(snapshot_to_dict(snapshot))
    assert restored.selected is None
    assert restored == snapshot
