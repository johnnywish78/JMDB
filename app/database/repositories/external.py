"""External IDs and artwork repository."""
from __future__ import annotations

from app.domain.models import Artwork, ExternalId
from app.database.repositories import BaseRepository, row_to_dataclass, rows_to_dataclasses


class ExternalIdsRepository(BaseRepository):
    def set(self, media_type: str, media_id: int, provider: str, value: str | None) -> None:
        if not value:
            return
        self.db.execute(
            "INSERT INTO external_ids (media_type, media_id, provider, value) VALUES (?,?,?,?)"
            " ON CONFLICT(media_type, media_id, provider) DO UPDATE SET value=excluded.value",
            (media_type, media_id, provider, str(value)),
        )

    def get(self, media_type: str, media_id: int, provider: str) -> str | None:
        return self.db.scalar(
            "SELECT value FROM external_ids WHERE media_type=? AND media_id=? AND provider=?",
            (media_type, media_id, provider),
        )

    def all_for(self, media_type: str, media_id: int) -> dict[str, str]:
        rows = self.db.query(
            "SELECT provider, value FROM external_ids WHERE media_type=? AND media_id=?",
            (media_type, media_id),
        )
        return {r["provider"]: r["value"] for r in rows}

    def find_by_external_id(self, provider: str, value: str) -> list[tuple[str, int]]:
        rows = self.db.query(
            "SELECT media_type, media_id FROM external_ids WHERE provider=? AND value=?",
            (provider, value),
        )
        return [(r["media_type"], r["media_id"]) for r in rows]


class ArtworkRepository(BaseRepository):
    def upsert(
        self,
        owner_type: str,
        owner_id: int,
        kind: str,
        source_url: str = "",
        local_path: str = "",
        width: int = 0,
        height: int = 0,
    ) -> Artwork:
        row = self.db.query_one(
            "SELECT * FROM artwork WHERE owner_type=? AND owner_id=? AND kind=? AND source_url=?",
            (owner_type, owner_id, kind, source_url),
        )
        if row is None:
            cur = self.db.execute(
                "INSERT INTO artwork (owner_type, owner_id, kind, source_url, local_path,"
                " width, height, downloaded_at, last_accessed)"
                " VALUES (?,?,?,?,?,?,?,datetime('now'),datetime('now'))",
                (owner_type, owner_id, kind, source_url, local_path, width, height),
            )
            row = self.db.query_one("SELECT * FROM artwork WHERE id=?", (cur.lastrowid,))
        elif local_path and local_path != row["local_path"]:
            self.db.execute(
                "UPDATE artwork SET local_path=?, width=?, height=?, downloaded_at=datetime('now')"
                " WHERE id=?",
                (local_path, width, height, row["id"]),
            )
            row = self.db.query_one("SELECT * FROM artwork WHERE id=?", (row["id"],))
        return row_to_dataclass(row, Artwork)

    def set_local(self, artwork_id: int, local_path: str, width: int, height: int) -> None:
        self.db.execute(
            "UPDATE artwork SET local_path=?, width=?, height=?, downloaded_at=datetime('now')"
            " WHERE id=?",
            (local_path, width, height, artwork_id),
        )

    def get(self, owner_type: str, owner_id: int, kind: str) -> Artwork | None:
        row = self.db.query_one(
            "SELECT * FROM artwork WHERE owner_type=? AND owner_id=? AND kind=?"
            " AND local_path<>'' ORDER BY id LIMIT 1",
            (owner_type, owner_id, kind),
        )
        return row_to_dataclass(row, Artwork) if row else None

    def all_for(self, owner_type: str, owner_id: int) -> list[Artwork]:
        rows = self.db.query(
            "SELECT * FROM artwork WHERE owner_type=? AND owner_id=? ORDER BY id",
            (owner_type, owner_id),
        )
        return rows_to_dataclasses(rows, Artwork)

    def local_path(self, owner_type: str, owner_id: int, kind: str) -> str:
        row = self.db.query_one(
            "SELECT local_path FROM artwork WHERE owner_type=? AND owner_id=? AND kind=?"
            " AND local_path<>'' ORDER BY id LIMIT 1",
            (owner_type, owner_id, kind),
        )
        return row["local_path"] if row else ""

    def touch(self, artwork_id: int) -> None:
        self.db.execute(
            "UPDATE artwork SET last_accessed=datetime('now') WHERE id=?", (artwork_id,)
        )

    def pending_urls(self, limit: int = 200) -> list[Artwork]:
        rows = self.db.query(
            "SELECT * FROM artwork WHERE source_url<>'' AND local_path='' ORDER BY id LIMIT ?",
            (limit,),
        )
        return rows_to_dataclasses(rows, Artwork)

    def cached_count(self) -> int:
        return int(self.db.scalar("SELECT COUNT(*) FROM artwork WHERE local_path<>''") or 0)

    def purge_missing_files(self) -> int:
        import os

        rows = self.db.query("SELECT id, local_path FROM artwork WHERE local_path<>''")
        removed = 0
        for r in rows:
            if not os.path.exists(r["local_path"]):
                self.db.execute("UPDATE artwork SET local_path='' WHERE id=?", (r["id"],))
                removed += 1
        return removed
