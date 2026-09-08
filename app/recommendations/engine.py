"""Taste-profile recommendations: genre affinity from favorites/ratings/watch activity."""
from __future__ import annotations

import json
from typing import Any

from app.database.connection import Database
from app.database.repositories import EpisodeRepository, MediaRepository


class RecommendationEngine:
    def __init__(self, db: Database, episode_repo: EpisodeRepository):
        self.db = db
        self.episode_repo = episode_repo

    def affinity(self) -> dict[str, float]:
        aff: dict[str, float] = {}

        def bump(genres: list[str], weight: float) -> None:
            for g in genres:
                aff[g] = aff.get(g, 0.0) + weight

        media = {m["id"]: m for m in self.db.query("SELECT * FROM media")}
        for row in self.db.query("SELECT media_id FROM favorites"):
            m = media.get(row["media_id"])
            if m:
                bump(json.loads(m["genres"] or "[]"), 3.0)
        for row in self.db.query("SELECT media_id, watched_at FROM movies_watched"):
            m = media.get(row["media_id"])
            if m:
                bump(json.loads(m["genres"] or "[]"), 2.0)
        for row in self.db.query("SELECT media_id, value FROM ratings WHERE value>=8"):
            m = media.get(row["media_id"])
            if m:
                bump(json.loads(m["genres"] or "[]"), 2.0)
        # shows touched via any watched episode
        show_ids = {r["show_id"] for r in self.db.query(
            "SELECT DISTINCT show_id FROM episodes WHERE id IN (SELECT episode_id FROM episodes_watched)")}
        for sid in show_ids:
            m = media.get(sid)
            if m:
                bump(json.loads(m["genres"] or "[]"), 1.0)
        return aff

    def for_you(self, limit: int = 18) -> list[dict[str, Any]]:
        import json

        aff = self.affinity()
        tuned = bool(aff)
        exclude = {r["media_id"] for r in self.db.query("SELECT media_id FROM movies_watched")}
        exclude |= {r["media_id"] for r in self.db.query("SELECT media_id FROM favorites")}
        exclude |= {r["show_id"] for r in self.db.query(
            """SELECT show_id FROM episodes GROUP BY show_id
               HAVING COUNT(*) = SUM(CASE WHEN id IN (SELECT episode_id FROM episodes_watched) THEN 1 ELSE 0 END)""")}
        watchlist = {r["media_id"] for r in self.db.query("SELECT media_id FROM watchlist")}

        scored: list[tuple[float, dict[str, Any]]] = []
        for m in self.db.query("SELECT * FROM media"):
            if m["id"] in exclude:
                continue
            genres = json.loads(m["genres"] or "[]")
            base = sum(aff.get(g, 0.0) for g in genres) * 2 if tuned else 0
            score = base + float(m["rating"] or 0) + (1.5 if m["id"] in watchlist else 0.0)
            scored.append((score, MediaRepository._expand(m)))
        scored.sort(key=lambda p: p[0], reverse=True)
        return [m for _, m in scored[:limit]]
