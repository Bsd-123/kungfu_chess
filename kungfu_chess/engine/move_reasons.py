from __future__ import annotations
from typing import ClassVar

__all__ = ["MoveReasons"]


class MoveReasons:
    """Canonical accept/reject reason codes reported on `MoveResult` and by
    `MotionGate`. Scoped to GameEngine-orchestration-level reasons, distinct from
    the deeper RuleEngine validation reasons (`"outside_board"`, etc.) that
    `request_move` copies through unchanged."""

    OK: ClassVar[str] = "ok"
    GAME_OVER: ClassVar[str] = "game_over"
    MOTION_IN_PROGRESS: ClassVar[str] = "motion_in_progress"
    COOLDOWN: ClassVar[str] = "cooldown"
