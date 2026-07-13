"""Backward-compatible CLI entry point. The real implementation now lives
in the `kungfu_chess` package (Spec §5); this just forwards to it so
`python main.py` keeps working unchanged."""
from __future__ import annotations

from kungfu_chess.app import main

if __name__ == '__main__':  # pragma: no cover
    main()
