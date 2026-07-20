"""UI entry point: re-exports key constants from composition.py/layout.py
and provides `main()`, wiring composition.py (construction), layout.py
(screen geometry), and game_loop.py (runtime loop).

The board isn't at screen origin -- side panels and name/score bands
surround it, so `layout.Layout`'s offsets are threaded through every
renderer plus `MouseRouter` (which subtracts them back out before
board-space clicks reach `Controller`).

`main()` defaults to local, single-process play (offline mode is kept,
not deleted); pass `--server ws://host:port` to instead connect to a
`KungFuChessServer` (Phase 2) -- this is the "config flag" the master
work plan calls for to pick local-bus-only vs. local-bus-plus-network-
adapter wiring."""
from __future__ import annotations

import argparse

from kungfu_chess.config import GameConfig
from kungfu_chess.ui.composition import (
    ASSET_ROOT,
    BOARD_BACKGROUND_PATH,
    DEFAULT_PLAYER_NAMES,
    build_board_view,
    build_remote_session,
    build_session,
    wire_event_observers,
    wire_remote_event_observers,
)
from kungfu_chess.ui.game_loop import run_loop
from kungfu_chess.ui.layout import BOARD_COLS, BOARD_ROWS, Layout

__all__ = [
    "ASSET_ROOT", "BOARD_BACKGROUND_PATH", "BOARD_COLS", "BOARD_ROWS",
    "DEFAULT_PLAYER_NAMES", "Layout", "build_session", "build_remote_session",
    "wire_event_observers", "wire_remote_event_observers",
    "build_board_view", "run_loop", "main",
]


def main() -> None:  # pragma: no cover
    from kungfu_chess.ui.rendering.cv2_renderer import Cv2Renderer

    parser = argparse.ArgumentParser(description="KungFu Chess")
    parser.add_argument(
        "--server", metavar="URL", default=None,
        help="Connect to a KungFuChessServer at this ws:// URL (e.g. "
             "ws://localhost:8765) instead of playing a local, "
             "single-process game.")
    args = parser.parse_args()

    config = GameConfig()
    board_view, layout = build_board_view(config)
    renderer = Cv2Renderer()

    if args.server:
        proxy, controller, network_client = build_remote_session(args.server, config)
        move_log, score, event_bus = wire_remote_event_observers(
            proxy, board_view.piece_renderer, config=config)
        try:
            run_loop(proxy, controller, board_view, renderer, layout,
                     move_log=move_log, score=score,
                     network_client=network_client, event_bus=event_bus)
        finally:
            network_client.close()
    else:
        engine, controller = build_session(config)
        move_log, score = wire_event_observers(engine, board_view.piece_renderer, config=config)
        run_loop(engine, controller, board_view, renderer, layout,
                 move_log=move_log, score=score)


if __name__ == '__main__':  # pragma: no cover
    main()
