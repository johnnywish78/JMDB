"""Statistics — pure SQL aggregation + a little python shaping."""
from __future__ import annotations

import json
import time
from datetime import date, timedelta
from typing import Any

from app.database.connection import Database

DAY_MS = 86_400_000


class StatisticsService:
    def __init__(self, db: Database):
        self.db = db

    def overview(self) -> dict[str, Any]:
        movies_watched = self._one("SELECT COUNT(*) n FROM movies_watched")
        episodes_watched = self._one("SELECT COUNT(*) n FROM episodes_watched")
        minutes = self._one(
            """SELECT COALESCE(SUM(m.runtime_min),0) n FROM movies_watched mw
               JOIN media m ON m.id=mw.media_id""")
        minutes += self._one(
            """SELECT COALESCE(SUM(e.runtime_min),0) n FROM episodes_watched ew
               JOIN episodes e ON e.id=ew.episode_id""")
        minutes += self._one(
            "SELECT COALESCE(SUM(position_s/60),0) n FROM playback_progress WHERE position_s>60")
        favorites = self._one("SELECT COUNT(*) n FROM favorites")
        watchlist = self._one("SELECT COUNT(*) n FROM watchlist")
        library = {k: self._one("SELECT COUNT(*) n FROM media WHERE kind=?", (k,))
                   for k in ("movie", "show", "music")}
        rated = self.db.query_one("SELECT COUNT(*) n, AVG(value) a FROM ratings") or {}
        return {
            "movies_watched": movies_watched,
            "episodes_watched": episodes_watched,
            "minutes": minutes,
            "hours": round(minutes / 60, 1),
            "favorites": favorites,
            "watchlist": watchlist,
            "library": library,
            "rated_count": int(rated.get("n") or 0),
            "avg_rating": round(float(rated.get("a") or 0), 1),
            "top_genres": self.genre_distribution(limit=7),
            "activity": self.activity(days=14),
            "streak": self._streak(),
        }

    def genre_distribution(self, limit: int = 7) -> list[tuple[str, float]]:
        counts: dict[str, float] = {}
        for row in self.db.query(
                """SELECT m.genres, 1.0 w FROM movies_watched mw JOIN media m ON m.id=mw.media_id
                   UNION ALL
                   SELECT m.genres, 0.5 w FROM episodes_watched ew
                   JOIN episodes e ON e.id=ew.episode_id JOIN media m ON m.id=e.show_id"""):
            for g in json.loads(row["genres"] or "[]"):
                counts[g] = counts.get(g, 0) + row["w"]
        return sorted(counts.items(), key=lambda p: p[1], reverse=True)[:limit]

    def activity(self, days: int = 14) -> list[dict[str, Any]]:
        today = date.today()
        start = today - timedelta(days=days - 1)
        start_ms = int(time.mktime(start.timetuple()) * 1000)
        rows = self.db.query(
            "SELECT finished_at FROM watch_history WHERE finished_at>=?", (start_ms,))
        per_day: dict[str, int] = {}
        for r in rows:
            d = date.fromtimestamp(r["finished_at"] / 1000).isoformat()
            per_day[d] = per_day.get(d, 0) + 1
        return [{"date": (start + timedelta(days=i)).isoformat(),
                 "count": per_day.get((start + timedelta(days=i)).isoformat(), 0)}
                for i in range(days)]

    def _streak(self) -> int:
        activity = self.activity(days=60)
        streak = 0
        for day in reversed(activity):
            if day["count"] > 0:
                streak += 1
            elif streak == 0 and day["date"] == activity[-1]["date"]:
                continue  # today not over yet
            else:
                break
        return streak

    def _one(self, sql: str, params: tuple = ()) -> int | float:
        row = self.db.query_one(sql, params)
        return row["n"] if row else 0
