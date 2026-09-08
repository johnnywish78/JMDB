#!/usr/bin/env python3
"""Headless environment probe. Usage:
    python scripts/diagnostics.py            # report
    python scripts/diagnostics.py --json
    python scripts/diagnostics.py --migrate  # apply pending migrations
    python scripts/diagnostics.py --reset    # DELETE the database (asks)
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

MODULES = ["PyQt6", "requests", "vlc", "mpv", "PyQt6.QtWebEngineWidgets"]


def probe_module(name: str) -> str:
    try:
        if "." in name:  # submodule: parent import needed
            parent, _, _mod = name.rpartition(".")
            if importlib.util.find_spec(parent) is None:
                return "missing (parent not installed)"
        return "ok" if importlib.util.find_spec(name) else "not installed (optional)"
    except Exception as exc:
        return f"probe error: {exc}"


def main() -> int:
    parser = argparse.ArgumentParser(prog="jmdb-diagnostics")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--migrate", action="store_true")
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()

    from app.config.paths import AppPaths

    paths = AppPaths().ensure()
    report: dict = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "db_path": str(paths.db_path),
        "db_exists": paths.db_path.exists(),
        "db_size_kb": round(paths.db_path.stat().st_size / 1024, 1) if paths.db_path.exists() else 0,
        "modules": {m: probe_module(m) for m in MODULES},
    }

    if args.reset:
        if paths.db_path.exists():
            answer = input(f"Delete {paths.db_path}? [y/N] ")
            if answer.lower() == "y":
                paths.db_path.unlink()
                report["reset"] = "deleted"
        return _emit(report, args.json)

    # database state
    try:
        from app.database.connection import Database
        from app.database.migrations import migrate

        db = Database(paths.db_path)
        db.connect()
        report["schema_version"] = migrate(db) if args.migrate else int(
            db.query_one("PRAGMA user_version")["user_version"])
        for kind in ("movie", "show", "music"):
            report[f"count_{kind}"] = db.query_one(
                "SELECT COUNT(*) AS n FROM media WHERE kind=?", (kind,))["n"]
        report["episodes"] = db.query_one("SELECT COUNT(*) AS n FROM episodes")["n"]
        report["history"] = db.query_one("SELECT COUNT(*) AS n FROM watch_history")["n"]
        # FTS sanity
        report["fts5"] = "ok" if db.query_one(
            "SELECT name FROM sqlite_master WHERE name='media_fts'") else "missing"
        db.close()
    except Exception as exc:
        report["db_error"] = str(exc)

    # last log lines
    if paths.log_file.exists():
        lines = paths.log_file.read_text(encoding="utf-8", errors="replace").splitlines()
        report["log_tail"] = lines[-5:]
    return _emit(report, args.json)


def _emit(report: dict, as_json: bool) -> int:
    if as_json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        for key, value in report.items():
            if isinstance(value, dict):
                print(f"{key}:")
                for k, v in value.items():
                    print(f"  {k}: {v}")
            elif isinstance(value, list):
                print(f"{key}:")
                for line in value:
                    print(f"  {line}")
            else:
                print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
