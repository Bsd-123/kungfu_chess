"""Piece-art directory naming and `resolve()`, which picks the real asset
pack over the placeholder one if present. Called once by the composition
root; the resulting `is_real` flag is passed down to `PieceRenderer`/
`SpriteLibrary`."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class AssetPaths:
    sprites_dirname: str = "sprites"
    assets_dirname: str = "assets"
    placeholder_dirname: str = "placeholder"
    pieces_mine_dirname: str = "pieces_mine"

    def resolve(self, ui_package_dir: str) -> Tuple[str, bool]:
        """Returns `(asset_root, is_real)` for the real or placeholder art
        folder under `ui_package_dir`."""
        sprites_dir = os.path.join(ui_package_dir, self.sprites_dirname, self.assets_dirname)
        real_root = os.path.join(sprites_dir, self.assets_dirname)
        placeholder_root = os.path.join(sprites_dir, self.placeholder_dirname)
        is_real = os.path.isdir(os.path.join(real_root, self.pieces_mine_dirname))
        return (real_root if is_real else placeholder_root), is_real


DEFAULT_ASSET_PATHS = AssetPaths()
