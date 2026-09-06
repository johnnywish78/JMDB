"""TheAudioDB provider — free music metadata/artwork.

TheAudioDB offers a free tier for personal apps; the API key is configurable
in Settings (their publicly documented free test key is used as the default
when nothing is configured).
"""
from __future__ import annotations

from app.metadata.http_client import HttpClient
from app.metadata.providers.base import (
    AlbumMetadata,
    ArtistMetadata,
    MetadataProvider,
)

BASE = "https://www.theaudiodb.com/api/v1/json"
FREE_KEY = "2"  # TheAudioDB's publicly documented free test key


class TheAudioDbProvider(MetadataProvider):
    id = "theaudiodb"
    display_name = "TheAudioDB"
    requires_key = False
    capabilities = {"artist", "album"}
    min_request_interval = 0.5

    @property
    def key(self) -> str:
        return self.api_key or FREE_KEY

    def search_artist(self, name: str) -> list[ArtistMetadata]:
        data = self.http.get_json(
            f"{BASE}/{self.key}/search.php", params={"s": name}, provider=self.id
        )
        results = []
        for row in (data.get("artists") or [])[:8]:
            if not row:
                continue
            results.append(
                ArtistMetadata(
                    name=row.get("strArtist", ""),
                    biography=row.get("strBiographyEN", "") or "",
                    genres=[g for g in (row.get("strGenre", "") or "").split("/") if g],
                    photo_url=row.get("strArtistThumb", "") or "",
                    banner_url=row.get("strArtistFanart", "") or "",
                    external_ids={"theaudiodb": str(row.get("idArtist", "") or "")},
                    provider=self.id,
                )
            )
        return results

    def artist_details(self, external_ref: str) -> ArtistMetadata | None:
        data = self.http.get_json(
            f"{BASE}/{self.key}/artist.php", params={"i": external_ref}, provider=self.id
        )
        artists = data.get("artists") or []
        if not artists or not artists[0]:
            return None
        row = artists[0]
        return ArtistMetadata(
            name=row.get("strArtist", ""),
            biography=row.get("strBiographyEN", "") or "",
            genres=[g for g in (row.get("strGenre", "") or "").split("/") if g],
            photo_url=row.get("strArtistThumb", "") or "",
            banner_url=row.get("strArtistFanart", "") or "",
            external_ids={"theaudiodb": str(row.get("idArtist", "") or "")},
            provider=self.id,
        )

    def search_album(self, artist: str, album: str) -> list[AlbumMetadata]:
        data = self.http.get_json(
            f"{BASE}/{self.key}/searchalbum.php", params={"s": artist, "a": album}, provider=self.id
        )
        results = []
        for row in (data.get("album") or [])[:8]:
            if not row:
                continue
            year = None
            try:
                year = int(row.get("intYearReleased", "") or 0) or None
            except ValueError:
                pass
            results.append(
                AlbumMetadata(
                    title=row.get("strAlbum", ""),
                    artist=row.get("strArtist", ""),
                    year=year,
                    genres=[g for g in (row.get("strGenre", "") or "").split("/") if g],
                    cover_url=row.get("strAlbumThumb", "") or "",
                    external_ids={"theaudiodb": str(row.get("idAlbum", "") or "")},
                    provider=self.id,
                )
            )
        return results
