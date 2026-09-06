#!/usr/bin/env python3
"""JMDB launcher.

Usage: python run.py
"""
from __future__ import annotations

import sys
from pathlib import Path


def _prepare_path() -> None:
    root = Path(__file__).resolve().parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


def main() -> int:
    _prepare_path()
    try:
        from app.bootstrap.application import run
    except ImportError as exc:
        print(
            f"JMDB cannot start: missing dependency ({exc}).\n\n"
            "Install requirements first:\n"
            "    pip install -r requirements.txt\n\n"
            "For the embedded browser also:\n"
            "    pip install PyQt6-WebEngine",
            file=sys.stderr,
        )
        return 1
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
