"""MusicBrainz provider — keyless (requires a proper User-Agent; 1 rps)."""
from __future__ import annotations

from app.metadata.http_client import HttpClient
from app.metadata.normalization import iso_date
from app.metadata.providers.base import (
    AlbumMetadata,
    ArtistMetadata,
    MetadataProvider,
)

BASE = "https://musicbrainz.org/ws/2"


class MusicBrainzProvider(MetadataProvider):
    id = "musicbrainz"
    display_name = "MusicBrainz"
    requires_key = False
    capabilities = {"artist", "album"}
    min_request_interval = 1.1  # MusicBrainz rate limit: max 1 req/sec

    def search_artist(self, name: str) -> list[ArtistMetadata]:
        data = self.http.get_json(
            f"{BASE}/artist/",
            params={"query": name, "fmt": "json", "limit": 8},
            provider=self.id,
        )
        results = []
        for row in data.get("artists", [])[:8]:
            results.append(
                ArtistMetadata(
                    name=row.get("name", ""),
                    sort_name=row.get("sort-name", ""),
                    disambiguation=row.get("disambiguation", ""),
                    external_ids={"musicbrainz": row.get("id", "")},
                    provider=self.id,
                )
            )
        return results

    def artist_details(self, external_ref: str) -> ArtistMetadata | None:
        data = self.http.get_json(
            f"{BASE}/artist/{external_ref}",
            params={"fmt": "json", "inc": "url-rels+tags"},
            provider=self.id,
        )
        genres = [t.get("name", "") for t in data.get("tags", []) if t.get("name")][:5]
        return ArtistMetadata(
            name=data.get("name", ""),
            sort_name=data.get("sort-name", ""),
            disambiguation=data.get("disambiguation", ""),
            genres=genres,
            external_ids={"musicbrainz": data.get("id", "")},
            provider=self.id,
        )

    def search_album(self, artist: str, album: str) -> list[AlbumMetadata]:
        query = f'artist:"{artist}" AND releasegroup:"{album}"'
        data = self.http.get_json(
            f"{BASE}/release-group/",
            params={"query": query, "fmt": "json", "limit": 8},
            provider=self.id,
        )
        results = []
        for row in data.get("release-groups", [])[:8]:
            results.append(
                AlbumMetadata(
                    title=row.get("title", ""),
                    artist=artist,
                    year=int(row.get("first-release-date", "0000")[:4] or 0) or None,
                    release_date=iso_date(row.get("first-release-date")),
                    cover_url=self._cover_url(row.get("id", "")),
                    external_ids={"musicbrainz": row.get("id", "")},
                    provider=self.id,
                )
            )
        return results

    def albums_for_artist(self, external_ref: str) -> list[AlbumMetadata]:
        data = self.http.get_json(
            f"{BASE}/release-group",
            params={"artist": external_ref, "type": "album", "fmt": "json", "limit": 50},
            provider=self.id,
        )
        return [
            AlbumMetadata(
                title=row.get("title", ""),
                year=int(row.get("first-release-date", "0000")[:4] or 0) or None,
                release_date=iso_date(row.get("first-release-date")),
                cover_url=self._cover_url(row.get("id", "")),
                external_ids={"musicbrainz": row.get("id", "")},
                provider=self.id,
            )
            for row in data.get("release-groups", [])
        ]

    @staticmethod
    def _cover_url(release_group_id: str) -> str:
        if not release_group_id:
            return ""
        return f"https://coverartarchive.org/release-group/{release_group_id}/front-500"
