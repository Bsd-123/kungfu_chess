"""Server-level move/jump rejection reasons -- distinct from
`engine.move_reasons.MoveReasons`, which is scoped to GameEngine's own
orchestration-level reasons. These are multiplayer-authorization
concerns (is this connection even a player here, does its assigned
color match the piece it's trying to move) that don't exist for local,
single-process play."""
from __future__ import annotations
from typing import ClassVar

__all__ = ["SessionReasons"]


class SessionReasons:
    NOT_A_PLAYER: ClassVar[str] = "not_a_player"
    WRONG_COLOR: ClassVar[str] = "wrong_color"
    NO_PIECE_AT_SOURCE: ClassVar[str] = "no_piece_at_source"
