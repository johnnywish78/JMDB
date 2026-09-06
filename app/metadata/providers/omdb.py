"""OMDb provider (http://www.omdbapi.com) — IMDb-linked metadata."""
from __future__ import annotations

from app.metadata.http_client import HttpClient
from app.metadata.normalization import clean_overview
from app.metadata.providers.base import (
    MetadataProvider,
    MovieMetadata,
    PersonCredit,
    ShowMetadata,
)

BASE = "https://www.omdbapi.com/"


def _parse_runtime(runtime: str) -> int | None:
    if not runtime or " min" not in runtime:
        return None
    try:
        return int(runtime.split(" min")[0]) * 60
    except ValueError:
        return None


class OmdbProvider(MetadataProvider):
    id = "omdb"
    display_name = "OMDb"
    requires_key = True
    key_provider_name = "omdb"
    capabilities = {"movie", "tv"}

    def _get(self, **params) -> dict:
        params["apikey"] = self._require_key()
        data = self.http.get_json(BASE, params=params, provider=self.id)
        if data.get("Response") == "False":
            error = data.get("Error", "unknown OMDb error")
            if "not found" in error.lower():
                return {}
            raise RuntimeError(error)
        return data

    def search_movie(self, title: str, year: int | None = None) -> list[MovieMetadata]:
        params = {"s": title, "type": "movie"}
        if year:
            params["y"] = year
        try:
            data = self._get(**params)
        except RuntimeError:
            return []
        results = []
        for row in (data.get("Search") or [])[:10]:
            try:
                results.append(
                    MovieMetadata(
                        title=row.get("Title", ""),
                        year=int(row["Year"][:4]) if row.get("Year", "")[:4].isdigit() else None,
                        poster_url=row.get("Poster", "") if row.get("Poster", "") != "N/A" else "",
                        external_ids={"imdb": row.get("imdbID", "")},
                        provider=self.id,
                    )
                )
            except (ValueError, KeyError):
                continue
        return results

    def movie_details(self, external_ref: str) -> MovieMetadata | None:
        data = self._get(i=external_ref, plot="full") if external_ref.startswith("tt") else None
        if data:
            return self._detail_to_movie(data)
        # try tmdb-style numeric ids via title search fallback: not supported by OMDb
        return None

    def search_show(self, title: str) -> list[ShowMetadata]:
        try:
            data = self._get(s=title, type="series")
        except RuntimeError:
            return []
        results = []
        for row in (data.get("Search") or [])[:10]:
            results.append(
                ShowMetadata(
                    title=row.get("Title", ""),
                    first_air_date=f"{row.get('Year', '')[:4]}-01-01"
                    if row.get("Year", "")[:4].isdigit()
                    else "",
                    poster_url=row.get("Poster", "") if row.get("Poster", "") != "N/A" else "",
                    external_ids={"imdb": row.get("imdbID", "")},
                    provider=self.id,
                )
            )
        return results

    def _detail_to_movie(self, data: dict) -> MovieMetadata:
        ratings = {r["Source"]: r["Value"] for r in data.get("Ratings", []) if "Source" in r}
        imdb_rating = None
        if "Internet Movie Database" in ratings:
            try:
                imdb_rating = float(ratings["Internet Movie Database"].split("/")[0])
            except (ValueError, IndexError):
                pass
        return MovieMetadata(
            title=data.get("Title", ""),
            year=int(data["Year"][:4]) if data.get("Year", "")[:4].isdigit() else None,
            release_date=data.get("Released", "") if data.get("Released", "") not in ("N/A", "") else "",
            runtime_seconds=_parse_runtime(data.get("Runtime", "")),
            overview=clean_overview(data.get("Plot", "") if data.get("Plot") != "N/A" else ""),
            rating=imdb_rating,
            vote_count=None,
            certification=data.get("Rated", "") if data.get("Rated") != "N/A" else "",
            languages=data.get("Language", "") if data.get("Language") != "N/A" else "",
            countries=data.get("Country", "") if data.get("Country") != "N/A" else "",
            genres=[g.strip() for g in data.get("Genre", "").split(",") if g.strip() and g != "N/A"],
            poster_url=data.get("Poster", "") if data.get("Poster") not in ("N/A", "") else "",
            cast=[
                PersonCredit(name=name.strip(), role="actor", sort_order=i)
                for i, name in enumerate(data.get("Actors", "").split(","))
                if name.strip() and name != "N/A"
            ],
            crew=self._crew_from_omdb(data),
            external_ids={"imdb": data.get("imdbID", "")},
            provider=self.id,
        )

    @staticmethod
    def _crew_from_omdb(data: dict) -> list[PersonCredit]:
        crew = []
        crew.extend(
            PersonCredit(name=name.strip(), role="director")
            for name in data.get("Director", "").split(",")
            if name.strip() and name != "N/A"
        )
        crew.extend(
            PersonCredit(name=name.strip(), role="writer")
            for name in data.get("Writer", "").split(",")
            if name.strip() and name != "N/A"
        )
        return crew

    def detail_by_imdb_id(self, imdb_id: str) -> MovieMetadata | None:
        if not imdb_id:
            return None
        try:
            data = self._get(i=imdb_id, plot="full")
        except RuntimeError:
            return None
        return self._detail_to_movie(data) if data else None
