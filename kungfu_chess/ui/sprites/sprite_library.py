"""Strategy pattern (plan section 7.1/7.3): asset-loading, isolated
behind one method (`get`) so `AnimatedSprite` never touches a filesystem
path or a `config.json` directly. Keys are the engine's raw `color`/
`kind` codes (`w_P`/`wP`, `b_N`/`bN`, ...), never translated English
words (plan section 0.3) -- one less place a name can drift out of sync
with the engine's actual `piece.color`/`piece.kind` values.

Frame images and `StateConfig` are cached per (color, kind, state) --
loaded from disk once -- but `get()` always returns a *fresh*
`SpriteState` instance (its own independent frame-timer) so two pieces
of the same (color, kind) animating in the same state don't share
timing state.

Supports two on-disk layouts, auto-detected once at construction from
`asset_root` itself (no config flag to keep in sync by hand):

- the placeholder layout this generator's own script writes:
  `{asset_root}/{color}_{kind}/{state}/frame_*.png` plus a flat
  `config.json` (`fps`/`loop`/`next_state_when_finished`).
- a "real" asset-pack layout (e.g. hand-authored/downloaded piece art
  dropped into `{asset_root}/pieces_mine/`):
  `{asset_root}/pieces_mine/{color}{KIND}/states/{state}/sprites/*.png`
  (numbered frames, not necessarily zero-padded) plus a nested
  `config.json` (`{"physics": {"speed_m_per_sec", "next_state_when_
  finished"}, "graphics": {"frames_per_sec", "is_loop"}}`).

Detection is just "does `{asset_root}/pieces_mine/` exist" -- whichever
asset pack is actually on disk determines behavior, so swapping in real
art is exactly the drop-a-folder-in operation the plan's own Phase 1
docstring promised ("swapping to real assets later is a one-line path
change"), not a code change here.
"""
from __future__ import annotations

import json
import os
from glob import glob
from typing import Dict, List, Tuple

from kungfu_chess.ui.img import Img
from kungfu_chess.ui.sprites.sprite_state import SpriteState, StateConfig

_DEFAULT_CONFIG = StateConfig(fps=4.0, loop=True, next_state_when_finished=None)
_REAL_PIECES_DIRNAME = "pieces_mine"


class SpriteLibrary:
    def __init__(self, asset_root: str, cell_pixel_size: int):
        self._asset_root = asset_root
        self._cell = cell_pixel_size
        self._cache: Dict[Tuple[str, str, str], Tuple[List[Img], StateConfig]] = {}

        self._pieces_root = os.path.join(asset_root, _REAL_PIECES_DIRNAME)
        self._real_layout = os.path.isdir(self._pieces_root)

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
            # Numbered ("1.png", "2.png", ..., "10.png"), not
            # zero-padded -- sort numerically by the filename stem
            # rather than lexically, which would otherwise order
            # "10.png" before "2.png".
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
