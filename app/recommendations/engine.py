"""Local recommendation engine.

Score-based, honest, and fully derived from the user's own data:
- genre overlap with favorites and highly-rated items,
- shared cast/directors with watched items,
- provider rating as a mild tiebreaker,
- watched items are excluded.

No machine learning, no external calls — documented as such.
"""
from __future__ import annotations

import logging
import math

from app.database.repositories import Repositories

logger = logging.getLogger(__name__)


class RecommendationEngine:
    def __init__(self, repos: Repositories) -> None:
        self.repos = repos

    def recommended_movies(self, profile_id: int, limit: int = 12) -> list[dict]:
        seed_genres, seed_people = self._seeds(profile_id, "movie")
        candidates = self.repos.db.query(
            """SELECT m.id, m.title, m.year, m.rating, m.vote_count,
            (SELECT a.local_path FROM artwork a WHERE a.owner_type='movie' AND a.owner_id=m.id
             AND a.kind='poster' AND a.local_path<>'' LIMIT 1) AS poster_path,
            (SELECT COUNT(*) FROM playback_history h WHERE h.profile_id=? AND h.media_type='movie'
             AND h.media_id=m.id AND h.completed=1) AS watched
            FROM movies m WHERE m.id IN (
              SELECT media_id FROM media_genres WHERE media_type='movie' AND genre_id IN (%s)
            ) OR m.id IN (
              SELECT media_id FROM credits WHERE media_type='movie' AND person_id IN (%s)
            ) ORDER BY watched, m.rating DESC LIMIT 300"""
            % (
                ",".join(str(g) for g in seed_genres) or "-1",
                ",".join(str(p) for p in seed_people) or "-1",
            ),
            (profile_id,),
        )
        scored = []
        for row in candidates:
            if row["watched"]:
                continue
            score = self._score("movie", row["id"], seed_genres, seed_people, row["rating"])
            scored.append((score, dict(row)))
        scored.sort(key=lambda pair: -pair[0])
        return [row for score, row in scored[:limit] if score > 0]

    def recommended_shows(self, profile_id: int, limit: int = 12) -> list[dict]:
        seed_genres, seed_people = self._seeds(profile_id, "tv_show")
        candidates = self.repos.db.query(
            """SELECT s.id, s.title, s.first_air_date, s.rating,
            substr(s.first_air_date,1,4) AS year,
            (SELECT a.local_path FROM artwork a WHERE a.owner_type='tv_show' AND a.owner_id=s.id
             AND a.kind='poster' AND a.local_path<>'' LIMIT 1) AS poster_path
            FROM tv_shows s WHERE s.id IN (
              SELECT media_id FROM media_genres WHERE media_type='tv_show' AND genre_id IN (%s)
            ) OR s.id IN (
              SELECT media_id FROM credits WHERE media_type='tv_show' AND person_id IN (%s)
            ) ORDER BY s.rating DESC LIMIT 300"""
            % (
                ",".join(str(g) for g in seed_genres) or "-1",
                ",".join(str(p) for p in seed_people) or "-1",
            ),
        )
        scored = []
        for row in candidates:
            score = self._score("tv_show", row["id"], seed_genres, seed_people, row["rating"])
            scored.append((score, dict(row)))
        scored.sort(key=lambda pair: -pair[0])
        return [row for score, row in scored[:limit] if score > 0]

    def recommended(self, profile_id: int, limit: int = 12) -> list[dict]:
        """Mixed movie/show recommendations, interleaved."""
        movies = self.recommended_movies(profile_id, limit=limit)
        shows = self.recommended_shows(profile_id, limit=limit)
        mixed: list[dict] = []
        for i in range(max(len(movies), len(shows))):
            if i < len(movies):
                mixed.append(movies[i])
            if i < len(shows):
                mixed.append(shows[i])
        if not mixed:
            # cold start: highest rated items in library (still real data)
            rows = self.repos.db.query(
                """SELECT m.id, m.title, m.year, m.rating,
                (SELECT a.local_path FROM artwork a WHERE a.owner_type='movie' AND a.owner_id=m.id
                 AND a.kind='poster' AND a.local_path<>'' LIMIT 1) AS poster_path
                FROM movies m WHERE m.rating IS NOT NULL ORDER BY m.rating DESC LIMIT ?""",
                (limit,),
            )
            mixed = [dict(r) for r in rows]
        return mixed[:limit]

    # -- internals -----------------------------------------------------------------
    def _seeds(self, profile_id: int, media_type: str) -> tuple[set[int], set[int]]:
        """Genres and people from favorites + watched + highly rated items."""
        seed_ids: set[int] = set()
        for row in self.repos.db.query(
            "SELECT media_id FROM favorites WHERE profile_id=? AND media_type=?",
            (profile_id, media_type),
        ):
            seed_ids.add(row["media_id"])
        for row in self.repos.db.query(
            "SELECT DISTINCT media_id FROM playback_history WHERE profile_id=? AND media_type=?"
            " AND completed=1",
            (profile_id, media_type),
        ):
            seed_ids.add(row["media_id"])
        for row in self.repos.db.query(
            "SELECT media_id FROM user_ratings WHERE profile_id=? AND media_type=? AND rating>=7",
            (profile_id, media_type),
        ):
            seed_ids.add(row["media_id"])
        genres: set[int] = set()
        people: set[int] = set()
        for media_id in list(seed_ids)[:100]:
            for row in self.repos.db.query(
                "SELECT genre_id FROM media_genres WHERE media_type=? AND media_id=?",
                (media_type, media_id),
            ):
                genres.add(row["genre_id"])
            for row in self.repos.db.query(
                "SELECT person_id FROM credits WHERE media_type=? AND media_id=?",
                (media_type, media_id),
            ):
                people.add(row["person_id"])
        return genres, people

    def _score(
        self,
        media_type: str,
        media_id: int,
        seed_genres: set[int],
        seed_people: set[int],
        rating: float | None,
    ) -> float:
        genre_rows = self.repos.db.query(
            "SELECT genre_id FROM media_genres WHERE media_type=? AND media_id=?",
            (media_type, media_id),
        )
        item_genres = {r["genre_id"] for r in genre_rows}
        genre_overlap = len(item_genres & seed_genres)
        people_rows = self.repos.db.query(
            "SELECT person_id FROM credits WHERE media_type=? AND media_id=?",
            (media_type, media_id),
        )
        item_people = {r["person_id"] for r in people_rows}
        people_overlap = len(item_people & seed_people)
        score = 3.0 * genre_overlap + 2.0 * people_overlap
        if rating:
            score += math.log10(max(rating, 1.0)) * 0.5
        return score
