"""API-key / secret handling.

Keys are resolved in this order (first non-empty wins):

1. environment variables (``TMDB_API_KEY`` etc.)
2. ``~/.jmdb/config/secrets.json``  (written by the Settings screen; never
   committed, lives outside the repository)

Secrets are never logged: :class:`SecretRedactor` installs itself on the
logging machinery and masks any configured secret value found in records.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any

ENV_VARS = {
    "tmdb": "TMDB_API_KEY",
    "omdb": "OMDB_API_KEY",
    "fanarttv": "FANART_TV_API_KEY",
    "lastfm": "LASTFM_API_KEY",
    "theaudiodb": "THEAUDIODB_API_KEY",
}

PROVIDER_LABELS = {
    "tmdb": "TMDB",
    "omdb": "OMDb",
    "fanarttv": "Fanart.tv",
    "lastfm": "Last.fm",
    "theaudiodb": "TheAudioDB",
}


class SecretRedactor(logging.Filter):
    """Mask secret values anywhere they appear in a log record."""

    def __init__(self) -> None:
        super().__init__()
        self._secrets: list[str] = []
        self._lock = threading.Lock()

    def set_secrets(self, values: list[str]) -> None:
        with self._lock:
            self._secrets = [v for v in values if v and len(v) >= 4]

    def _mask(self, text: Any) -> Any:
        if not isinstance(text, str) or not self._secrets:
            return text
        for secret in self._secrets:
            if secret in text:
                text = text.replace(secret, "***REDACTED***")
        return text

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = self._mask(record.getMessage())
        record.args = ()
        if record.exc_info:
            exc = record.exc_info
            if exc and exc[1] is not None:
                try:
                    exc[1].args = tuple(
                        self._mask(a) if isinstance(a, str) else a
                        for a in (exc[1].args or ())
                    )
                except Exception:  # pragma: no cover - best effort
                    pass
        return True


class SecretsStore:
    """Load/store provider keys in a local JSON file outside the repo."""

    def __init__(self, config_dir: Path, env: dict[str, str] | None = None) -> None:
        self._file = config_dir / "secrets.json"
        self._env = env if env is not None else dict(os.environ)
        self._lock = threading.RLock()
        self._cache: dict[str, str] | None = None

    # -- file ----------------------------------------------------------
    def _load(self) -> dict[str, str]:
        with self._lock:
            if self._cache is None:
                data: dict[str, str] = {}
                try:
                    if self._file.exists():
                        raw = json.loads(self._file.read_text("utf-8"))
                        if isinstance(raw, dict):
                            data = {str(k): str(v) for k, v in raw.items()}
                except (OSError, json.JSONDecodeError):
                    data = {}
                self._cache = data
            return self._cache

    def _save(self, data: dict[str, str]) -> None:
        with self._lock:
            self._file.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._file.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, indent=2), "utf-8")
            tmp.replace(self._file)
            os.chmod(self._file, 0o600)
            self._cache = dict(data)

    # -- API -----------------------------------------------------------
    def get(self, provider: str) -> str:
        env_name = ENV_VARS.get(provider)
        if env_name:
            env_value = (self._env.get(env_name) or "").strip()
            if env_value:
                return env_value
        return self._load().get(provider, "")

    def set(self, provider: str, value: str) -> None:
        data = dict(self._load())
        if value:
            data[provider] = value.strip()
        else:
            data.pop(provider, None)
        self._save(data)

    def all_providers(self) -> dict[str, str]:
        return {p: self.get(p) for p in ENV_VARS}

    def active_secrets(self) -> list[str]:
        return [v for v in self.all_providers().values() if v]
