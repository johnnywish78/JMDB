"""Movie catalog: read-model assembly for the UI."""
from __future__ import annotations

from app.database.repositories import Repositories
from app.domain.value_objects import PlayableItem


class MovieCatalog:
    def __init__(self, repos: Repositories) -> None:
        self.repos = repos

    def list_page(self, profile_id: int, **filters) -> tuple[list[dict], int]:
        return self.repos.movies.list_page(profile_id=profile_id, **filters)

    def recently_added(self, profile_id: int, limit: int = 20) -> list[dict]:
        return self.repos.movies.recently_added(profile_id, limit)

    def detail(self, movie_id: int, profile_id: int) -> dict | None:
        movie = self.repos.movies.get(movie_id)
        if movie is None:
            return None
        detail = {
            "id": movie.id,
            "title": movie.title,
            "original_title": movie.original_title,
            "year": movie.year,
            "release_date": movie.release_date,
            "runtime_seconds": movie.runtime_seconds,
            "overview": movie.overview,
            "tagline": movie.tagline,
            "rating": movie.rating,
            "vote_count": movie.vote_count,
            "certification": movie.certification,
            "languages": movie.languages,
            "countries": movie.countries,
            "genres": self.repos.taxonomy.genres_for("movie", movie_id),
            "studios": self.repos.taxonomy.studios_for("movie", movie_id),
            "external_ids": self.repos.external_ids.all_for("movie", movie_id),
            "trailer_url": self.repos.external_ids.get("movie", movie_id, "trailer") or "",
            "poster_path": self.repos.artwork.local_path("movie", movie_id, "poster"),
            "backdrop_path": self.repos.artwork.local_path("movie", movie_id, "backdrop"),
            "logo_path": self.repos.artwork.local_path("movie", movie_id, "logo"),
            "files": [
                {
                    "id": f.id,
                    "path": f.path,
                    "size_bytes": f.size_bytes,
                    "container": f.container,
                }
                for f in self.repos.files.files_for("movie", movie_id)
            ],
            "credits": self.repos.people.credits_with_people("movie", movie_id),
            "is_favorite": self.repos.lists.is_favorite(profile_id, "movie", movie_id),
            "in_watchlist": self.repos.lists.in_watchlist(profile_id, "movie", movie_id),
            "watched": self.repos.playback.is_watched(profile_id, "movie", movie_id),
            "user_rating": self.repos.lists.get_rating(profile_id, "movie", movie_id),
            "resume": None,
            "franchise": None,
            "franchise_movies": [],
        }
        state = self.repos.playback.get_position(profile_id, "movie", movie_id)
        if state and state.position_seconds > 5:
            detail["resume"] = {
                "position_seconds": state.position_seconds,
                "duration_seconds": state.duration_seconds,
            }
        collection_row = self.repos.db.query_one(
            "SELECT id, name, overview FROM movie_collections WHERE id=?", (movie.collection_id,)
        )
        if collection_row:
            detail["franchise"] = dict(collection_row)
            detail["franchise_movies"] = self.repos.movies.movies_in_collection(
                movie.collection_id, profile_id
            )
        return detail

    def playable(self, movie_id: int) -> PlayableItem | None:
        movie = self.repos.movies.get(movie_id)
        if movie is None:
            return None
        media_file = self.repos.files.primary_file("movie", movie_id)
        if media_file is None:
            return None
        return PlayableItem(
            media_type="movie",
            media_id=movie_id,
            media_file_id=media_file.id,
            path=media_file.path,
            title=movie.title,
            subtitle=str(movie.year or ""),
            duration_seconds=float(movie.runtime_seconds or 0),
            artwork_path=self.repos.artwork.local_path("movie", movie_id, "poster"),
        )
