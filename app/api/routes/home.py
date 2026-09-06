"""Home dashboard bundle: hero candidates + all rows in one request."""
from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter()

HERO_SQL = """
SELECT m.id, m.title, m.overview, m.year, m.rating,
       'movie' AS media_type,
       (SELECT a.local_path FROM artwork a WHERE a.owner_type='movie' AND a.owner_id=m.id
        AND a.kind='backdrop' AND a.local_path<>'' LIMIT 1) AS backdrop_path,
       (SELECT a.local_path FROM artwork a WHERE a.owner_type='movie' AND a.owner_id=m.id
        AND a.kind='poster' AND a.local_path<>'' LIMIT 1) AS poster_path
FROM movies m
WHERE EXISTS (SELECT 1 FROM artwork a WHERE a.owner_type='movie' AND a.owner_id=m.id
              AND a.kind='backdrop' AND a.local_path<>'')
ORDER BY m.rating DESC LIMIT 8
"""

HERO_TV_SQL = """
SELECT s.id, s.title, s.overview,
       substr(s.first_air_date, 1, 4) AS year, s.rating,
       'tv_show' AS media_type,
       (SELECT a.local_path FROM artwork a WHERE a.owner_type='tv_show' AND a.owner_id=s.id
        AND a.kind='backdrop' AND a.local_path<>'' LIMIT 1) AS backdrop_path,
       (SELECT a.local_path FROM artwork a WHERE a.owner_type='tv_show' AND a.owner_id=s.id
        AND a.kind='poster' AND a.local_path<>'' LIMIT 1) AS poster_path
FROM tv_shows s
WHERE EXISTS (SELECT 1 FROM artwork a WHERE a.owner_type='tv_show' AND a.owner_id=s.id
              AND a.kind='backdrop' AND a.local_path<>'')
ORDER BY s.rating DESC LIMIT 8
"""


@router.get("/home")
def home(request: Request) -> dict:
    services = request.app.state.context.services
    profile = services.profile.id
    repos = services.repos

    hero = [dict(row) for row in repos.db.query(HERO_SQL)]
    hero += [dict(row) for row in repos.db.query(HERO_TV_SQL)]
    hero.sort(key=lambda row: row.get("rating") or 0, reverse=True)

    return {
        "hero": hero[:10],
        "continue_watching": services.playback.resume.continue_watching(profile, 14),
        "recently_added": services.movies.recently_added(profile, 14),
        "recent_episodes": repos.tv.recent_episodes(profile, 14),
        "recently_played": services.playback.history.recently_played(profile, 14),
        "recommended": services.recommendations.recommended(profile, 14),
        "favorites": repos.lists.favorites(profile),
        "watchlist": repos.lists.watchlist(profile),
        "recent_albums": repos.music.recent_albums(14),
        "stats": services.statistics.overview(profile),
    }
