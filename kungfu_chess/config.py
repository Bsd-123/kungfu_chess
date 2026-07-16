from __future__ import annotations
from dataclasses import dataclass, field


@dataclass(frozen=True)
class GameConfig:
    """Centralized configuration. All magic numbers/strings used across the
    engine live here so they can be tuned or overridden (e.g. for a custom
    game variant) without touching business logic anywhere else."""

    cell_pixel_size: int = 100

    # Per-square travel time in ms, keyed by piece type. Used as the
    # multiplier in `duration = squares_traveled * per_square_ms`
    # (Spec §10: "Moving N squares takes N x 1000ms"). A piece type not
    # present here falls back to `default_move_duration_ms`. This dict
    # previously held a *flat* per-piece duration; it is now interpreted
    # as a *per-square* duration, which is a strict generalization: any
    # game whose pieces all move exactly one square already behaves
    # identically to before.
    move_duration_ms: dict = field(default_factory=dict)
    # TEMPORARY x2.5 slowdown (requested for easier testing/visibility --
    # revert both of these two numbers back to 1000 to restore normal
    # speed; nothing else in the engine depends on this specific value).
    default_move_duration_ms: int = 2500

    jump_duration_ms: int = 2500
    empty_token: str = '.'
    board_marker: str = 'Board:'
    commands_marker: str = 'Commands:'
    print_board_command: str = 'print board'
    token_pattern: str = r'^(?:\.|[wb][KQRBNP])$'
