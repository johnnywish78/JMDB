"""User settings: JSON-backed, typed defaults, autosave. No Qt dependency."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class Settings:
    THEME = "theme"
    ACCENT = "accent"
    BACKEND = "backend"               # auto | mpv | vlc | qt | external
    AUTOPLAY_NEXT = "autoplay_next"
    SUBTITLES = "subtitles_enabled"
    LIBRARY_FOLDERS = "library_folders"
    TMDB_API_KEY = "tmdb_api_key"
    OMDB_API_KEY = "omdb_api_key"
    SORT_MOVIES = "sort_movies"
    SORT_SHOWS = "sort_shows"
    VOLUME = "volume"                 # default playback volume 0-100
    BROWSER_HOME = "browser_home"     # browser default URL

    DEFAULTS: dict[str, Any] = {
        THEME: "dark",
        ACCENT: "amber",
        BACKEND: "auto",
        AUTOPLAY_NEXT: True,
        SUBTITLES: True,
        LIBRARY_FOLDERS: [],
        TMDB_API_KEY: "",
        OMDB_API_KEY: "",
        SORT_MOVIES: "rating",
        SORT_SHOWS: "rating",
        VOLUME: 70,
        BROWSER_HOME: "https://duckduckgo.com",
    }

    def __init__(self, path: Path):
        self._path = path
        self._data: dict[str, Any] = dict(self.DEFAULTS)
        self.load()

    def load(self) -> None:
        if self._path.exists():
            try:
                stored = json.loads(self._path.read_text(encoding="utf-8"))
                if isinstance(stored, dict):
                    self._data.update(stored)
            except (OSError, json.JSONDecodeError):
                pass  # corrupted settings fall back to defaults, never crash start

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._data, indent=2, ensure_ascii=False), encoding="utf-8")

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, self.DEFAULTS.get(key, default))

    def set(self, key: str, value: Any, autosave: bool = True) -> None:
        self._data[key] = value
        if autosave:
            self.save()
