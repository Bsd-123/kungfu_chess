"""Strategy pattern (plan section 7.1/7.3): asset-loading, isolated
behind one method (`get`) so `AnimatedSprite` never touches a filesystem
path or a `config.json` directly. Keys are the engine's raw `color`/
`kind` codes (`w_P`, `b_N`, ...), never translated English words (plan
section 0.3) -- one less place a name can drift out of sync with the
engine's actual `piece.color`/`piece.kind` values.

Frame images and `StateConfig` are cached per (color, kind, state) --
loaded from disk once -- but `get()` always returns a *fresh*
`SpriteState` instance (its own independent frame-timer) so two pieces
of the same (color, kind) animating in the same state don't share
timing state.
"""
from __future__ import annotations

import json
import os
from glob import glob
from typing import Dict, List, Tuple

from kungfu_chess.ui.img import Img
from kungfu_chess.ui.sprites.sprite_state import SpriteState, StateConfig

_DEFAULT_CONFIG = StateConfig(fps=4.0, loop=True, next_state_when_finished=None)


class SpriteLibrary:
    def __init__(self, asset_root: str, cell_pixel_size: int):
        self._asset_root = asset_root
        self._cell = cell_pixel_size
        self._cache: Dict[Tuple[str, str, str], Tuple[List[Img], StateConfig]] = {}

    def _folder(self, color: str, kind: str, state_name: str) -> str:
        return os.path.join(self._asset_root, f"{color}_{kind}", state_name)

    def _load_config(self, folder: str) -> StateConfig:
        path = os.path.join(folder, "config.json")
        if not os.path.isfile(path):
            return _DEFAULT_CONFIG
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return StateConfig(
            fps=float(data.get("fps", _DEFAULT_CONFIG.fps)),
            loop=bool(data.get("loop", _DEFAULT_CONFIG.loop)),
            next_state_when_finished=data.get("next_state_when_finished"),
        )

    def _load_frames(self, folder: str) -> List[Img]:
        paths = sorted(glob(os.path.join(folder, "frame_*.png")))
        if not paths:
            raise FileNotFoundError(f"SpriteLibrary: no frames found in '{folder}'")
        return [Img().read(p, size=(self._cell, self._cell), keep_aspect=True)
                for p in paths]

    def get(self, color: str, kind: str, state_name: str) -> SpriteState:
        key = (color, kind, state_name)
        cached = self._cache.get(key)
        if cached is None:
            folder = self._folder(color, kind, state_name)
            frames = self._load_frames(folder)
            config = self._load_config(folder)
            cached = (frames, config)
            self._cache[key] = cached
        frames, config = cached
        return SpriteState(state_name, frames, config)
