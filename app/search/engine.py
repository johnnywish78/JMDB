"""Search: FTS5 MATCH preferred, graceful LIKE fallback (missing FTS5, weird input)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.database.connection import Database
from app.database.repositories import MediaRepository

_TOKEN = re.compile(r"[\wآ-ی]+", re.UNICODE)


@dataclass
class SearchFilters:
    kind: str | None = None          # 'movie' | 'show' | None
    genre: str | None = None
    min_rating: float = 0.0
    years: tuple[int, int] | None = None
    extra: dict = field(default_factory=dict)


class SearchEngine:
    def __init__(self, db: Database):
        self.db = db
        self._fts_ok: bool | None = None

    def _fts_available(self) -> bool:
        if self._fts_ok is None:
            try:
                self.db.query("SELECT rowid FROM media_fts LIMIT 1")
                self._fts_ok = True
            except Exception:
                self._fts_ok = False
        return self._fts_ok

    def search(self, text: str, filters: SearchFilters | None = None,
               limit: int = 60) -> list[dict[str, Any]]:
        filters = filters or SearchFilters()
        text = (text or "").strip()
        ids: list[int] | None = None
        if text:
            tokens = _TOKEN.findall(text)
            ids = self._match_ids(tokens, limit)
            if ids is not None and not ids:
                return []
        sql, params = self._build_where(filters, ids)
        sql += " ORDER BY rating DESC, title LIMIT ?"
        params.append(limit)
        return [MediaRepository._expand(r) for r in self.db.query(sql, params)]

    def _match_ids(self, tokens: list[str], limit: int) -> list[int] | None:
        if not tokens:
            return None
        if self._fts_available():
            try:
                expr = " OR ".join(f'"{t}"' for t in tokens)
                rows = self.db.query(
                    "SELECT rowid AS id FROM media_fts WHERE media_fts MATCH ? LIMIT ?",
                    (expr, limit))
                return [int(r["id"]) for r in rows]
            except Exception:
                pass  # fall through to LIKE
        likes = " AND ".join("LOWER(title) LIKE ?" for _ in tokens)
        rows = self.db.query(
            f"SELECT id FROM media WHERE {likes}",
            tuple(f"%{t.lower()}%" for t in tokens))
        return [int(r["id"]) for r in rows]

    @staticmethod
    def _build_where(filters: SearchFilters, ids: list[int] | None):
        sql = "SELECT * FROM media WHERE 1=1"
        params: list[Any] = []
        if ids is not None:
            sql += f" AND id IN ({','.join('?' for _ in ids) or 'NULL'})"
            params.extend(ids)
        if filters.kind:
            sql += " AND kind=?"; params.append(filters.kind)
        if filters.genre:
            sql += " AND genres LIKE ?"; params.append(f'%"{filters.genre}"%')
        if filters.min_rating > 0:
            sql += " AND rating>=?"; params.append(filters.min_rating)
        if filters.years:
            sql += " AND year BETWEEN ? AND ?"; params.extend(filters.years)
        return sql, params
