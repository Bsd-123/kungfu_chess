"""Owns one piece's current `SpriteState`, swapping it via
`SpriteLibrary` when the engine-reported state changes.
`long_rest`/`short_rest` are UI-only post-motion cooldowns the engine
doesn't know about: when `engine_state` drops back to `"idle"` right
after `"move"`/`"jump"`, this enters the matching post-motion state
first (`jump -> short_rest -> long_rest -> idle`, `move -> long_rest ->
idle`), driven onward by each state's own non-looping `config.json`.
State-name strings come from `GameConfig`'s `MOTION_STATE_*` constants,
shared with the engine side."""
from __future__ import annotations

from kungfu_chess.config import GameConfig
from kungfu_chess.ui.img import Img
from kungfu_chess.ui.sprites.sprite_library import SpriteLibrary

_ENGINE_DRIVEN_STATES = GameConfig.ENGINE_DRIVEN_STATES
_POST_MOTION_STATE = GameConfig.POST_MOTION_STATE
_IDLE = GameConfig.MOTION_STATE_IDLE


class AnimatedSprite:
    def __init__(self, library: SpriteLibrary, color: str, kind: str):
        self._library = library
        self._color = color
        self._kind = kind
        self._state_name = _IDLE
        self._state = library.get(color, kind, _IDLE)

    def _switch_to(self, state_name: str) -> None:
        self._state_name = state_name
        self._state = self._library.get(self._color, self._kind, state_name)

    def update(self, dt_ms: float, engine_state: str) -> None:
        if engine_state in _ENGINE_DRIVEN_STATES:
            if self._state_name != engine_state:
                self._switch_to(engine_state)
            self._state.advance(dt_ms)
            return

        # engine_state == "idle" (nothing else is reported by GameEngine)
        if self._state_name in _ENGINE_DRIVEN_STATES:
            # Motion just finished -> UI-only cooldown state.
            self._switch_to(_POST_MOTION_STATE[self._state_name])
            return

        next_state = self._state.advance(dt_ms)
        if next_state is not None:
            self._switch_to(next_state)

    def current_frame(self) -> Img:
        return self._state.current_frame()

    @property
    def state_name(self) -> str:
        return self._state_name
