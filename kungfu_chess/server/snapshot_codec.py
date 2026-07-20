"""Serializes `GameSnapshot` (already plain values -- see
`view/game_snapshot.py`) to/from a JSON-safe dict for the `snapshot`
message payload. No new state derivation happens here, only
transmission: `GameEngine.snapshot()` -> `SnapshotBuilder` -> this
codec, unchanged from the local single-process version."""
from __future__ import annotations

from typing import Any, Dict, Optional

from kungfu_chess.model.position import Position
from kungfu_chess.view.game_snapshot import GameSnapshot, PieceSnapshot


def _piece_to_dict(piece: PieceSnapshot) -> Dict[str, Any]:
    return {
        "kind": piece.kind,
        "color": piece.color,
        "pixel_x": piece.pixel_x,
        "pixel_y": piece.pixel_y,
        "state": piece.state,
        "motion_progress": piece.motion_progress,
        "dst_pixel_x": piece.dst_pixel_x,
        "dst_pixel_y": piece.dst_pixel_y,
        "cooldown_progress": piece.cooldown_progress,
    }


def _piece_from_dict(data: Dict[str, Any]) -> PieceSnapshot:
    return PieceSnapshot(
        kind=data["kind"],
        color=data["color"],
        pixel_x=data["pixel_x"],
        pixel_y=data["pixel_y"],
        state=data["state"],
        motion_progress=data["motion_progress"],
        dst_pixel_x=data["dst_pixel_x"],
        dst_pixel_y=data["dst_pixel_y"],
        cooldown_progress=data["cooldown_progress"],
    )


def snapshot_to_dict(snapshot: GameSnapshot) -> Dict[str, Any]:
    return {
        "board_width": snapshot.board_width,
        "board_height": snapshot.board_height,
        "pieces": [_piece_to_dict(p) for p in snapshot.pieces],
        "selected": list(snapshot.selected) if snapshot.selected is not None else None,
        "game_over": snapshot.game_over,
        "winner": snapshot.winner,
    }


def snapshot_from_dict(data: Dict[str, Any]) -> GameSnapshot:
    selected: Optional[Position] = (
        Position(*data["selected"]) if data["selected"] is not None else None)
    return GameSnapshot(
        board_width=data["board_width"],
        board_height=data["board_height"],
        pieces=[_piece_from_dict(p) for p in data["pieces"]],
        selected=selected,
        game_over=data["game_over"],
        winner=data["winner"],
    )
