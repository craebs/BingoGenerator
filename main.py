# General Bingo Generator
# Copyright (c) 2026 Craebs Media
# Licensed under the PolyForm Noncommercial License 1.0.0
#
# Author: Craebs Media
#
# Application entry point. Run with: python main.py

from __future__ import annotations

from pathlib import Path

from gui.app import BingoApp


if __name__ == "__main__":
    root_dir = Path(__file__).resolve().parent
    app = BingoApp(root_dir=root_dir)
    app.mainloop()
