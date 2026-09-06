"""Browser profile management (disk locations under ~/.jmdb/browser)."""
from __future__ import annotations

import shutil

from app.config.paths import Paths


class ProfileManager:
    def __init__(self, paths: Paths) -> None:
        self.paths = paths

    def ensure_profile_dir(self) -> str:
        self.paths.browser_profile.mkdir(parents=True, exist_ok=True)
        return str(self.paths.browser_profile)

    def cache_size_bytes(self) -> int:
        total = 0
        if self.paths.browser_profile.exists():
            for item in self.paths.browser_profile.rglob("*"):
                try:
                    if item.is_file():
                        total += item.stat().st_size
                except OSError:
                    pass
        return total

    def clear_cache(self) -> None:
        if self.paths.browser_profile.exists():
            for child in self.paths.browser_profile.iterdir():
                try:
                    if child.is_dir():
                        shutil.rmtree(child)
                    else:
                        child.unlink()
                except OSError:
                    pass
        self.ensure_profile_dir()
