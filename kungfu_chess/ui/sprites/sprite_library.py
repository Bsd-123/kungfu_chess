"""Loads sprite frames/config so `AnimatedSprite` never touches the
filesystem directly. Frames+`StateConfig` are cached per (color, kind,
state), but `get()` always returns a fresh `SpriteState` so pieces
sharing a state don't share a frame-timer.

Supports two on-disk layouts, auto-detected from whether
`{asset_root}/pieces_mine/` exists:
- placeholder: `{asset_root}/{color}_{kind}/{state}/frame_*.png` + flat
  `config.json` (`fps`/`loop`/`next_state_when_finished`).
- "real" asset pack: `{asset_root}/pieces_mine/{color}{KIND}/states/
  {state}/sprites/*.png` (numbered, not zero-padded) + nested
  `config.json` (`physics.*`/`graphics.*`).

`is_real`: optional pre-computed detection result (from
`ui/composition.py`) to avoid redundant `os.path.isdir` checks;
`None` falls back to auto-detection."""
from __future__ import annotations

import json
import os
from glob import glob
from typing import Dict, List, Optional, Tuple

from kungfu_chess.ui.asset_paths import DEFAULT_ASSET_PATHS
from kungfu_chess.ui.img import Img
from kungfu_chess.ui.sprites.sprite_state import SpriteState, StateConfig

_DEFAULT_CONFIG = StateConfig(fps=4.0, loop=True, next_state_when_finished=None)
_REAL_PIECES_DIRNAME = DEFAULT_ASSET_PATHS.pieces_mine_dirname


class SpriteLibrary:
    def __init__(self, asset_root: str, cell_pixel_size: int,
                 is_real: Optional[bool] = None):
        self._asset_root = asset_root
        self._cell = cell_pixel_size
        self._cache: Dict[Tuple[str, str, str], Tuple[List[Img], StateConfig]] = {}

        self._pieces_root = os.path.join(asset_root, _REAL_PIECES_DIRNAME)
        self._real_layout = is_real if is_real is not None else os.path.isdir(self._pieces_root)

    def _folder(self, color: str, kind: str, state_name: str) -> str:
        if self._real_layout:
            return os.path.join(self._pieces_root, f"{color}{kind}", "states", state_name)
        return os.path.join(self._asset_root, f"{color}_{kind}", state_name)

    def _load_config(self, folder: str) -> StateConfig:
        path = os.path.join(folder, "config.json")
        if not os.path.isfile(path):
            return _DEFAULT_CONFIG
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if self._real_layout:
            physics = data.get("physics", {}) or {}
            graphics = data.get("graphics", {}) or {}
            return StateConfig(
                fps=float(graphics.get("frames_per_sec", _DEFAULT_CONFIG.fps)),
                loop=bool(graphics.get("is_loop", _DEFAULT_CONFIG.loop)),
                next_state_when_finished=physics.get("next_state_when_finished"),
            )
        return StateConfig(
            fps=float(data.get("fps", _DEFAULT_CONFIG.fps)),
            loop=bool(data.get("loop", _DEFAULT_CONFIG.loop)),
            next_state_when_finished=data.get("next_state_when_finished"),
        )

    def _load_frames(self, folder: str) -> List[Img]:
        if self._real_layout:
            frames_dir = os.path.join(folder, "sprites")
            paths = glob(os.path.join(frames_dir, "*.png"))
            # Not zero-padded -- sort numerically, not lexically.
            paths.sort(key=lambda p: int(os.path.splitext(os.path.basename(p))[0]))
        else:
            frames_dir = folder
            paths = sorted(glob(os.path.join(frames_dir, "frame_*.png")))

        if not paths:
            raise FileNotFoundError(f"SpriteLibrary: no frames found in '{frames_dir}'")
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
