from __future__ import annotations
from dataclasses import dataclass, field
from typing import ClassVar, Dict, Tuple


@dataclass(frozen=True)
class GameConfig:
    """Centralized configuration for all magic numbers/strings used across the engine. The three per-piece-type
    override tables (move_duration_ms, cooldown_ms, jump_cooldown_ms) should be read via their accessor methods,
    not the dicts directly."""

    cell_pixel_size: int = 100

    # Per-square travel time in ms, keyed by piece type; falls back to default_move_duration_ms.
    move_duration_ms: dict = field(default_factory=dict)
    default_move_duration_ms: int = 2500

    jump_duration_ms: int = 2500

    # Post-move cooldown (ms) before the landing square can host another motion; 0 disables it.
    cooldown_ms: dict = field(default_factory=dict)
    default_cooldown_ms: int = 1000

    # Same shape as cooldown_ms, for jump landings.
    jump_cooldown_ms: dict = field(default_factory=dict)
    default_jump_cooldown_ms: int = 400

    # Standard chess relative piece values, keyed by piece type; used by
    # ScoreObserver to score captures. King omitted from capture scoring
    # since a king capture ends the game via win_condition_piece_types.
    piece_values: dict = field(default_factory=lambda: {
        'P': 1, 'N': 3, 'B': 3, 'R': 5, 'Q': 9, 'K': 0,
    })

    empty_token: str = '.'
    board_marker: str = 'Board:'
    commands_marker: str = 'Commands:'
    print_board_command: str = 'print board'

    # Matches the empty token or a "<color><type>" piece token, e.g. "wK", "bP".
    token_pattern: str = r'^(\.|[wb][KQRBNP])$'

    # Which captured piece type(s) end the game; ('K',) is standard chess.
    win_condition_piece_types: Tuple[str, ...] = ('K',)

    # Motion/animation state vocabulary shared between the engine and the UI's sprite state machine.
    MOTION_STATE_IDLE: ClassVar[str] = 'idle'
    MOTION_STATE_MOVE: ClassVar[str] = 'move'
    MOTION_STATE_JUMP: ClassVar[str] = 'jump'

    # States whose progress is computed by the engine (motion_progress) rather than the sprite's own animation loop.
    ENGINE_DRIVEN_STATES: ClassVar[frozenset] = frozenset({'move', 'jump'})

    # Sprite state a piece transitions into once an engine-driven motion finishes.
    POST_MOTION_STATE: ClassVar[Dict[str, str]] = {
        'move': 'short_rest',
        'jump': 'long_rest',
    }

    def move_duration_for(self, piece_type: str) -> int:
        return self.move_duration_ms.get(piece_type, self.default_move_duration_ms)

    def cooldown_for(self, piece_type: str) -> int:
        return self.cooldown_ms.get(piece_type, self.default_cooldown_ms)

    def jump_cooldown_for(self, piece_type: str) -> int:
        return self.jump_cooldown_ms.get(piece_type, self.default_jump_cooldown_ms)
