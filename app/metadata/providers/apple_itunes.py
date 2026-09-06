"""Apple iTunes Search provider — keyless, useful out-of-the-box.

The iTunes Search API (https://developer.apple.com/library/archive/documentation/AudioVideo/Conceptual/iTuneSearchAPI)
is public and free without a key. It provides solid basic movie/TV/music
metadata and high-quality artwork, so JMDB has real, honest enrichment even
before the user configures TMDB/OMDb keys. It is intentionally a *secondary*
source: TMDB/OMDb/TVmaze remain richer for detailed credits.
"""
from __future__ import annotations

from app.metadata.http_client import HttpClient
from app.metadata.normalization import clean_overview, iso_date
from app.metadata.providers.base import (
    AlbumMetadata,
    ArtistMetadata,
    MetadataProvider,
    MovieMetadata,
    ShowMetadata,
)

BASE = "https://itunes.apple.com/search"


def _artwork(row: dict, size: int) -> str:
    url = row.get("artworkUrl100", "") or row.get("artworkUrl60", "")
    if url:
        return url.replace("/100x100bb", f"/{size}x{size}bb").replace("/60x60bb", f"/{size}x{size}bb")
    return ""


class ItunesProvider(MetadataProvider):
    id = "itunes"
    display_name = "Apple iTunes"
    requires_key = False
    capabilities = {"movie", "tv", "artist", "album"}
    min_request_interval = 0.5

    def search_movie(self, title: str, year: int | None = None) -> list[MovieMetadata]:
        data = self.http.get_json(
            BASE, params={"term": title, "media": "movie", "limit": 10}, provider=self.id
        )
        results = []
        for row in data.get("results", []):
            if year and row.get("releaseDate", "")[:4] and abs(int(row["releaseDate"][:4]) - year) > 2:
                continue
            runtime = None
            if row.get("trackTimeMillis"):
                runtime = int(row["trackTimeMillis"] / 1000)
            results.append(
                MovieMetadata(
                    title=row.get("trackName", ""),
                    year=int(row.get("releaseDate", "0000")[:4] or 0) or None,
                    release_date=iso_date(row.get("releaseDate")),
                    runtime_seconds=runtime,
                    overview=clean_overview(row.get("longDescription", "") or row.get("shortDescription", "")),
                    certification=row.get("contentAdvisoryRating", ""),
                    genres=[row.get("primaryGenreName", "")] if row.get("primaryGenreName") else [],
                    poster_url=_artwork(row, 600),
                    external_ids={"itunes": str(row.get("trackId", ""))},
                    provider=self.id,
                )
            )
        return results

    def search_show(self, title: str) -> list[ShowMetadata]:
        data = self.http.get_json(
            BASE, params={"term": title, "media": "tvShow", "limit": 10}, provider=self.id
        )
        results = []
        seen = set()
        for row in data.get("results", []):
            name = row.get("artistName", "")  # show name on tvSeason entries
            key = (name, row.get("collectionName", ""))
            if not name or key in seen:
                continue
            seen.add(key)
            results.append(
                ShowMetadata(
                    title=name,
                    first_air_date=iso_date(row.get("releaseDate")),
                    overview=clean_overview(row.get("longDescription", "") or row.get("shortDescription", "")),
                    genres=[row.get("primaryGenreName", "")] if row.get("primaryGenreName") else [],
                    poster_url=_artwork(row, 600),
                    external_ids={"itunes": str(row.get("collectionId", ""))},
                    provider=self.id,
                )
            )
        return results

    def search_artist(self, name: str) -> list[ArtistMetadata]:
        data = self.http.get_json(
            BASE, params={"term": name, "media": "music", "entity": "musicArtist", "limit": 8}, provider=self.id
        )
        return [
            ArtistMetadata(
                name=row.get("artistName", ""),
                genres=[row.get("primaryGenreName", "")] if row.get("primaryGenreName") else [],
                external_ids={"itunes": str(row.get("artistId", ""))},
                provider=self.id,
            )
            for row in data.get("results", [])[:8]
        ]

    def search_album(self, artist: str, album: str) -> list[AlbumMetadata]:
        data = self.http.get_json(
            BASE,
            params={"term": f"{artist} {album}", "media": "music", "entity": "album", "limit": 8},
            provider=self.id,
        )
        results = []
        for row in data.get("results", []):
            if artist.lower() not in (row.get("artistName", "") or "").lower():
                continue
            results.append(
                AlbumMetadata(
                    title=row.get("collectionName", ""),
                    artist=row.get("artistName", ""),
                    year=int(row.get("releaseDate", "0000")[:4] or 0) or None,
                    release_date=iso_date(row.get("releaseDate")),
                    genres=[row.get("primaryGenreName", "")] if row.get("primaryGenreName") else [],
                    cover_url=_artwork(row, 600),
                    external_ids={"itunes": str(row.get("collectionId", ""))},
                    provider=self.id,
                )
            )
        return results
