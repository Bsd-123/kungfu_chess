"""Client-side read-only board view for `Controller`'s click handling
in remote (networked) mode. `GameSnapshot` (what the server actually
broadcasts) is pixel-coordinate based, built for rendering -- it can't
answer "what piece is at board Position(row, col)" without lossy
reverse pixel-mapping. Instead this mirror starts from the known
standard start position (Phase 2's server always starts one -- no
matchmaking/room-specific setups yet, see Phase 4/5) and stays in sync
purely from the relayed `MoveResolvedEvent`/`JumpResolvedEvent`, which
already carry exact board coordinates -- no pixel math needed."""
from __future__ import annotations

from kungfu_chess.model.board import ArrayBoard
from kungfu_chess.model.piece import Piece
from kungfu_chess.model.position import Position
from kungfu_chess.ui.events.events import JumpResolvedEvent, MoveResolvedEvent
from kungfu_chess.ui.setup import standard_start_rows


class RemoteBoardMirror(ArrayBoard):
    def __init__(self) -> None:
        super().__init__(standard_start_rows)

    def on_move_resolved(self, event: MoveResolvedEvent) -> None:
        piece = Piece(color=event.piece_color, type=event.piece_kind)
        self.set_piece_at(Position(event.dst_row, event.dst_col), piece)
        self.set_piece_at(Position(event.src_row, event.src_col), None)

    def on_jump_resolved(self, event: JumpResolvedEvent) -> None:
        # A jump lands back on its own source square; a captured_piece_kind
        # here just means an enemy piece occupied it and got overwritten.
        piece = Piece(color=event.piece_color, type=event.piece_kind)
        self.set_piece_at(Position(event.row, event.col), piece)
