"""Browser history, bookmarks, downloads repositories."""
from __future__ import annotations

from app.domain.models import Bookmark, BrowserHistoryEntry, DownloadRecord
from app.database.repositories import BaseRepository, row_to_dataclass, rows_to_dataclasses


class BrowserRepository(BaseRepository):
    # -- history ------------------------------------------------------------
    def add_history(self, url: str, title: str = "") -> None:
        if url and not url.startswith(("data:", "about:")):
            self.db.execute(
                "INSERT INTO browser_history (url, title) VALUES (?,?)", (url, title)
            )

    def history(self, limit: int = 200, query: str = "") -> list[BrowserHistoryEntry]:
        where, params = ["1=1"], []
        if query:
            where.append("(url LIKE ? OR title LIKE ?)")
            params.extend([f"%{query}%", f"%{query}%"])
        rows = self.db.query(
            "SELECT * FROM browser_history WHERE " + " AND ".join(where) +
            " ORDER BY visited_at DESC LIMIT ?",
            (*params, limit),
        )
        return rows_to_dataclasses(rows, BrowserHistoryEntry)

    def clear_history(self) -> None:
        self.db.execute("DELETE FROM browser_history")

    def top_sites(self, limit: int = 10) -> list[dict]:
        rows = self.db.query(
            "SELECT url, title, COUNT(*) n FROM browser_history"
            " WHERE url LIKE 'http%' GROUP BY url ORDER BY n DESC LIMIT ?",
            (limit,),
        )
        return [dict(r) for r in rows]

    # -- bookmarks --------------------------------------------------------------
    def add_bookmark(self, url: str, title: str = "", folder: str = "") -> Bookmark:
        cur = self.db.execute(
            "INSERT INTO bookmarks (url, title, folder) VALUES (?,?,?)"
            " ON CONFLICT(url) DO UPDATE SET title=excluded.title, folder=excluded.folder",
            (url, title or url, folder),
        )
        row = self.db.query_one("SELECT * FROM bookmarks WHERE url=?", (url,))
        return row_to_dataclass(row, Bookmark)

    def remove_bookmark(self, url: str) -> None:
        self.db.execute("DELETE FROM bookmarks WHERE url=?", (url,))

    def bookmarks(self, folder: str | None = None) -> list[Bookmark]:
        if folder is None:
            return rows_to_dataclasses(
                self.db.query("SELECT * FROM bookmarks ORDER BY folder, title"), Bookmark
            )
        return rows_to_dataclasses(
            self.db.query("SELECT * FROM bookmarks WHERE folder=? ORDER BY title", (folder,)),
            Bookmark,
        )

    def is_bookmarked(self, url: str) -> bool:
        return bool(self.db.scalar("SELECT 1 FROM bookmarks WHERE url=?", (url,)))

    # -- downloads -----------------------------------------------------------------
    def add_download(self, url: str, path: str, mime_type: str = "", bytes_total: int = 0) -> int:
        cur = self.db.execute(
            "INSERT INTO downloads (url, path, mime_type, bytes_total)"
            " VALUES (?,?,?,?)",
            (url, path, mime_type, bytes_total),
        )
        return int(cur.lastrowid)

    def update_download(
        self,
        download_id: int,
        state: str | None = None,
        bytes_received: int | None = None,
        bytes_total: int | None = None,
    ) -> None:
        sets, params = [], []
        if state is not None:
            sets.append("state=?")
            params.append(state)
            if state in ("completed", "cancelled", "failed"):
                sets.append("finished_at=datetime('now')")
        if bytes_received is not None:
            sets.append("bytes_received=?")
            params.append(bytes_received)
        if bytes_total is not None:
            sets.append("bytes_total=?")
            params.append(bytes_total)
        if sets:
            params.append(download_id)
            self.db.execute(f"UPDATE downloads SET {', '.join(sets)} WHERE id=?", params)

    def downloads(self, limit: int = 100) -> list[DownloadRecord]:
        return rows_to_dataclasses(
            self.db.query("SELECT * FROM downloads ORDER BY started_at DESC LIMIT ?", (limit,)),
            DownloadRecord,
        )
