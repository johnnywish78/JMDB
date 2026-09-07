"""TMDB provider (https://api.themoviedb.org, v3 API key)."""
from __future__ import annotations

from app.metadata.http_client import HttpClient
from app.metadata.normalization import clean_overview, iso_date
from app.metadata.providers.base import (
    EpisodeMetadata,
    MetadataProvider,
    MovieMetadata,
    PersonCredit,
    PersonMetadata,
    SeasonMetadata,
    ShowMetadata,
)

BASE = "https://api.themoviedb.org/3"
IMAGE_BASE = "https://image.tmdb.org/t/p"


class TmdbProvider(MetadataProvider):
    id = "tmdb"
    display_name = "TMDB"
    requires_key = True
    key_provider_name = "tmdb"
    capabilities = {"movie", "tv", "person"}
    min_request_interval = 0.25
    website = "https://www.themoviedb.org"
    supplies = "Movie, TV and people metadata, posters and backdrops (primary source)"

    def test_connection(self, api_key: str = "") -> dict:
        key = api_key or self.api_key
        if not key:
            return {"ok": False, "detail": "no API key configured"}
        try:
            self.http.get_json(f"{BASE}/configuration", params={"api_key": key}, provider=self.id)
            return {"ok": True, "detail": "TMDB accepted the key"}
        except Exception as exc:
            return {"ok": False, "detail": str(exc)}

    def _image(self, path: str, size: str = "original") -> str:
        if not path:
            return ""
        return f"{IMAGE_BASE}/{size}{path}"

    # -- movies ---------------------------------------------------------------
    def search_movie(self, title: str, year: int | None = None) -> list[MovieMetadata]:
        key = self._require_key()
        params = {"api_key": key, "query": title, "include_adult": "false"}
        if year:
            params["year"] = year
        data = self.http.get_json(
            f"{BASE}/search/movie", params=params, provider=self.id
        )
        results = []
        for row in data.get("results", [])[:10]:
            results.append(
                MovieMetadata(
                    title=row.get("title", ""),
                    original_title=row.get("original_title", ""),
                    year=int(row.get("release_date", "0000")[:4] or 0) or None,
                    release_date=iso_date(row.get("release_date")),
                    overview=clean_overview(row.get("overview", "")),
                    rating=row.get("vote_average") or None,
                    vote_count=row.get("vote_count") or None,
                    poster_url=self._image(row.get("poster_path"), "w500"),
                    backdrop_url=self._image(row.get("backdrop_path")),
                    external_ids={"tmdb": str(row.get("id", ""))},
                    provider=self.id,
                )
            )
        return results

    def movie_details(self, external_ref: str) -> MovieMetadata | None:
        key = self._require_key()
        data = self.http.get_json(
            f"{BASE}/movie/{external_ref}",
            params={
                "api_key": key,
                "append_to_response": "credits,external_ids,release_dates,videos,images",
                "include_image_language": "en,null",
            },
            provider=self.id,
        )
        certification = ""
        for release in data.get("release_dates", {}).get("results", []):
            for entry in release.get("release_dates", []):
                if entry.get("certification"):
                    certification = entry["certification"]
                    break
            if certification:
                break
        trailer = ""
        for video in data.get("videos", {}).get("results", []):
            if video.get("site") == "YouTube" and video.get("type") == "Trailer":
                trailer = f"https://www.youtube.com/watch?v={video.get('key')}"
                break
        images = data.get("images", {})
        logo_path = ""
        for logo in images.get("logos", []):
            if logo.get("iso_639_1") in ("en", None):
                logo_path = logo.get("file_path", "")
                break
        cast = [
            PersonCredit(
                name=entry.get("name", ""),
                role="actor",
                character=entry.get("character", ""),
                photo_url=self._image(entry.get("profile_path"), "w300"),
                sort_order=entry.get("order", 0),
                tmdb_id=str(entry.get("id", "")) if entry.get("id") else None,
            )
            for entry in data.get("credits", {}).get("cast", [])[:25]
        ]
        crew = []
        for entry in data.get("credits", {}).get("crew", []):
            job = entry.get("job", "")
            role = job.lower() if job.lower() in ("director", "writer", "producer") else "crew"
            crew.append(
                PersonCredit(
                    name=entry.get("name", ""),
                    role=role,
                    job=job,
                    photo_url=self._image(entry.get("profile_path"), "w300"),
                    tmdb_id=str(entry.get("id", "")) if entry.get("id") else None,
                )
            )
        ext = data.get("external_ids", {}) or {}
        return MovieMetadata(
            title=data.get("title", ""),
            original_title=data.get("original_title", ""),
            year=int(data.get("release_date", "0000")[:4] or 0) or None,
            release_date=iso_date(data.get("release_date")),
            runtime_seconds=(data.get("runtime") or 0) * 60 or None,
            overview=clean_overview(data.get("overview", "")),
            tagline=data.get("tagline", ""),
            rating=data.get("vote_average") or None,
            vote_count=data.get("vote_count") or None,
            certification=certification,
            languages=", ".join(
                sorted({s.get("iso_639_1", "") for s in data.get("spoken_languages", []) if s.get("iso_639_1")})
            ),
            countries=", ".join(
                sorted({c.get("iso_3166_1", "") for c in data.get("production_countries", []) if c.get("iso_3166_1")})
            ),
            genres=[g["name"] for g in data.get("genres", [])],
            studios=[s["name"] for s in data.get("production_companies", [])[:5]],
            collection=(data.get("belongs_to_collection") or {}).get("name", ""),
            trailer_url=trailer,
            poster_url=self._image(data.get("poster_path"), "w500"),
            backdrop_url=self._image(data.get("backdrop_path")),
            logo_url=self._image(logo_path, "w300"),
            cast=cast,
            crew=crew,
            external_ids={
                "tmdb": str(data.get("id", "")),
                "imdb": ext.get("imdb_id", "") or "",
            },
            provider=self.id,
        )

    # -- tv ----------------------------------------------------------------------
    def search_show(self, title: str) -> list[ShowMetadata]:
        key = self._require_key()
        data = self.http.get_json(
            f"{BASE}/search/tv",
            params={"api_key": key, "query": title, "include_adult": "false"},
            provider=self.id,
        )
        results = []
        for row in data.get("results", [])[:10]:
            results.append(
                ShowMetadata(
                    title=row.get("name", ""),
                    original_title=row.get("original_name", ""),
                    first_air_date=iso_date(row.get("first_air_date")),
                    overview=clean_overview(row.get("overview", "")),
                    rating=row.get("vote_average") or None,
                    vote_count=row.get("vote_count") or None,
                    poster_url=self._image(row.get("poster_path"), "w500"),
                    backdrop_url=self._image(row.get("backdrop_path")),
                    external_ids={"tmdb": str(row.get("id", ""))},
                    provider=self.id,
                )
            )
        return results

    def show_details(self, external_ref: str, seasons: bool = True) -> ShowMetadata | None:
        key = self._require_key()
        data = self.http.get_json(
            f"{BASE}/tv/{external_ref}",
            params={"api_key": key, "append_to_response": "credits,external_ids"},
            provider=self.id,
        )
        show = ShowMetadata(
            title=data.get("name", ""),
            original_title=data.get("original_name", ""),
            first_air_date=iso_date(data.get("first_air_date")),
            last_air_date=iso_date(data.get("last_air_date")),
            status=data.get("status", ""),
            overview=clean_overview(data.get("overview", "")),
            rating=data.get("vote_average") or None,
            vote_count=data.get("vote_count") or None,
            genres=[g["name"] for g in data.get("genres", [])],
            networks=[n["name"] for n in data.get("networks", [])],
            studios=[c["name"] for c in data.get("production_companies", [])[:5]],
            poster_url=self._image(data.get("poster_path"), "w500"),
            backdrop_url=self._image(data.get("backdrop_path")),
            cast=[
                PersonCredit(
                    name=entry.get("name", ""),
                    role="actor",
                    character=entry.get("character", ""),
                    photo_url=self._image(entry.get("profile_path"), "w300"),
                    sort_order=entry.get("order", 0),
                    tmdb_id=str(entry.get("id", "")) if entry.get("id") else None,
                )
                for entry in data.get("credits", {}).get("cast", [])[:25]
            ],
            crew=[
                PersonCredit(
                    name=entry.get("name", ""),
                    role=entry.get("job", "").lower()
                    if entry.get("job", "").lower() in ("director", "writer", "producer")
                    else "crew",
                    job=entry.get("job", ""),
                    photo_url=self._image(entry.get("profile_path"), "w300"),
                    tmdb_id=str(entry.get("id", "")) if entry.get("id") else None,
                )
                for entry in data.get("credits", {}).get("crew", [])[:25]
            ],
            external_ids={
                "tmdb": str(data.get("id", "")),
                "imdb": (data.get("external_ids") or {}).get("imdb_id", "") or "",
                "tvdb": str((data.get("external_ids") or {}).get("tvdb_id", "") or ""),
            },
            provider=self.id,
        )
        if seasons:
            for season_summary in data.get("seasons", []):
                number = season_summary.get("season_number", 0)
                season_data = self.http.get_json(
                    f"{BASE}/tv/{external_ref}/season/{number}",
                    params={"api_key": key},
                    provider=self.id,
                )
                season = SeasonMetadata(
                    season_number=number,
                    title=season_data.get("name", ""),
                    overview=clean_overview(season_data.get("overview", "")),
                    air_date=iso_date(season_data.get("air_date")),
                    poster_url=self._image(season_data.get("poster_path"), "w500"),
                    episodes=[
                        EpisodeMetadata(
                            episode_number=ep.get("episode_number", 0),
                            title=ep.get("name", ""),
                            overview=clean_overview(ep.get("overview", "")),
                            air_date=iso_date(ep.get("air_date")),
                            runtime_seconds=(ep.get("runtime") or 0) * 60 or None,
                            rating=ep.get("vote_average") or None,
                            still_url=self._image(ep.get("still_path"), "w300"),
                        )
                        for ep in season_data.get("episodes", [])
                    ],
                )
                show.seasons.append(season)
        return show

    # -- people ---------------------------------------------------------------------
    def find_person(self, name: str) -> list[PersonMetadata]:
        key = self._require_key()
        data = self.http.get_json(
            f"{BASE}/search/person",
            params={"api_key": key, "query": name},
            provider=self.id,
        )
        return [
            PersonMetadata(
                name=row.get("name", ""),
                photo_url=self._image(row.get("profile_path"), "w300"),
                external_ids={"tmdb": str(row.get("id", ""))},
                provider=self.id,
            )
            for row in data.get("results", [])[:8]
        ]

    def person_details(self, external_ref: str) -> PersonMetadata | None:
        key = self._require_key()
        data = self.http.get_json(
            f"{BASE}/person/{external_ref}",
            params={"api_key": key, "append_to_response": "external_ids"},
            provider=self.id,
        )
        ext = data.get("external_ids", {}) or {}
        return PersonMetadata(
            name=data.get("name", ""),
            biography=clean_overview(data.get("biography", "")),
            birthday=iso_date(data.get("birthday")),
            deathday=iso_date(data.get("deathday")),
            place_of_birth=data.get("place_of_birth", ""),
            photo_url=self._image(data.get("profile_path"), "w300"),
            external_ids={
                "tmdb": str(data.get("id", "")),
                "imdb": ext.get("imdb_id", "") or "",
            },
            provider=self.id,
        )
