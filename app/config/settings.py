"""Application settings model and persistence.

Settings persist to ``~/.jmdb/config/settings.json`` (outside the repository,
survives database resets). API keys are *not* settings — they go through
:class:`app.config.secrets.SecretsStore`.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

DEFAULTS = {
    # General
    "first_run_completed": False,
    "startup_screen": "home",
    "confirm_before_delete": True,
    # Appearance
    "theme": "system",  # dark | light | system
    "poster_card_width": 190,
    # Library scanning
    "scan_hidden_directories": False,
    "follow_symlinks": False,
    "probe_media_files": True,
    "auto_enrich_metadata": True,
    "auto_refresh_metadata_days": 30,
    "duplicate_min_size_mb": 50,
    # Metadata
    "metadata_language": "en-US",
    "provider_priority": ["tmdb", "omdb", "tvmaze", "itunes"],
    "music_provider_priority": ["musicbrainz", "theaudiodb", "lastfm"],
    "metadata_cache_days": 14,
    "metadata_timeout_seconds": 10,
    "metadata_retries": 2,
    # Artwork
    "artwork_quality": "high",  # high=original, medium<=780, low<=342
    "download_backdrops": True,
    "artwork_revalidate_days": 30,
    # Playback
    "playback_backend": "auto",  # auto | vlc | mpv | qt | external
    "external_player_path": "",  # empty = auto-detect
    "autoplay_next": True,  # autoplay next episode/track when one finishes
    "player_default_volume": 90,  # 0-100
    "resume_min_seconds": 10,  # don't offer resume below this
    "resume_completion_pct": 95,  # consider finished above this
    "mark_watched_pct": 90,
    "seek_step_seconds": 10,
    "volume_step": 5,
    "default_subtitle_language": "",
    "default_audio_language": "",
    # Browser
    "browser_home_url": "jmdb://home",
    "browser_search_engine": "duckduckgo",  # google|duckduckgo|bing|brave|startpage
    "browser_default_zoom": 100,  # percent, 50-300, applied to new Browser Hub tabs
    "browser_enable_javascript": True,
    "browser_allow_cookies": True,
    "browser_external": "auto",  # auto | chrome | chromium | firefox | edge | default
    # Notifications
    "notify_scan": True,
    "notify_metadata": True,
    "notify_playback": False,
    "toast_duration_ms": 4000,
    # Advanced
    "log_level": "INFO",
    "cache_location": "",  # empty = default (~/.jmdb/cache)
}

VALID_THEMES = {"dark", "light", "system"}
VALID_BACKENDS = {"auto", "vlc", "mpv", "qt", "external"}
VALID_QUALITY = {"high", "medium", "low"}


class SettingsError(ValueError):
    pass


def _coerce(raw: Any, default: Any) -> Any:
    """Coerce a JSON-loaded value into the type of the default."""
    if isinstance(default, bool):
        return bool(raw)
    if isinstance(default, int) and not isinstance(default, bool):
        try:
            return int(raw)
        except (TypeError, ValueError):
            return default
    if isinstance(default, float):
        try:
            return float(raw)
        except (TypeError, ValueError):
            return default
    if isinstance(default, list):
        if isinstance(raw, list):
            return [str(x) for x in raw]
        return list(default)
    return str(raw)


class SettingsService:
    """Typed, thread-safe access to persisted application settings."""

    def __init__(self, config_dir: Path) -> None:
        self._file = config_dir / "settings.json"
        self._lock = threading.RLock()
        self._values: dict[str, Any] = dict(DEFAULTS)
        self._listeners: list[Callable[[str, Any, Any], None]] = []
        self.load()

    # -- persistence ----------------------------------------------------
    def load(self) -> None:
        with self._lock:
            raw: dict = {}
            try:
                if self._file.exists():
                    loaded = json.loads(self._file.read_text("utf-8"))
                    if not isinstance(loaded, dict):
                        raise ValueError("settings file is not an object")
                    raw = loaded
            except (OSError, ValueError) as exc:
                logger.warning("Could not load settings (%s); using defaults", exc)
                raw = {}
            for key, default in DEFAULTS.items():
                if key in raw:
                    self._values[key] = _coerce(raw[key], default)

    def save(self) -> None:
        with self._lock:
            self._file.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._file.with_suffix(".tmp")
            tmp.write_text(
                json.dumps(self._values, indent=2, sort_keys=True), "utf-8"
            )
            tmp.replace(self._file)

    # -- access ---------------------------------------------------------
    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            if key in self._values:
                return self._values[key]
            return DEFAULTS.get(key, default)

    def set(self, key: str, value: Any, persist: bool = True) -> None:
        if key not in DEFAULTS:
            raise SettingsError(f"Unknown setting: {key}")
        coerced = _coerce(value, DEFAULTS[key])
        self._validate(key, coerced)
        with self._lock:
            old = self._values.get(key)
            self._values[key] = coerced
        if persist:
            self.save()
        for listener in list(self._listeners):
            try:
                listener(key, old, coerced)
            except Exception:  # pragma: no cover - listener isolation
                logger.exception("settings listener failed")

    def set_many(self, values: dict[str, Any], persist: bool = True) -> None:
        for key, value in values.items():
            self.set(key, value, persist=False)
        if persist:
            self.save()

    def as_dict(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._values)

    def defaults(self) -> dict[str, Any]:
        return dict(DEFAULTS)

    def reset(self, key: str) -> None:
        self.set(key, DEFAULTS[key])

    # -- change notification ---------------------------------------------
    def on_change(self, listener: Callable[[str, Any, Any], None]) -> None:
        self._listeners.append(listener)

    # -- validation -------------------------------------------------------
    @staticmethod
    def _validate(key: str, value: Any) -> None:
        if key == "browser_default_zoom" and not (50 <= int(value) <= 300):
            raise SettingsError("browser_default_zoom must be between 50 and 300")
        if key == "theme" and value not in VALID_THEMES:
            raise SettingsError(f"theme must be one of {sorted(VALID_THEMES)}")
        if key == "playback_backend" and value not in VALID_BACKENDS:
            raise SettingsError(
                f"playback_backend must be one of {sorted(VALID_BACKENDS)}"
            )
        if key == "artwork_quality" and value not in VALID_QUALITY:
            raise SettingsError(
                f"artwork_quality must be one of {sorted(VALID_QUALITY)}"
            )
        if key == "metadata_language":
            value = str(value)
