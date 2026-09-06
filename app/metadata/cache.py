"""Metadata cache facade over the metadata_cache table."""
from __future__ import annotations

from app.database.repositories import MetadataCacheRepository


class MetadataCache:
    def __init__(self, repo: MetadataCacheRepository, ttl_days: int = 14) -> None:
        self.repo = repo
        self.ttl_days = ttl_days

    def get(self, provider: str, object_type: str, key: str):
        return self.repo.get(provider, object_type, key)

    def put(self, provider: str, object_type: str, key: str, payload) -> None:
        self.repo.put(provider, object_type, key, payload, ttl_days=self.ttl_days)

    def purge_expired(self) -> int:
        return self.repo.purge_expired()
