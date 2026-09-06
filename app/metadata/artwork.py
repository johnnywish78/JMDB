"""Artwork manager: download, validate, resize, cache, deduplicate.

Artwork is downloaded once per URL into ``~/.jmdb/artwork/<kind>/`` with a
content-addressed filename (sha1 of URL), validated as a real image with
Pillow, optionally downscaled per the quality setting, and recorded in the
artwork table with the local path. Everything works offline from cache.
"""
from __future__ import annotations

import logging
from pathlib import Path

from app.config.paths import Paths
from app.database.repositories import Repositories
from app.metadata.http_client import HttpClient

logger = logging.getLogger(__name__)

QUALITY_MAX_WIDTH = {"high": None, "medium": 780, "low": 342}
ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp"}


class ArtworkManager:
    def __init__(
        self,
        paths: Paths,
        repos: Repositories,
        http: HttpClient,
        quality: str = "high",
    ) -> None:
        self.paths = paths
        self.repos = repos
        self.http = http
        self.quality = quality

    def set_quality(self, quality: str) -> None:
        self.quality = quality if quality in QUALITY_MAX_WIDTH else "high"

    # -- public API ------------------------------------------------------------
    def ensure_artwork(
        self,
        owner_type: str,
        owner_id: int,
        kind: str,
        url: str,
    ) -> str:
        """Make sure artwork exists locally; returns local path ('' on failure).

        Never raises: one broken URL must not stop other artwork.
        """
        if not url:
            return ""
        existing = self.repos.artwork.upsert(owner_type, owner_id, kind, source_url=url)
        if existing.local_path and Path(existing.local_path).exists():
            return existing.local_path
        try:
            local = self._download_and_process(url, kind)
        except Exception as exc:
            logger.warning("artwork download failed (%s): %s", url[:120], exc)
            return ""
        if not local:
            return ""
        width, height = self._dimensions(local)
        self.repos.artwork.set_local(existing.id, str(local), width, height)
        return str(local)

    def register_local(
        self, owner_type: str, owner_id: int, kind: str, path: str
    ) -> str:
        """Register an already-local image file (e.g. poster.jpg in a folder)."""
        if not Path(path).exists():
            return ""
        artwork = self.repos.artwork.upsert(
            owner_type, owner_id, kind, source_url="", local_path=str(path)
        )
        width, height = self._dimensions(path)
        self.repos.artwork.set_local(artwork.id, str(path), width, height)
        return str(path)

    # -- internals -----------------------------------------------------------------
    def _download_and_process(self, url: str, kind: str) -> Path | None:
        # content-addressed cache: same URL → same file, never re-downloaded
        ext = Path(url.split("?")[0]).suffix.lower()
        if ext not in ALLOWED_EXT:
            ext = ".jpg"
        dest = self.paths.unique_artwork_path(kind, url, ext)
        if dest.exists() and dest.stat().st_size > 0:
            return dest
        temp = dest.with_suffix(dest.suffix + ".part")
        try:
            self.http.download(url, temp, provider="artwork")
            if not self._is_valid_image(temp):
                temp.unlink(missing_ok=True)
                return None
            max_width = QUALITY_MAX_WIDTH.get(self.quality)
            if max_width:
                self._resize(temp, max_width)
            temp.replace(dest)
            return dest
        except Exception:
            temp.unlink(missing_ok=True)
            raise

    @staticmethod
    def _is_valid_image(path: Path) -> bool:
        try:
            from PIL import Image

            with Image.open(path) as img:
                img.verify()
            return True
        except Exception:
            return False

    @staticmethod
    def _dimensions(path: str | Path) -> tuple[int, int]:
        try:
            from PIL import Image

            with Image.open(path) as img:
                return img.size
        except Exception:
            return 0, 0

    @staticmethod
    def _resize(path: Path, max_width: int) -> None:
        from PIL import Image

        with Image.open(path) as img:
            if img.width <= max_width:
                return
            ratio = max_width / img.width
            resized = img.resize((max_width, int(img.height * ratio)), Image.LANCZOS)
            resized.save(path, quality=88)

    # -- maintenance -------------------------------------------------------------------
    def cache_size_bytes(self) -> int:
        total = 0
        if self.paths.artwork.exists():
            for file in self.paths.artwork.rglob("*"):
                if file.is_file():
                    total += file.stat().st_size
        return total

    def clear_cache(self) -> int:
        removed = 0
        if self.paths.artwork.exists():
            for file in self.paths.artwork.rglob("*"):
                if file.is_file():
                    file.unlink()
                    removed += 1
        self.repos.artwork.purge_missing_files()
        return removed
