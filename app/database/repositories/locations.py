"""Library locations repository."""
from __future__ import annotations

from app.domain.models import LibraryLocation
from app.database.repositories import BaseRepository, row_to_dataclass, rows_to_dataclasses


class LibraryLocationsRepository(BaseRepository):
    def add(self, path: str, label: str = "") -> LibraryLocation:
        cur = self.db.execute(
            "INSERT OR IGNORE INTO library_locations (path, label) VALUES (?, ?)",
            (path, label),
        )
        return self.get_by_path(path) or LibraryLocation(id=cur.lastrowid, path=path)

    def get(self, location_id: int) -> LibraryLocation | None:
        row = self.db.query_one("SELECT * FROM library_locations WHERE id=?", (location_id,))
        return row_to_dataclass(row, LibraryLocation) if row else None

    def get_by_path(self, path: str) -> LibraryLocation | None:
        row = self.db.query_one("SELECT * FROM library_locations WHERE path=?", (path,))
        return row_to_dataclass(row, LibraryLocation) if row else None

    def list(self) -> list[LibraryLocation]:
        return rows_to_dataclasses(
            self.db.query("SELECT * FROM library_locations ORDER BY path"),
            LibraryLocation,
        )

    def remove(self, location_id: int) -> None:
        self.db.execute("DELETE FROM library_locations WHERE id=?", (location_id,))

    def update_scan_result(
        self, location_id: int, status: str, error: str = ""
    ) -> None:
        self.db.execute(
            "UPDATE library_locations SET last_scan_at=datetime('now'),"
            " last_scan_status=?, last_scan_error=? WHERE id=?",
            (status, error, location_id),
        )

    def set_enabled(self, location_id: int, enabled: bool) -> None:
        self.db.execute(
            "UPDATE library_locations SET enabled=? WHERE id=?",
            (1 if enabled else 0, location_id),
        )

    def file_counts(self) -> dict[int, int]:
        rows = self.db.query(
            "SELECT library_location_id, COUNT(*) AS n FROM media_files"
            " WHERE is_missing=0 GROUP BY library_location_id"
        )
        return {r["library_location_id"]: r["n"] for r in rows}
