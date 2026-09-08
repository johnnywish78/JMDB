"""Filesystem layout for JMDB. All data lives under <root>/data."""
from __future__ import annotations

from pathlib import Path


class AppPaths:
    def __init__(self, root: Path | None = None):
        self.root = root or Path(__file__).resolve().parents[2]  # JMDB/
        self.data_dir = self.root / "data"
        self.database_dir = self.data_dir / "database"
        self.cache_dir = self.data_dir / "cache"
        self.artwork_dir = self.data_dir / "artwork"
        self.thumbs_dir = self.data_dir / "thumbnails"
        self.downloads_dir = self.data_dir / "downloads"
        self.logs_dir = self.data_dir / "logs"

    @property
    def db_path(self) -> Path:
        return self.database_dir / "jmdb.db"

    @property
    def settings_path(self) -> Path:
        return self.data_dir / "settings.json"

    @property
    def env_path(self) -> Path:
        return self.root / ".env"

    @property
    def log_file(self) -> Path:
        return self.logs_dir / "jmdb.log"

    def ensure(self) -> AppPaths:
        for d in (
            self.data_dir, self.database_dir, self.cache_dir, self.artwork_dir,
            self.thumbs_dir, self.downloads_dir, self.logs_dir,
        ):
            d.mkdir(parents=True, exist_ok=True)
            keep = d / ".gitkeep"
            if not keep.exists():
                keep.touch()
        return self
