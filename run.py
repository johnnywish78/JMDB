#!/usr/bin/env python3
"""JMDB — Johnny Media Database. Application entry point.

Usage:
    python run.py            # Launch JMDB Desktop (Electron)
    python run.py --theme dark
    python run.py --dev      # Development mode with Electron + backend separately
    python run.py --backend  # Start only the Python backend (for debugging)
    python run.py --reset-db # Drop local database before start

Architecture:
    The primary desktop UI is Electron. The Python backend (FastAPI) runs
    as a local subprocess and is managed by the Electron main process.
    Legacy PyQt6 remains available via `python run.py --legacy`.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(prog="jmdb", description="Johnny Media Database")
    parser.add_argument("--theme", choices=["dark", "light"], default=None)
    parser.add_argument("--reset-db", action="store_true", help="delete the local database before start")
    parser.add_argument("--dev", action="store_true", help="development mode: start backend + electron separately")
    parser.add_argument("--backend", action="store_true", help="start only the Python FastAPI backend")
    parser.add_argument("--legacy", action="store_true", help="use legacy PyQt6 UI instead of Electron")
    args = parser.parse_args()

    if args.reset_db:
        from app.config.paths import AppPaths
        db_path = AppPaths().db_path
        if db_path.exists():
            db_path.unlink()
            print(f"[jmdb] removed {db_path}")

    # Legacy mode: PyQt6
    if args.legacy:
        return _run_legacy(args.theme)

    # Backend-only mode
    if args.backend:
        return _run_backend()

    # Default: launch Electron (which manages the backend)
    return _run_electron(args.dev, args.theme)


def _run_backend() -> int:
    """Start only the Python FastAPI backend server."""
    from app.api.serve import main as serve_main
    return serve_main()


def _run_electron(dev: bool = False, theme: str | None = None) -> int:
    """Launch Electron with the project's main process."""
    electron_path = ROOT / "node_modules" / ".bin" / "electron"
    if not electron_path.exists():
        print(f"[jmdb] Electron not found at {electron_path}", file=sys.stderr)
        print("Run: npm install --prefix electron", file=sys.stderr)
        return 1

    env = os.environ.copy()
    if theme:
        env["JMDB_THEME"] = theme

    cmd = [str(electron_path), str(ROOT / "electron" / "main.js")]
    if dev:
        cmd.append("--dev")

    print("[jmdb] Starting Electron frontend…", flush=True)
    result = subprocess.run(cmd, env=env, cwd=str(ROOT), check=False)
    return result.returncode


def _run_legacy(theme: str | None = None) -> int:
    """Fall back to the legacy PyQt6 startup for compatibility."""
    from app.bootstrap.startup import run
    return run(theme_override=theme)


if __name__ == "__main__":
    raise SystemExit(main())
