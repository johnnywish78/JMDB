#!/usr/bin/env python3
"""JMDB launcher — one command, complete app.

    python run.py                 → Electron desktop app (production UI)
    python run.py --legacy-qt     → previous PyQt6 UI (legacy)
    python run.py --backend-only  → run just the local API server (dev)
    python run.py --theme dark    → set theme (dark|light|system), then launch
    python run.py --reset-db      → guarded, backup-first database reset

The Electron app and the Python backend talk over localhost HTTP+WebSocket
only. The backend binds 127.0.0.1 with a per-launch token; run.py owns the
backend process so nothing is left behind when the window closes.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ELECTRON_DIR = ROOT / "electron"


def _prepare_path() -> None:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))


def _find_free_port() -> int:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _apply_theme(theme: str) -> int:
    """Persist the theme choice, then continue launching normally."""
    _prepare_path()
    from app.bootstrap.dependencies import Dependencies
    from app.config.paths import Paths

    paths = Paths.create()
    paths.ensure_directories()
    deps = Dependencies()
    try:
        services = deps.build()
        if theme not in ("dark", "light", "system"):
            print(f"Unknown theme {theme!r}; use dark, light or system.", file=sys.stderr)
            return 2
        services.settings.set("theme", theme)
        print(f"Theme set to {theme}.")
        return -1  # signal: continue with normal launch
    finally:
        deps.close()


def _reset_database() -> int:
    """Backup-first, confirmation-guarded database reset.

    Never executed automatically — only when the user runs this flag and
    types the confirmation. A timestamped backup is always created first.
    """
    _prepare_path()
    from app.config.paths import Paths

    paths = Paths.create()
    database = paths.database_file
    if not database.exists():
        print(f"No database found at {database} — nothing to reset.")
        return 0

    print("This will RESET the JMDB database:")
    print(f"  {database}")
    print("A backup copy is created first, but watch history, favorites,")
    print("collections and settings will be lost from the fresh database.")
    print()
    try:
        answer = input("Type RESET to continue: ")
    except EOFError:
        answer = ""
    if answer.strip() != "RESET":
        print("Aborted — nothing was changed.")
        return 1

    backup = database.with_name(f"jmdb-backup-{time.strftime('%Y%m%d-%H%M%S')}.db")
    shutil.copy2(database, backup)
    print(f"Backup written: {backup}")
    database.unlink()
    print("Database removed. It will be recreated on the next start.")
    return 0


def _run_backend(port: int | None = None, log_level: str = "warning") -> tuple[int, object]:
    """Start the API server on a background thread. Returns (port, stop_fn)."""
    import uvicorn

    from app.api.auth import generate_token
    from app.api.server import create_app

    port = port or _find_free_port()
    token = generate_token()
    app = create_app(token=token)
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level=log_level, access_log=False)
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, name="jmdb-backend", daemon=True)
    thread.start()

    # wait for health
    import urllib.request
    import urllib.error

    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=2) as response:
                if response.status == 200:
                    return port, server
        except (urllib.error.URLError, OSError):
            time.sleep(0.2)
    raise RuntimeError("backend did not become healthy in time")


def _run_electron(backend_port: int) -> int:
    """Launch the Electron frontend against our backend; blocks until exit."""
    electron = ELECTRON_DIR / "node_modules" / ".bin" / "electron"
    if not electron.exists():
        # windows npm layout
        electron_cmd = str(ELECTRON_DIR / "node_modules" / ".bin" / "electron.cmd")
        if Path(electron_cmd).exists():
            electron = Path(electron_cmd)
        else:
            print(
                "Electron is not installed yet. Run once:\n"
                "    cd electron && npm install\n"
                "(or use `python run.py --legacy-qt` for the previous UI)",
                file=sys.stderr,
            )
            return 1

    env = dict(os.environ)
    env["JMDB_BACKEND_URL"] = f"http://127.0.0.1:{backend_port}"
    env.setdefault("JMDB_PYTHON", sys.executable)

    process = subprocess.Popen(
        [str(electron), "."],
        cwd=ELECTRON_DIR,
        env=env,
    )
    try:
        return process.wait()
    except KeyboardInterrupt:
        process.terminate()
        try:
            return process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            return process.wait()


def main() -> int:
    parser = argparse.ArgumentParser(prog="jmdb", description="JMDB — Johnny Media Database")
    parser.add_argument("--legacy-qt", action="store_true", help="run the previous PyQt6 UI (legacy)")
    parser.add_argument("--backend-only", action="store_true", help="run only the local API server")
    parser.add_argument("--port", type=int, default=None, help="port for --backend-only (default: random free port)")
    parser.add_argument("--theme", choices=["dark", "light", "system"], help="set the theme, then launch")
    parser.add_argument("--reset-db", action="store_true", help="backup-first, confirmation-guarded database reset")
    parser.add_argument("--dev", action="store_true", help="developer mode (verbose logs, devtools enabled)")
    args = parser.parse_args()

    if args.reset_db:
        return _reset_database()

    if args.theme:
        result = _apply_theme(args.theme)
        if result >= 0:
            return result

    _prepare_path()

    if args.legacy_qt:
        try:
            from app.bootstrap.application import run as run_qt
        except ImportError as exc:
            print(
                f"Legacy Qt UI cannot start: missing dependency ({exc}).\n\n"
                "Install requirements first:\n    pip install -r requirements.txt",
                file=sys.stderr,
            )
            return 1
        return run_qt()

    if args.backend_only:
        from app.api.__main__ import main as run_api

        port = args.port or _find_free_port()
        # the API CLI writes the launch token to JMDB_HOME/api_token.json (0600)
        from app.config.paths import Paths

        token_file = Paths.create().home / "api_token.json"
        print(f"JMDB API listening on http://127.0.0.1:{port} (token in {token_file})")
        return run_api([
            "--port", str(port),
            "--token-file", str(token_file),
        ])

    # default: Electron frontend + in-process backend
    try:
        port, server = _run_backend()
    except Exception as exc:  # noqa: BLE001 - report any startup failure cleanly
        print(f"JMDB backend failed to start: {exc}", file=sys.stderr)
        return 1

    try:
        return _run_electron(port)
    finally:
        server.should_exit = True


if __name__ == "__main__":
    raise SystemExit(main())
