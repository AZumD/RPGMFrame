#!/usr/bin/env python3
"""RPGMFrame desktop GUI entry point for source and PyInstaller builds."""

from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from rpgmframe.gui import main


if __name__ == "__main__":
    main()
