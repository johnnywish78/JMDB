"""Media files repository — the single source of truth for files on disk."""
from __future__ import annotations

import json
from typing import Iterable, Optional

from app.domain.models import MediaFile
from app.database.repositories import BaseRepository, row_to_dataclass, rows_to_dataclasses


class MediaFilesRepository(BaseRepository):
    # -- upsert ----------------------------------------------------------
    def upsert(
        self,
        library_location_id: int,
        path: str,
        filename: str,
        directory: str,
        kind: str,
        container: str,
        size_bytes: int,
        mtime_ns: int,
    ) -> tuple[int, bool]:
        """Insert or refresh a file. Returns (id, created)."""
        row = self.db.query_one("SELECT id, size_bytes, mtime_ns FROM media_files WHERE path=?", (path,))
        if row is None:
            cur = self.db.execute(
                "INSERT INTO media_files (library_location_id, path, filename, directory,"
                " kind, container, size_bytes, mtime_ns)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (library_location_id, path, filename, directory, kind, container, size_bytes, mtime_ns),
            )
            return int(cur.lastrowid), True
        if row["size_bytes"] != size_bytes or row["mtime_ns"] != mtime_ns:
            self.db.execute(
                "UPDATE media_files SET size_bytes=?, mtime_ns=?, is_missing=0,"
                " last_seen_at=datetime('now') WHERE id=?",
                (size_bytes, mtime_ns, row["id"]),
            )
        else:
            self.db.execute(
                "UPDATE media_files SET is_missing=0, last_seen_at=datetime('now') WHERE id=?",
                (row["id"],),
            )
        return int(row["id"]), False

    def get(self, file_id: int) -> MediaFile | None:
        row = self.db.query_one("SELECT * FROM media_files WHERE id=?", (file_id,))
        return self._hydrate(row)

    def get_by_path(self, path: str) -> MediaFile | None:
        row = self.db.query_one("SELECT * FROM media_files WHERE path=?", (path,))
        return self._hydrate(row)

    def _hydrate(self, row) -> MediaFile | None:
        if row is None:
            return None
        mf = row_to_dataclass(row, MediaFile)
        if mf.probe is None and row["probe_json"]:
            try:
                mf.probe = json.loads(row["probe_json"])
            except (ValueError, TypeError):
                mf.probe = None
        return mf

    def set_probe(self, file_id: int, probe: dict | None) -> None:
        self.db.execute(
            "UPDATE media_files SET probe_json=? WHERE id=?",
            (json.dumps(probe) if probe else None, file_id),
        )

    def set_checksum(self, file_id: int, checksum: str) -> None:
        self.db.execute("UPDATE media_files SET checksum=? WHERE id=?", (checksum, file_id))

    # -- missing / stale detection ----------------------------------------
    def mark_missing(self, file_id: int) -> None:
        self.db.execute("UPDATE media_files SET is_missing=1 WHERE id=?", (file_id,))

    def purge_missing(self, older_than_seen: bool = False) -> int:
        """Delete missing files and their links. Returns deleted count."""
        cur = self.db.execute("DELETE FROM media_files WHERE is_missing=1")
        return cur.rowcount

    def recheck_missing(self, location_id: int | None = None) -> list[str]:
        """Return paths of files marked missing that exist on disk again."""
        if location_id is None:
            rows = self.db.query("SELECT id, path FROM media_files WHERE is_missing=1")
        else:
            rows = self.db.query(
                "SELECT id, path FROM media_files WHERE is_missing=1 AND library_location_id=?",
                (location_id,),
            )
        import os

        back = []
        for r in rows:
            if os.path.exists(r["path"]):
                self.db.execute(
                    "UPDATE media_files SET is_missing=0, last_seen_at=datetime('now') WHERE id=?",
                    (r["id"],),
                )
                back.append(r["path"])
        return back

    # -- links ---------------------------------------------------------------
    def link(self, media_item_type: str, media_item_id: int, media_file_id: int, primary: bool = False) -> None:
        self.db.execute(
            "INSERT INTO media_file_links (media_item_type, media_item_id, media_file_id, is_primary)"
            " VALUES (?,?,?,?)"
            " ON CONFLICT(media_item_type, media_item_id, media_file_id)"
            " DO UPDATE SET is_primary=excluded.is_primary",
            (media_item_type, media_item_id, media_file_id, 1 if primary else 0),
        )
        if primary:
            self.db.execute(
                "UPDATE media_file_links SET is_primary=0 WHERE media_item_type=?"
                " AND media_item_id=? AND media_file_id<>?",
                (media_item_type, media_item_id, media_file_id),
            )

    def unlink_file(self, media_file_id: int) -> None:
        self.db.execute("DELETE FROM media_file_links WHERE media_file_id=?", (media_file_id,))

    def files_for(self, media_item_type: str, media_item_id: int) -> list[MediaFile]:
        rows = self.db.query(
            "SELECT mf.* FROM media_files mf"
            " JOIN media_file_links l ON l.media_file_id = mf.id"
            " WHERE l.media_item_type=? AND l.media_item_id=?"
            " ORDER BY l.is_primary DESC, mf.size_bytes DESC",
            (media_item_type, media_item_id),
        )
        return [self._hydrate(r) for r in rows]

    def primary_file(self, media_item_type: str, media_item_id: int) -> MediaFile | None:
        rows = self.files_for(media_item_type, media_item_id)
        return rows[0] if rows else None

    def owner_of_file(self, media_file_id: int) -> tuple[str, int] | None:
        row = self.db.query_one(
            "SELECT media_item_type, media_item_id FROM media_file_links WHERE media_file_id=?",
            (media_file_id,),
        )
        return (row["media_item_type"], row["media_item_id"]) if row else None

    # -- bulk queries ----------------------------------------------------------
    def count(self, kind: str | None = None, missing: bool = False) -> int:
        sql = "SELECT COUNT(*) FROM media_files WHERE is_missing=?"
        params: list = [1 if missing else 0]
        if kind:
            sql += " AND kind=?"
            params.append(kind)
        return int(self.db.scalar(sql, params) or 0)

    def videos_without_owner(self, limit: int = 100) -> list[MediaFile]:
        rows = self.db.query(
            "SELECT mf.* FROM media_files mf"
            " LEFT JOIN media_file_links l ON l.media_file_id = mf.id"
            " WHERE mf.kind='video' AND mf.is_missing=0 AND l.id IS NULL"
            " ORDER BY mf.path LIMIT ?",
            (limit,),
        )
        return [self._hydrate(r) for r in rows]

    def subtitles_near(self, directory: str, stem: str) -> list[MediaFile]:
        """Subtitle files in a directory matching a video stem (or 'all' subs)."""
        rows = self.db.query(
            "SELECT * FROM media_files WHERE kind='subtitle' AND directory=?"
            " AND (filename LIKE ? OR filename NOT LIKE '%.%')"
            " ORDER BY filename",
            (directory, stem + ".%"),
        )
        return [self._hydrate(r) for r in rows]

    def duplicate_groups(self, min_size_bytes: int = 0) -> list[list[MediaFile]]:
        """Groups of files sharing a checksum (size-filtered)."""
        rows = self.db.query(
            "SELECT * FROM media_files WHERE checksum<>'' AND is_missing=0"
            " AND size_bytes>=? ORDER BY checksum, path",
            (min_size_bytes,),
        )
        groups: list[list[MediaFile]] = []
        current_key, current = None, []
        for row in rows:
            if row["checksum"] != current_key:
                if len(current) > 1:
                    groups.append(current)
                current_key, current = row["checksum"], []
            current.append(self._hydrate(row))
        if len(current) > 1:
            groups.append(current)
        return groups
