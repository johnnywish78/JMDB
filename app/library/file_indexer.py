"""File indexer: bulk-sync filesystem discoveries into media_files."""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass

from app.database.connection import Database
from app.database.repositories import Repositories

logger = logging.getLogger(__name__)

CHUNK_SIZE = 64 * 1024


@dataclass
class IndexResult:
    files_added: int = 0
    files_updated: int = 0
    files_missing: int = 0
    files_moved: int = 0


class FileIndexer:
    def __init__(self, db: Database, repos: Repositories) -> None:
        self.db = db
        self.repos = repos

    def sync(self, location_id: int, entries: list[dict]) -> dict:
        """Full file-sync for one scan pass.

        Order matters: rows for vanished paths are marked missing *before*
        inserting new rows, so a file that reappears at a new path with the
        same name and size is recognized as a move and its row is adopted
        (history/links are preserved).
        """
        seen = {entry["path"] for entry in entries}
        missing_count = self.mark_missing(location_id, seen)
        result = self.bulk_upsert(location_id, entries)
        result["missing"] = missing_count
        return result

    def bulk_upsert(self, location_id: int, entries: list[dict]) -> dict[int, int]:
        """Upsert many found files. ``entries`` have keys from FoundFile + kind.

        Returns mapping file_id -> size (for matching stage).
        """
        existing = {
            r["path"]: r
            for r in self.db.query(
                "SELECT id, path, size_bytes, mtime_ns, is_missing FROM media_files"
                " WHERE library_location_id=?",
                (location_id,),
            )
        }
        added = 0
        updated = 0
        id_by_path: dict[int, int] = {}
        with self.db.transaction() as conn:
            for entry in entries:
                old = existing.get(entry["path"])
                if old is None:
                    # moved-file detection: same filename+size previously missing
                    moved = self._find_moved_row(conn, entry)
                    if moved is not None:
                        conn.execute(
                            "UPDATE media_files SET path=?, directory=?, size_bytes=?,"
                            " mtime_ns=?, is_missing=0, last_seen_at=datetime('now')"
                            " WHERE id=?",
                            (
                                entry["path"], entry["directory"], entry["size_bytes"],
                                entry["mtime_ns"], moved,
                            ),
                        )
                        id_by_path[entry["path"]] = moved
                        continue
                    cur = conn.execute(
                        "INSERT INTO media_files (library_location_id, path, filename,"
                        " directory, size_bytes, mtime_ns, kind, container)"
                        " VALUES (?,?,?,?,?,?,?,?)",
                        (
                            location_id, entry["path"], entry["filename"],
                            entry["directory"], entry["size_bytes"], entry["mtime_ns"],
                            entry["kind"], entry["extension"],
                        ),
                    )
                    id_by_path[entry["path"]] = int(cur.lastrowid)
                    added += 1
                else:
                    id_by_path[entry["path"]] = int(old["id"])
                    if old["size_bytes"] != entry["size_bytes"] or old["mtime_ns"] != entry["mtime_ns"] or old["is_missing"]:
                        conn.execute(
                            "UPDATE media_files SET size_bytes=?, mtime_ns=?, is_missing=0,"
                            " last_seen_at=datetime('now') WHERE id=?",
                            (entry["size_bytes"], entry["mtime_ns"], old["id"]),
                        )
                        updated += 1
        return {"added": added, "updated": updated, "ids": id_by_path}

    def _find_moved_row(self, conn, entry: dict) -> int | None:
        row = conn.execute(
            "SELECT id FROM media_files WHERE filename=? AND size_bytes=? AND is_missing=1"
            " LIMIT 1",
            (entry["filename"], entry["size_bytes"]),
        ).fetchone()
        return int(row["id"]) if row else None

    def mark_missing(self, location_id: int, seen_paths: set[str]) -> int:
        """Files previously indexed under this location but not seen now."""
        with self.db.transaction() as conn:
            conn.execute(
                "CREATE TEMP TABLE IF NOT EXISTS seen_paths (path TEXT PRIMARY KEY)"
            )
            conn.execute("DELETE FROM seen_paths")
            for i in range(0, len(seen_paths), 500):
                chunk = list(seen_paths)[i : i + 500]
                conn.executemany(
                    "INSERT OR IGNORE INTO seen_paths (path) VALUES (?)",
                    [(p,) for p in chunk],
                )
            cur = conn.execute(
                "UPDATE media_files SET is_missing=1 WHERE library_location_id=?"
                " AND path NOT IN (SELECT path FROM seen_paths)",
                (location_id,),
            )
            conn.execute("DROP TABLE IF EXISTS seen_paths")
            return cur.rowcount

    @staticmethod
    def partial_checksum(path: str, size: int) -> str | None:
        """Cheap checksum (first+last 64KB) for duplicate detection."""
        if size <= 0:
            return None
        try:
            digest = hashlib.sha1()
            with open(path, "rb") as handle:
                digest.update(handle.read(CHUNK_SIZE))
                if size > CHUNK_SIZE * 2:
                    handle.seek(-CHUNK_SIZE, 2)
                    digest.update(handle.read(CHUNK_SIZE))
            return digest.hexdigest()
        except OSError:
            return None

    def checksum_videos(self, location_id: int, min_size_bytes: int) -> int:
        """Compute checksums for large videos that lack one."""
        rows = self.db.query(
            "SELECT id, path, size_bytes FROM media_files"
            " WHERE library_location_id=? AND kind='video' AND checksum=''"
            " AND size_bytes>=? AND is_missing=0",
            (location_id, min_size_bytes),
        )
        count = 0
        for row in rows:
            checksum = self.partial_checksum(row["path"], row["size_bytes"])
            if checksum:
                self.repos.files.set_checksum(row["id"], checksum)
                count += 1
        return count
