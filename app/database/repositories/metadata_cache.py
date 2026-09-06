"""Metadata cache + provider-source tracking repositories."""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from app.database.repositories import BaseRepository


class MetadataCacheRepository(BaseRepository):
    def get(self, provider: str, object_type: str, external_key: str) -> dict | list | None:
        row = self.db.query_one(
            "SELECT payload_json, expires_at FROM metadata_cache"
            " WHERE provider=? AND object_type=? AND external_key=?",
            (provider, object_type, external_key),
        )
        if row is None:
            return None
        try:
            expires = datetime.fromisoformat(row["expires_at"])
        except ValueError:
            expires = datetime.utcnow() - timedelta(seconds=1)
        if expires < datetime.utcnow():
            return None
        try:
            return json.loads(row["payload_json"])
        except (ValueError, TypeError):
            return None

    def put(
        self,
        provider: str,
        object_type: str,
        external_key: str,
        payload: dict | list,
        ttl_days: int = 14,
    ) -> None:
        expires = (datetime.utcnow() + timedelta(days=ttl_days)).isoformat()
        self.db.execute(
            "INSERT INTO metadata_cache (provider, object_type, external_key, payload_json,"
            " fetched_at, expires_at) VALUES (?,?,?,?,datetime('now'),?)"
            " ON CONFLICT(provider, object_type, external_key) DO UPDATE SET"
            " payload_json=excluded.payload_json, fetched_at=excluded.fetched_at,"
            " expires_at=excluded.expires_at",
            (provider, object_type, external_key, json.dumps(payload), expires),
        )

    def purge_expired(self) -> int:
        cur = self.db.execute(
            "DELETE FROM metadata_cache WHERE expires_at < datetime('now')"
        )
        return cur.rowcount

    def entry_count(self) -> int:
        return int(self.db.scalar("SELECT COUNT(*) FROM metadata_cache") or 0)


class MetadataSourcesRepository(BaseRepository):
    def record(self, media_type: str, media_id: int, provider: str) -> None:
        self.db.execute(
            "INSERT INTO metadata_sources (media_type, media_id, provider)"
            " VALUES (?,?,?)"
            " ON CONFLICT(media_type, media_id, provider)"
            " DO UPDATE SET fetched_at=datetime('now')",
            (media_type, media_id, provider),
        )

    def providers_for(self, media_type: str, media_id: int) -> list[str]:
        rows = self.db.query(
            "SELECT provider FROM metadata_sources WHERE media_type=? AND media_id=?",
            (media_type, media_id),
        )
        return [r["provider"] for r in rows]

    def last_fetched(self, media_type: str, media_id: int) -> str | None:
        return self.db.scalar(
            "SELECT MAX(fetched_at) FROM metadata_sources WHERE media_type=? AND media_id=?",
            (media_type, media_id),
        )

    def stale_items(self, older_than_days: int, media_type: str, limit: int = 50) -> list[int]:
        cutoff = (datetime.utcnow() - timedelta(days=older_than_days)).isoformat(sep=" ")
        rows = self.db.query(
            "SELECT id FROM " + media_type + " WHERE NOT EXISTS ("
            " SELECT 1 FROM metadata_sources ms WHERE ms.media_type=? AND ms.media_id=" + media_type + ".id"
            " AND ms.fetched_at > ?) LIMIT ?",
            (media_type, cutoff, limit),
        )
        return [r["id"] for r in rows]
