"""Generates placeholder sprite/board art as hand-built silhouettes via Img draw calls (no PIL/external art,
since cv2's Hershey fonts lack chess glyphs). Each state folder gets frame_N.png plus a config.json (fps, loop,
next_state_when_finished) read by SpriteLibrary. Only writes under `.../sprites/assets/placeholder/`, never the
real-asset folder. Run: `python -m kungfu_chess.scripts.generate_placeholder_assets`."""
from __future__ import annotations

import json
import os

from kungfu_chess.config import GameConfig
from kungfu_chess.ui.img import Img

ASSET_ROOT = os.path.join(os.path.dirname(__file__), "..", "ui", "sprites",
                           "assets", "placeholder")

LIGHT_SQUARE = (181, 217, 240)   # BGR
DARK_SQUARE = (99, 136, 181)     # BGR

WHITE_FILL = (240, 240, 240)     # BGR, near-white
WHITE_OUTLINE = (25, 25, 25)
BLACK_FILL = (30, 30, 30)
BLACK_OUTLINE = (225, 225, 225)

MOVE_HIGHLIGHT = (60, 220, 255)  # BGR, bright amber ring while in motion

KINDS = ["K", "Q", "R", "B", "N", "P"]
COLORS = ["w", "b"]

STATE_CONFIGS = {
    "idle": {"fps": 2, "loop": True, "next_state_when_finished": None},
    "move": {"fps": 6, "loop": True, "next_state_when_finished": None},
    "jump": {"fps": 6, "loop": True, "next_state_when_finished": None},
    "short_rest": {"fps": 4, "loop": False, "next_state_when_finished": "long_rest"},
    "long_rest": {"fps": 2, "loop": False, "next_state_when_finished": "idle"},
}


def generate_board(cell_pixel_size: int, ncols: int, nrows: int) -> str:
    """Plain checkerboard, no margin/labels -- those are drawn by BoardRenderer."""
    board_w = cell_pixel_size * ncols
    board_h = cell_pixel_size * nrows

    checkerboard = Img.new(board_w, board_h, channels=4, color=(0, 0, 0, 255))
    for row in range(nrows):
        for col in range(ncols):
            is_light = (row + col) % 2 == 0
            color = LIGHT_SQUARE if is_light else DARK_SQUARE
            x1, y1 = col * cell_pixel_size, row * cell_pixel_size
            x2, y2 = x1 + cell_pixel_size, y1 + cell_pixel_size
            checkerboard.draw_rect(x1, y1, x2 - 1, y2 - 1, color, thickness=-1)

    path = os.path.join(ASSET_ROOT, "board.png")
    checkerboard.save(path)
    return path


def _palette(color: str):
    return (WHITE_FILL, WHITE_OUTLINE) if color == "w" else (BLACK_FILL, BLACK_OUTLINE)


def _canvas(cell: int) -> Img:
    return Img.new(cell, cell, channels=4, color=(0, 0, 0, 0))


def _pt(cx: float, cy: float, dx: float, dy: float, sx: float, sy: float) -> tuple:
    return (int(round(cx + dx * sx)), int(round(cy + dy * sy)))


def _draw_base_plate(img: Img, fill, outline, cx: float, cy: float, sx: float, sy: float,
                      half_width: float = 18, y1: float = 30, y2: float = 36) -> None:
    """Base plate shared by all six `_draw_<kind>` functions; only half_width/y1/y2 vary."""
    base = [_pt(cx, cy, -half_width, y1, sx, sy), _pt(cx, cy, half_width, y1, sx, sy),
            _pt(cx, cy, half_width, y2, sx, sy), _pt(cx, cy, -half_width, y2, sx, sy)]
    img.draw_polygon(base, (*fill, 255), thickness=-1)
    img.draw_polygon(base, (*outline, 255), thickness=2)


def _draw_pawn(img: Img, fill, outline, cx: float, cy: float, sx: float, sy: float) -> None:
    head_r = int(round(12 * min(sx, sy)))
    head_c = _pt(cx, cy, 0, -14, sx, sy)
    body = [_pt(cx, cy, -9, -8, sx, sy), _pt(cx, cy, 9, -8, sx, sy),
            _pt(cx, cy, 15, 24, sx, sy), _pt(cx, cy, -15, 24, sx, sy)]
    img.draw_polygon(body, (*fill, 255), thickness=-1)
    img.draw_circle(head_c[0], head_c[1], head_r, (*fill, 255), thickness=-1)
    img.draw_polygon(body, (*outline, 255), thickness=2)
    img.draw_circle(head_c[0], head_c[1], head_r, (*outline, 255), thickness=2)
    _draw_base_plate(img, fill, outline, cx, cy, sx, sy)


def _draw_rook(img: Img, fill, outline, cx: float, cy: float, sx: float, sy: float) -> None:
    body = [_pt(cx, cy, -15, -5, sx, sy), _pt(cx, cy, 15, -5, sx, sy),
            _pt(cx, cy, 15, 30, sx, sy), _pt(cx, cy, -15, 30, sx, sy)]
    img.draw_polygon(body, (*fill, 255), thickness=-1)
    img.draw_polygon(body, (*outline, 255), thickness=2)
    slab = [_pt(cx, cy, -20, -13, sx, sy), _pt(cx, cy, 20, -13, sx, sy),
            _pt(cx, cy, 20, -5, sx, sy), _pt(cx, cy, -20, -5, sx, sy)]
    img.draw_polygon(slab, (*fill, 255), thickness=-1)
    img.draw_polygon(slab, (*outline, 255), thickness=2)
    for mx in (-17, -3, 11):
        mer = [_pt(cx, cy, mx, -26, sx, sy), _pt(cx, cy, mx + 8, -26, sx, sy),
               _pt(cx, cy, mx + 8, -13, sx, sy), _pt(cx, cy, mx, -13, sx, sy)]
        img.draw_polygon(mer, (*fill, 255), thickness=-1)
        img.draw_polygon(mer, (*outline, 255), thickness=2)
    _draw_base_plate(img, fill, outline, cx, cy, sx, sy)


def _draw_knight(img: Img, fill, outline, cx: float, cy: float, sx: float, sy: float) -> None:
    head = [
        _pt(cx, cy, 14, 32, sx, sy), _pt(cx, cy, -16, 32, sx, sy),
        _pt(cx, cy, -14, 10, sx, sy), _pt(cx, cy, -18, -4, sx, sy),
        _pt(cx, cy, -8, -18, sx, sy), _pt(cx, cy, 6, -24, sx, sy),
        _pt(cx, cy, 18, -18, sx, sy), _pt(cx, cy, 10, -12, sx, sy),
        _pt(cx, cy, 20, -6, sx, sy), _pt(cx, cy, 12, -2, sx, sy),
        _pt(cx, cy, 18, 8, sx, sy), _pt(cx, cy, 10, 14, sx, sy),
        _pt(cx, cy, 16, 32, sx, sy),
    ]
    img.draw_polygon(head, (*fill, 255), thickness=-1)
    img.draw_polygon(head, (*outline, 255), thickness=2)
    eye = _pt(cx, cy, 3, -8, sx, sy)
    img.draw_circle(eye[0], eye[1], 2, (*outline, 255), thickness=-1)
    _draw_base_plate(img, fill, outline, cx, cy, sx, sy)


def _draw_bishop(img: Img, fill, outline, cx: float, cy: float, sx: float, sy: float) -> None:
    body_axes = (int(round(14 * sx)), int(round(24 * sy)))
    body_c = _pt(cx, cy, 0, 6, sx, sy)
    img.draw_ellipse(body_c[0], body_c[1], body_axes, (*fill, 255), thickness=-1)
    img.draw_ellipse(body_c[0], body_c[1], body_axes, (*outline, 255), thickness=2)
    ball_c = _pt(cx, cy, 0, -22, sx, sy)
    ball_r = int(round(6 * min(sx, sy)))
    img.draw_circle(ball_c[0], ball_c[1], ball_r, (*fill, 255), thickness=-1)
    img.draw_circle(ball_c[0], ball_c[1], ball_r, (*outline, 255), thickness=2)
    slit_a = _pt(cx, cy, -7, -6, sx, sy)
    slit_b = _pt(cx, cy, 7, 6, sx, sy)
    img.draw_line(slit_a[0], slit_a[1], slit_b[0], slit_b[1], (*outline, 255), thickness=2)
    _draw_base_plate(img, fill, outline, cx, cy, sx, sy, y1=28, y2=34)


def _draw_queen(img: Img, fill, outline, cx: float, cy: float, sx: float, sy: float) -> None:
    body = [_pt(cx, cy, -17, 30, sx, sy), _pt(cx, cy, 17, 30, sx, sy),
            _pt(cx, cy, 12, 2, sx, sy), _pt(cx, cy, -12, 2, sx, sy)]
    img.draw_polygon(body, (*fill, 255), thickness=-1)
    img.draw_polygon(body, (*outline, 255), thickness=2)
    crown = [
        _pt(cx, cy, -16, 2, sx, sy), _pt(cx, cy, -16, -14, sx, sy),
        _pt(cx, cy, -9, -2, sx, sy), _pt(cx, cy, -5, -20, sx, sy),
        _pt(cx, cy, 0, -4, sx, sy), _pt(cx, cy, 5, -20, sx, sy),
        _pt(cx, cy, 9, -2, sx, sy), _pt(cx, cy, 16, -14, sx, sy),
        _pt(cx, cy, 16, 2, sx, sy),
    ]
    img.draw_polygon(crown, (*fill, 255), thickness=-1)
    img.draw_polygon(crown, (*outline, 255), thickness=2)
    for dx, dy in ((-16, -14), (-5, -20), (5, -20), (16, -14)):
        p = _pt(cx, cy, dx, dy, sx, sy)
        img.draw_circle(p[0], p[1], 3, (*fill, 255), thickness=-1)
        img.draw_circle(p[0], p[1], 3, (*outline, 255), thickness=1)
    _draw_base_plate(img, fill, outline, cx, cy, sx, sy, half_width=19)


def _draw_king(img: Img, fill, outline, cx: float, cy: float, sx: float, sy: float) -> None:
    body = [_pt(cx, cy, -17, 30, sx, sy), _pt(cx, cy, 17, 30, sx, sy),
            _pt(cx, cy, 11, 0, sx, sy), _pt(cx, cy, -11, 0, sx, sy)]
    img.draw_polygon(body, (*fill, 255), thickness=-1)
    img.draw_polygon(body, (*outline, 255), thickness=2)
    band = [_pt(cx, cy, -14, 0, sx, sy), _pt(cx, cy, 14, 0, sx, sy),
            _pt(cx, cy, 14, -8, sx, sy), _pt(cx, cy, -14, -8, sx, sy)]
    img.draw_polygon(band, (*fill, 255), thickness=-1)
    img.draw_polygon(band, (*outline, 255), thickness=2)
    v_top = _pt(cx, cy, 0, -8, sx, sy)
    v_bot = _pt(cx, cy, 0, -24, sx, sy)
    h_left = _pt(cx, cy, -7, -20, sx, sy)
    h_right = _pt(cx, cy, 7, -20, sx, sy)
    img.draw_line(v_top[0], v_top[1], v_bot[0], v_bot[1], (*outline, 255), thickness=3)
    img.draw_line(h_left[0], h_left[1], h_right[0], h_right[1], (*outline, 255), thickness=3)
    _draw_base_plate(img, fill, outline, cx, cy, sx, sy, half_width=19)


_SHAPE_DRAWERS = {
    "P": _draw_pawn, "R": _draw_rook, "N": _draw_knight,
    "B": _draw_bishop, "Q": _draw_queen, "K": _draw_king,
}


def _piece_sprite(kind: str, color: str, cell: int, sx: float = 1.0, sy: float = 1.0,
                   ring: bool = False, alpha: int = 255) -> Img:
    fill, outline = _palette(color)
    sprite = _canvas(cell)
    cx, cy = cell / 2.0, cell / 2.0 + 6
    if alpha < 255:
        fill = tuple(int(c * 0.7) for c in fill)
        outline = tuple(int(c * 0.7) for c in outline)
    _SHAPE_DRAWERS[kind](sprite, fill, outline, cx, cy, sx, sy)
    if alpha < 255:
        sprite.array[:, :, 3] = (sprite.array[:, :, 3].astype("float32") * (alpha / 255.0)).astype("uint8")
    if ring:
        sprite.draw_circle(int(cx), int(cy), int(38 * min(sx, sy)), (*MOVE_HIGHLIGHT, 255), thickness=2)
    return sprite


def idle_frames(color: str, kind: str, cell: int):
    return [_piece_sprite(kind, color, cell, 1.0, 1.0),
            _piece_sprite(kind, color, cell, 1.06, 1.06)]


def move_frames(color: str, kind: str, cell: int):
    return [_piece_sprite(kind, color, cell, 1.0, 1.0, ring=True),
            _piece_sprite(kind, color, cell, 1.06, 1.06, ring=True)]


def jump_frames(color: str, kind: str, cell: int):
    return [_piece_sprite(kind, color, cell, 1.18, 0.82),
            _piece_sprite(kind, color, cell, 0.85, 1.2)]


def short_rest_frames(color: str, kind: str, cell: int):
    # Lighter dim than long_rest for visual distinction.
    return [_piece_sprite(kind, color, cell, 1.0, 1.0, alpha=230),
            _piece_sprite(kind, color, cell, 1.0, 1.0, alpha=210)]


def long_rest_frames(color: str, kind: str, cell: int):
    return [_piece_sprite(kind, color, cell, 1.0, 1.0, alpha=200),
            _piece_sprite(kind, color, cell, 1.0, 1.0, alpha=140)]


STATE_BUILDERS = {
    "idle": idle_frames,
    "move": move_frames,
    "jump": jump_frames,
    "short_rest": short_rest_frames,
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
