"""Secrets resolution: OS environment first, then project `.env` file."""
from __future__ import annotations

import os
from pathlib import Path

_loaded: dict[str, str] | None = None


def load_dotenv(path: Path) -> dict[str, str]:
    """Minimal .env parser (KEY=VALUE, '#' comments, no quotes handling)."""
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def env(key: str, default: str = "") -> str:
    global _loaded
    if _loaded is None:
        from app.config.paths import AppPaths

        _loaded = load_dotenv(AppPaths().env_path)
    return os.environ.get(key) or _loaded.get(key) or default
