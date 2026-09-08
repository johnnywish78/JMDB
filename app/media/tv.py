"""TV catalog: show/season/episode read-models for the UI."""
from __future__ import annotations

from app.database.repositories import Repositories
from app.domain.value_objects import PlayableItem


class TvCatalog:
    def __init__(self, repos: Repositories) -> None:
        self.repos = repos

    def list_shows(self, profile_id: int, **filters) -> tuple[list[dict], int]:
        return self.repos.tv.list_shows(profile_id=profile_id, **filters)

    def show_detail(self, show_id: int, profile_id: int) -> dict | None:
        show = self.repos.tv.get_show(show_id)
        if show is None:
            return None
        seasons = self.repos.tv.seasons_for_show(show_id, profile_id)
        total_episodes = sum(s["episode_count"] for s in seasons)
        watched = sum(s["watched_count"] for s in seasons)
        unwatched_ids = self.repos.tv.unwatched_episode_ids(show_id, profile_id)
        next_episode = None
        for episode_id in unwatched_ids:
            row = self.repos.tv.episode_details(episode_id, profile_id)
            if row and row.get("file_path"):
                next_episode = row
                break
        return {
            "id": show.id,
            "title": show.title,
            "original_title": show.original_title,
            "first_air_date": show.first_air_date,
            "last_air_date": show.last_air_date,
            "status": show.status,
            "overview": show.overview,
            "rating": show.rating,
            "vote_count": show.vote_count,
            "genres": self.repos.taxonomy.genres_for("tv_show", show_id),
            "networks": self.repos.taxonomy.networks_for(show_id),
            "studios": self.repos.taxonomy.studios_for("tv_show", show_id),
            "external_ids": self.repos.external_ids.all_for("tv_show", show_id),
            "poster_path": self.repos.artwork.local_path("tv_show", show_id, "poster"),
            "backdrop_path": self.repos.artwork.local_path("tv_show", show_id, "backdrop"),
            "logo_path": self.repos.artwork.local_path("tv_show", show_id, "logo"),
            "seasons": seasons,
            "season_count": len(seasons),
            "episode_count": total_episodes,
            "watched_count": watched,
            "next_episode": next_episode,
            "credits": self.repos.people.credits_with_people("tv_show", show_id),
            "is_favorite": self.repos.lists.is_favorite(profile_id, "tv_show", show_id),
            "in_watchlist": self.repos.lists.in_watchlist(profile_id, "tv_show", show_id),
            "watched": total_episodes > 0 and watched == total_episodes,
        }

    def next_episode_after(self, episode_id: int, profile_id: int) -> dict | None:
        """The next playable episode after this one (same season, then later
        seasons). Backend-owned logic: the player just asks."""
        current = self.repos.tv.episode_details(episode_id, profile_id)
        if current is None:
            return None
        season = self.repos.tv.get_season(current["season_id"])
        show_id = current["tv_show_id"]

        seasons = self.repos.tv.seasons_for_show(show_id, profile_id)
        ordered = [s for s in seasons]
        if season is not None:
            try:
                start_index = [s["id"] for s in ordered].index(season.id)
            except ValueError:
                start_index = 0
            ordered = ordered[start_index:]

        seen_current = False
        for season_row in ordered:
            for episode in self.repos.tv.episodes_for_season(season_row["id"], profile_id):
                if episode["id"] == episode_id:
                    seen_current = True
                    continue
                if seen_current and episode.get("file_path"):
                    return episode
        return None

    def season_detail(self, season_id: int, profile_id: int) -> dict | None:
        season = self.repos.tv.get_season(season_id)
        if season is None:
            return None
        show = self.repos.tv.get_show(season.tv_show_id)
        episodes = self.repos.tv.episodes_for_season(season_id, profile_id)
        return {
            "id": season.id,
            "show_id": season.tv_show_id,
            "show_title": show.title if show else "",
            "season_number": season.season_number,
            "title": season.title or f"Season {season.season_number}",
            "overview": season.overview,
            "air_date": season.air_date,
            "poster_path": self.repos.artwork.local_path("season", season_id, "season_poster"),
            "show_poster_path": self.repos.artwork.local_path("tv_show", season.tv_show_id, "poster"),
            "episodes": episodes,
            "episode_count": len(episodes),
            "watched_count": sum(1 for e in episodes if e["watched"]),
        }

    def episode_detail(self, episode_id: int, profile_id: int) -> dict | None:
        detail = self.repos.tv.episode_details(episode_id, profile_id)
        if detail is None:
            return None
        episode = self.repos.tv.get_episode(episode_id)
        detail["season_title"] = f"Season {detail['season_number']}"
        detail["show_poster_path"] = self.repos.artwork.local_path("tv_show", detail["tv_show_id"], "poster")
        detail["external_ids"] = self.repos.external_ids.all_for("episode", episode_id)
        detail["guest_cast"] = self.repos.people.credits_with_people("episode", episode_id)
        detail["is_favorite"] = self.repos.lists.is_favorite(profile_id, "episode", episode_id)
        detail["files"] = [
            {"id": f.id, "path": f.path, "size_bytes": f.size_bytes, "container": f.container}
            for f in self.repos.files.files_for("episode", episode_id)
        ]
        detail["runtime_seconds"] = detail.get("runtime_seconds") or (episode.runtime_seconds if episode else None)
        return detail

    def playable(self, episode_id: int) -> PlayableItem | None:
        detail = self.repos.tv.episode_details(episode_id, profile_id=1)
        if detail is None or not detail.get("file_path"):
            return None
        media_file = self.repos.files.primary_file("episode", episode_id)
        if media_file is None:
            return None
        return PlayableItem(
            media_type="episode",
            media_id=episode_id,
            media_file_id=media_file.id,
            path=media_file.path,
            title=detail["show_title"],
            subtitle=f"S{detail['season_number']:02d}E{detail['episode_number']:02d}"
            + (f" · {detail['title']}" if detail.get("title") else ""),
            duration_seconds=float(detail.get("runtime_seconds") or 0),
            # General artwork chain: episode still -> season poster -> show
            # poster. Works for any show: locally-scanned libraries often
            # have no episode stills, but do have season/show posters.
            artwork_path=(
                detail.get("still_path")
                or self.repos.artwork.local_path("season", detail["season_id"], "season_poster")
                or detail.get("poster_path")
                or ""
            ),
        )
