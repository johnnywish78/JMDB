"""Indexer: writes detector output into repositories (idempotent upserts)."""
from __future__ import annotations

import json

from app.database.repositories import EpisodeRepository, MediaRepository
from app.domain.enums import MediaKind
from app.domain.models import DetectedMedia


class LibraryIndexer:
    def __init__(self, media_repo: MediaRepository, episode_repo: EpisodeRepository):
        self.media_repo = media_repo
        self.episode_repo = episode_repo

    def index(self, detected: DetectedMedia) -> int:
        if detected.kind == MediaKind.EPISODE:
            return self._index_episode(detected)
        kind = detected.kind.value if detected.kind != MediaKind.SHOW else "show"
        return self.media_repo.upsert(kind, detected.title, detected.year,
                                      file_path=detected.path)

    def _index_episode(self, detected: DetectedMedia) -> int:
        show_id = self._ensure_show(detected)
        return self.episode_repo.upsert(
            show_id, int(detected.season or 1), int(detected.number or 1),
            file_path=detected.path)

    def _ensure_show(self, detected: DetectedMedia) -> int:
        show_id = self.media_repo.upsert("show", detected.title, detected.year)
        if detected.season:
            row = self.media_repo.get(show_id) or {}
            seasons = set(row.get("seasons") or [])
            if int(detected.season) not in seasons:
                seasons.add(int(detected.season))
                self.media_repo.upsert("show", detected.title, detected.year,
                                       seasons=sorted(seasons))
        return show_id


class DuplicateDetector:
    """Report duplicates by normalized title (same name, different files)."""
    def __init__(self, media_repo: MediaRepository):
        self.media_repo = media_repo

    def movies(self) -> list[tuple[str, int]]:
        groups: dict[str, int] = {}
        for row in self.media_repo.list(MediaKind.MOVIE, sort="title"):
            key = f"{row['title'].casefold()}|{row.get('year')}"
            groups[key] = groups.get(key, 0) + 1
        return sorted([(k, n) for k, n in groups.items() if n > 1])

    def summary_json(self) -> str:
        return json.dumps({"movie_duplicates": self.movies()}, ensure_ascii=False)
