"""SQLite-backed JSON cache with TTL, provider tracking, and invalidation."""
from __future__ import annotations

import json
import time
from typing import Any

from app.database.connection import Database

CACHE_SCHEMA_VERSION = 2
# Buckets map to media kinds stored in the cache.
BUCKET_MOVIE = "movie"
BUCKET_SERIES = "series"
BUCKET_MUSIC = "music"


class MetadataCache:
    """SQL-backed positive-result cache.

    Each entry tracks (bucket, key, provider, payload, created_at).
    • TTL 30 days for successful results.
    • Failed look-ups are NOT cached (no negative caching by default).
    • ``clear(...)`` supports targeted or global invalidation.
    """

    CREATE_SQL = """
        CREATE TABLE IF NOT EXISTS metadata_cache (
            bucket     TEXT NOT NULL,
            key        TEXT NOT NULL,
            provider   TEXT NOT NULL DEFAULT '',
            payload    TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            PRIMARY KEY (bucket, key, provider)
        );
    """

    def __init__(self, db: Database):
        self.db = db
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        existing = self.db.query_one(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='metadata_cache'")
        if existing is None:
            self.db.execute(self.CREATE_SQL)
            return
        # Check whether provider column exists (migration from v1).
        cols = {row["name"] for row in self.db.query(
            "PRAGMA table_info(metadata_cache)")}
        if "provider" not in cols:
            # SQLite doesn't support ADD COLUMN IF NOT EXISTS directly; create new.
            self.db.execute("ALTER TABLE metadata_cache RENAME TO metadata_cache_old")
            self.db.execute(self.CREATE_SQL)
            self.db.execute("""
                INSERT INTO metadata_cache (bucket, key, provider, payload, created_at)
                SELECT bucket, key, '', payload, created_at FROM metadata_cache_old
            """)
            self.db.execute("DROP TABLE metadata_cache_old")

    # ── reads ─────────────────────────────────────────────────────────────────

    def get(self, bucket: str, key: str, ttl_s: int,
            provider: str | None = None) -> dict[str, Any] | None:
        """Return a cached entry. If *provider* is None, return the most-recent valid entry."""
        if provider is not None:
            row = self.db.query_one(
                "SELECT payload, created_at FROM metadata_cache "
                "WHERE bucket=? AND key=? AND provider=?",
                (bucket, key, provider))
            if row and time.time() - row["created_at"] <= ttl_s:
                try:
                    return json.loads(row["payload"])
                except json.JSONDecodeError:
                    return None
            return None
        # No provider specified — try any provider, newest first
        return self.get_any_provider(bucket, key, ttl_s)

    def get_any_provider(self, bucket: str, key: str, ttl_s: int) -> dict[str, Any] | None:
        """Return the most-recently-created valid entry regardless of provider."""
        rows = self.db.query(
            "SELECT payload, created_at, provider FROM metadata_cache "
            "WHERE bucket=? AND key=? ORDER BY created_at DESC",
            (bucket, key))
        for row in rows:
            if time.time() - row["created_at"] <= ttl_s:
                try:
                    return json.loads(row["payload"])
                except json.JSONDecodeError:
                    continue
        return None

    # ── writes ────────────────────────────────────────────────────────────────

    def set(self, bucket: str, key: str, payload: dict[str, Any],
            provider: str = "") -> None:
        if not payload:
            return
        self.db.execute(
            """INSERT OR REPLACE INTO metadata_cache
               (bucket, key, provider, payload, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (bucket, key, provider,
             json.dumps(payload, ensure_ascii=False), int(time.time())))

    # ── invalidation ──────────────────────────────────────────────────────────

    def clear(self, bucket: str | None = None, provider: str | None = None,
              key_prefix: str | None = None) -> int:
        """Remove cached entries. Returns count removed."""
        wheres: list[str] = []
        params: list[Any] = []
        if bucket:
            wheres.append("bucket=?"); params.append(bucket)
        if provider:
            wheres.append("provider=?"); params.append(provider)
        if key_prefix:
            wheres.append("key LIKE ?"); params.append(f"{key_prefix}%")
        where = (" WHERE " + " AND ".join(wheres)) if wheres else ""
        cur = self.db.query_one(
            f"SELECT COUNT(*) AS n FROM metadata_cache{where}", params)
        self.db.execute(f"DELETE FROM metadata_cache{where}", params)
        return int(cur["n"]) if cur else 0

    def clear_expired(self, ttl_s: int) -> int:
        """Remove entries older than ttl_s seconds. Returns count."""
        cutoff = int(time.time()) - ttl_s
        cur = self.db.query_one(
            "SELECT COUNT(*) AS n FROM metadata_cache WHERE created_at <?", (cutoff,))
        self.db.execute("DELETE FROM metadata_cache WHERE created_at <?", (cutoff,))
        return int(cur["n"]) if cur else 0

    def stats(self) -> dict[str, int]:
        row = self.db.query_one(
            "SELECT COUNT(*) AS total, "
            "COALESCE(SUM(CASE WHEN bucket='movie' THEN 1 ELSE 0 END),0) AS movies, "
            "COALESCE(SUM(CASE WHEN bucket='series' THEN 1 ELSE 0 END),0) AS series, "
            "COALESCE(SUM(CASE WHEN bucket='music' THEN 1 ELSE 0 END),0) AS music "
            "FROM metadata_cache")
        return {
            "total": int(row["total"]) if row else 0,
            "movies": int(row["movies"]) if row else 0,
            "series": int(row["series"]) if row else 0,
            "music": int(row["music"]) if row else 0,
        }
