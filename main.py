"""CLI entry point. Forwards to `kungfu_chess.app.main`, where the
actual implementation lives."""
from __future__ import annotations

from kungfu_chess.app import main

if __name__ == "__main__":
    main()
