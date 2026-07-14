"""Placeholder art (final_plan_verified.md Phase 1 step 4, extended in
Phase 4 for the sprite/state-machine layer): a checkerboard board
background + a full idle/move/jump/long_rest animation set per
(color, kind), built purely through `Img.new`/`draw_rect`/
`draw_circle`/`draw_ellipse`/`put_text`/`save` -- no external art, no
other drawing library.

Each state folder gets `frame_0.png`, `frame_1.png`, ... plus a
`config.json` (`fps`, `loop`, `next_state_when_finished`) that
`SpriteLibrary` reads. Swapping to real assets later is a one-line path
change in `PieceRenderer`'s asset root (this script only ever writes
under `.../sprites/assets/placeholder/`, never touches `.../official/`).

Run directly: `python -m kungfu_chess.scripts.generate_placeholder_assets`
"""
from __future__ import annotations

import json
import os

from kungfu_chess.config import GameConfig
from kungfu_chess.ui.img import Img

ASSET_ROOT = os.path.join(os.path.dirname(__file__), "..", "ui", "sprites",
                           "assets", "placeholder")

LIGHT_SQUARE = (181, 217, 240)   # BGR
DARK_SQUARE = (99, 136, 181)     # BGR

WHITE_FILL = (235, 235, 235)     # BGR, near-white
WHITE_OUTLINE = (30, 30, 30)
BLACK_FILL = (35, 35, 35)
BLACK_OUTLINE = (230, 230, 230)

MOVE_HIGHLIGHT = (60, 220, 255)  # BGR, bright amber ring while in motion

KINDS = ["K", "Q", "R", "B", "N", "P"]
COLORS = ["w", "b"]

STATE_CONFIGS = {
    "idle": {"fps": 2, "loop": True, "next_state_when_finished": None},
    "move": {"fps": 6, "loop": True, "next_state_when_finished": None},
    "jump": {"fps": 6, "loop": True, "next_state_when_finished": None},
    "long_rest": {"fps": 2, "loop": False, "next_state_when_finished": "idle"},
}


def generate_board(cell_pixel_size: int, ncols: int, nrows: int) -> str:
    board = Img.new(cell_pixel_size * ncols, cell_pixel_size * nrows,
                     channels=4, color=(0, 0, 0, 255))
    for row in range(nrows):
        for col in range(ncols):
            is_light = (row + col) % 2 == 0
            color = LIGHT_SQUARE if is_light else DARK_SQUARE
            x1, y1 = col * cell_pixel_size, row * cell_pixel_size
            x2, y2 = x1 + cell_pixel_size, y1 + cell_pixel_size
            board.draw_rect(x1, y1, x2 - 1, y2 - 1, color, thickness=-1)

    path = os.path.join(ASSET_ROOT, "board.png")
    board.save(path)
    return path


def _palette(color: str):
    return (WHITE_FILL, WHITE_OUTLINE) if color == "w" else (BLACK_FILL, BLACK_OUTLINE)


def _canvas(cell: int) -> Img:
    return Img.new(cell, cell, channels=4, color=(0, 0, 0, 0))


def _label(sprite: Img, kind: str, cell: int, outline, alpha: int = 255) -> None:
    font_scale = cell / 100.0
    thickness = max(1, round(2 * font_scale))
    cx = cy = cell // 2
    text_x = cx - int(14 * font_scale)
    text_y = cy + int(12 * font_scale)
    sprite.put_text(kind, text_x, text_y, (*outline, alpha),
                     font_scale=font_scale, thickness=thickness)


def idle_frames(color: str, kind: str, cell: int):
    fill, outline = _palette(color)
    cx = cy = cell // 2
    base_r = cell // 2 - 6
    frames = []
    for bump in (0, 4):  # frame 0 = exhale, frame 1 = inhale (breathing pulse)
        sprite = _canvas(cell)
        r = base_r + bump
        sprite.draw_circle(cx, cy, r, (*fill, 255), thickness=-1)
        sprite.draw_circle(cx, cy, r, (*outline, 255), thickness=3)
        _label(sprite, kind, cell, outline)
        frames.append(sprite)
    return frames


def move_frames(color: str, kind: str, cell: int):
    # Same breathing pair as idle, plus a bright ring so a gliding piece
    # reads as visibly "in motion" independent of position interpolation.
    fill, outline = _palette(color)
    cx = cy = cell // 2
    base_r = cell // 2 - 6
    frames = []
    for bump in (0, 4):
        sprite = _canvas(cell)
        r = base_r + bump
        sprite.draw_circle(cx, cy, r, (*fill, 255), thickness=-1)
        sprite.draw_circle(cx, cy, r, (*outline, 255), thickness=3)
        sprite.draw_circle(cx, cy, r + 5, (*MOVE_HIGHLIGHT, 255), thickness=2)
        _label(sprite, kind, cell, outline)
        frames.append(sprite)
    return frames


def jump_frames(color: str, kind: str, cell: int):
    fill, outline = _palette(color)
    cx = cy = cell // 2
    base_r = cell // 2 - 6
    frames = []

    # frame 0: crouch/squash -- wide and short
    squash = _canvas(cell)
    squash.draw_ellipse(cx, cy + 6, (base_r + 6, base_r - 8), (*fill, 255), thickness=-1)
    squash.draw_ellipse(cx, cy + 6, (base_r + 6, base_r - 8), (*outline, 255), thickness=3)
    _label(squash, kind, cell, outline)
    frames.append(squash)

    # frame 1: mid-air stretch -- narrow and tall
    stretch = _canvas(cell)
    stretch.draw_ellipse(cx, cy - 4, (base_r - 8, base_r + 8), (*fill, 255), thickness=-1)
    stretch.draw_ellipse(cx, cy - 4, (base_r - 8, base_r + 8), (*outline, 255), thickness=3)
    _label(stretch, kind, cell, outline)
    frames.append(stretch)

    return frames


def long_rest_frames(color: str, kind: str, cell: int):
    # UI-only cooldown state (plan Phase 4 step 3) -- dimmed, fading
    # further across its two frames before AnimatedSprite transitions
    # back to idle on its own.
    fill, outline = _palette(color)
    cx = cy = cell // 2
    base_r = cell // 2 - 6
    dim_fill = tuple(int(c * 0.6) for c in fill)
    dim_outline = tuple(int(c * 0.6) for c in outline)
    frames = []
    for alpha in (200, 150):
        sprite = _canvas(cell)
        sprite.draw_circle(cx, cy, base_r, (*dim_fill, alpha), thickness=-1)
        sprite.draw_circle(cx, cy, base_r, (*dim_outline, alpha), thickness=3)
        _label(sprite, kind, cell, dim_outline, alpha=alpha)
        frames.append(sprite)
    return frames


STATE_BUILDERS = {
    "idle": idle_frames,
    "move": move_frames,
    "jump": jump_frames,
    "long_rest": long_rest_frames,
}


def generate_piece_state(color: str, kind: str, state_name: str, cell: int) -> str:
    frames = STATE_BUILDERS[state_name](color, kind, cell)
    folder = os.path.join(ASSET_ROOT, f"{color}_{kind}", state_name)
    for i, frame in enumerate(frames):
        frame.save(os.path.join(folder, f"frame_{i}.png"))
    with open(os.path.join(folder, "config.json"), "w", encoding="utf-8") as f:
        json.dump(STATE_CONFIGS[state_name], f, indent=2)
    return folder


def main() -> None:
    config = GameConfig()
    cell = config.cell_pixel_size

    board_path = generate_board(cell, ncols=8, nrows=8)
    print(f"wrote {board_path}")

    for color in COLORS:
        for kind in KINDS:
            for state_name in STATE_BUILDERS:
                folder = generate_piece_state(color, kind, state_name, cell)
                print(f"wrote {folder}")


if __name__ == "__main__":
    main()
