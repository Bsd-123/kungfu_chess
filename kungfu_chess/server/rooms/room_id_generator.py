"""Short, human-readable room codes (Decision 8) -- alphanumeric,
never UUIDs, with an explicit collision check against currently active
room IDs. Isolated in its own module so the code scheme can change
later without touching `room_manager.py`."""
from __future__ import annotations

import secrets
from typing import Callable, Container

from kungfu_chess.server.config import RoomConfig

# Uppercase letters and digits, minus visually ambiguous characters
# (0/O, 1/I) -- a human reading a code aloud shouldn't have to guess.
_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_MAX_ATTEMPTS = 100


def generate_room_id(existing_ids: Container[str], config: RoomConfig = None,
                      choice_fn: Callable[[str], str] = secrets.choice) -> str:
    """`choice_fn` defaults to `secrets.choice` (cryptographically
    random, not that unpredictability matters for a room code -- just a
    convenient stdlib source of uniform randomness); tests inject a
    scripted stub to exercise the collision-retry path deterministically."""
    config = config or RoomConfig()
    for _ in range(_MAX_ATTEMPTS):
        candidate = "".join(choice_fn(_ALPHABET) for _ in range(config.room_code_length))
        if candidate not in existing_ids:
            return candidate
    raise RuntimeError(
        f"failed to generate a unique {config.room_code_length}-character room id "
        f"after {_MAX_ATTEMPTS} attempts")
