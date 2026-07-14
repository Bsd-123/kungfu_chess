"""`BoardView` -- thin coordinator, not a god object (plan section
7.2a). Owns no drawing logic of its own; just sequences its
collaborators. `overlay_renderer` is optional here because it doesn't
exist until Phase 3 -- passing `None` simply skips that step, so Phase 1
can use this exact class unchanged rather than a throwaway stand-in."""
from __future__ import annotations

from typing import Optional

from kungfu_chess.ui.img import Img
from kungfu_chess.ui.rendering.board_renderer import BoardRenderer
from kungfu_chess.ui.rendering.piece_renderer import PieceRenderer
from kungfu_chess.view.game_snapshot import GameSnapshot


class BoardView:
    def __init__(self, board_renderer: BoardRenderer,
                 piece_renderer: PieceRenderer,
                 overlay_renderer: Optional[object] = None):
        self._board = board_renderer
        self._pieces = piece_renderer
        self._overlay = overlay_renderer

    def render(self, snapshot: GameSnapshot, input_state=None) -> Img:
        frame = self._board.fresh_frame()
        self._pieces.draw(frame, snapshot)
        if self._overlay is not None:
            self._overlay.draw(frame, snapshot, input_state)
        return frame
