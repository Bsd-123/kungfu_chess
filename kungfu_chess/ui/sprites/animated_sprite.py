"""Owns exactly one piece's current `SpriteState` and transitions it
(plan section 7.1/7.2 step 2): `update(dt_ms, engine_state)` swaps to a
new `SpriteState` via `SpriteLibrary` whenever the engine-reported
state (`"idle"`/`"move"`/`"jump"`) differs from what's currently
playing, otherwise just advances the current state's own frame clock.

`long_rest`/`short_rest` are both UI-only (plan Phase 4 step 3): the
engine has no notion of a post-motion cooldown at all, so this class is
the *only* place that ever enters either -- the instant `engine_state`
drops back to `"idle"` right after having been `"move"`/`"jump"`, this
transitions into the matching post-motion state on its own rather than
jumping straight to `idle`. `_POST_MOTION_STATE` picks which one: a
settled move goes straight to `long_rest` (its own cooldown), while a
settled jump goes through the shorter `short_rest` first -- matching
the state chain authored into the real asset pack's own `config.json`
`next_state_when_finished` fields (`jump -> short_rest -> long_rest ->
idle`, `move -> long_rest -> idle`). Each state's own `config.json`
(non-looping, `next_state_when_finished` pointing at the next one) is
what carries it the rest of the way to `idle` -- never a direct read of
the engine's `state` field."""
from __future__ import annotations

from kungfu_chess.ui.img import Img
from kungfu_chess.ui.sprites.sprite_library import SpriteLibrary

_ENGINE_DRIVEN_STATES = ("move", "jump")
_POST_MOTION_STATE = {"move": "long_rest", "jump": "short_rest"}


class AnimatedSprite:
    def __init__(self, library: SpriteLibrary, color: str, kind: str):
        self._library = library
        self._color = color
        self._kind = kind
        self._state_name = "idle"
        self._state = library.get(color, kind, "idle")

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
            # A motion just finished this tick -> UI-only cooldown,
            # never read off the snapshot's own state field. Which
            # cooldown depends on which motion just finished (see
            # module docstring).
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
