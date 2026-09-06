"""Platform-aware data paths for JMDB.

All runtime data lives under a single home directory (default ``~/.jmdb``)
so the repository itself never stores user media, secrets, or caches.

The home can be relocated with the ``JMDB_HOME`` environment variable which
keeps tests hermetic and lets users put data on another disk.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ENV_HOME = "JMDB_HOME"


def default_home() -> Path:
    override = os.environ.get(ENV_HOME)
    if override:
        return Path(override).expanduser().resolve()
    return Path.home() / ".jmdb"


@dataclass(frozen=True)
class Paths:
    """Resolved runtime paths. Construct via :meth:`create`."""

    home: Path
    database: Path = field(init=False)
    cache: Path = field(init=False)
    artwork: Path = field(init=False)
    thumbnails: Path = field(init=False)
    downloads: Path = field(init=False)
    logs: Path = field(init=False)
    config: Path = field(init=False)
    browser_profile: Path = field(init=False)
    database_file: Path = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "database", self.home / "database")
        object.__setattr__(self, "cache", self.home / "cache")
        object.__setattr__(self, "artwork", self.home / "artwork")
        object.__setattr__(self, "thumbnails", self.home / "thumbnails")
        object.__setattr__(self, "downloads", self.home / "downloads")
        object.__setattr__(self, "logs", self.home / "logs")
        object.__setattr__(self, "config", self.home / "config")
        object.__setattr__(
            self, "browser_profile", self.home / "browser" / "profile"
        )
        object.__setattr__(self, "database_file", self.database / "jmdb.db")

    @classmethod
    def create(cls, home: Path | None = None) -> "Paths":
        return cls(home=(home or default_home()).expanduser().resolve())

    def ensure_directories(self) -> None:
        for directory in (
            self.home,
            self.database,
            self.cache,
            self.artwork,
            self.thumbnails,
            self.downloads,
            self.logs,
            self.config,
            self.browser_profile,
        ):
            directory.mkdir(parents=True, exist_ok=True)

    # Artwork kind subdirectories -------------------------------------
    def artwork_dir(self, kind: str) -> Path:
        directory = self.artwork / kind
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def unique_artwork_path(self, kind: str, url: str, ext: str) -> Path:
        import hashlib

        digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:24]
        return self.artwork_dir(kind) / f"{digest}{ext}"

    def __str__(self) -> str:  # pragma: no cover - debug helper
        return f"Paths(home={self.home})"
