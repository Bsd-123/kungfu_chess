"""UI composition root (final_plan_verified.md Phase 0).

Wires the existing engine factory + Controller together for the live
GUI session. Deliberately does nothing else yet: no window, no
rendering, no game loop -- those are Phase 1+. Running this module
directly boots the engine and prints a quick sanity summary of the
starting snapshot, which is Phase 0's exit criteria (engine boots,
`snapshot()` returns the starting position, no window opened).
"""
from __future__ import annotations
from typing import Tuple

from kungfu_chess.app import build_game_engine
from kungfu_chess.config import GameConfig
from kungfu_chess.engine.game_engine import GameEngine
from kungfu_chess.input.controller import Controller
from kungfu_chess.ui.setup import standard_start_rows


def build_session(config: GameConfig = None) -> Tuple[GameEngine, Controller]:
    """Boots one GameEngine + one Controller for the session, mirroring
    ClickCommand's one-per-engine caching (plan Phase 0 step 3). Reuses
    the already-existing `build_game_engine` factory rather than
    rebuilding engine wiring here."""
    config = config or GameConfig()
    engine = build_game_engine(standard_start_rows, config)
    controller = Controller(engine, config.cell_pixel_size)
    return engine, controller


def main() -> None:  # pragma: no cover
    engine, _controller = build_session()
    snapshot = engine.snapshot()
    print(
        f"Engine booted: {snapshot.board_width}x{snapshot.board_height} board, "
        f"{len(snapshot.pieces)} pieces, game_over={snapshot.game_over}"
    )


if __name__ == '__main__':  # pragma: no cover
    main()
