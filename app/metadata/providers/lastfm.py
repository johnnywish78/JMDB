"""Last.fm provider (requires API key)."""
from __future__ import annotations

from app.metadata.http_client import HttpClient
from app.metadata.providers.base import (
    AlbumMetadata,
    ArtistMetadata,
    MetadataProvider,
)

BASE = "https://ws.audioscrobbler.com/2.0/"


class LastFmProvider(MetadataProvider):
    id = "lastfm"
    display_name = "Last.fm"
    requires_key = True
    key_provider_name = "lastfm"
    capabilities = {"artist", "album"}

    def _call(self, method: str, **params) -> dict:
        params.update(
            {
                "method": method,
                "api_key": self._require_key(),
                "format": "json",
            }
        )
        return self.http.get_json(BASE, params=params, provider=self.id)

    def search_artist(self, name: str) -> list[ArtistMetadata]:
        data = self._call("artist.search", artist=name, limit=8)
        results = []
        for row in (data.get("results", {}).get("artistmatches", {}) or {}).get("artist", [])[:8]:
            image = self._image(row.get("image", []))
            results.append(
                ArtistMetadata(
                    name=row.get("name", ""),
                    photo_url=image,
                    external_ids={"lastfm": row.get("mbid", "") or ""},
                    provider=self.id,
                )
            )
        return results

    def artist_details(self, external_ref: str) -> ArtistMetadata | None:
        data = self._call("artist.getinfo", mbid=external_ref)
        artist = data.get("artist", {})
        if not artist:
            return None
        return ArtistMetadata(
            name=artist.get("name", ""),
            biography=self._strip_links(artist.get("bio", {}).get("summary", "")),
            genres=[t.get("name", "") for t in artist.get("tags", {}).get("tag", []) if t.get("name")][:6],
            photo_url=self._image(artist.get("image", [])),
            external_ids={"lastfm": artist.get("mbid", "") or ""},
            provider=self.id,
        )

    def search_album(self, artist: str, album: str) -> list[AlbumMetadata]:
        data = self._call("album.search", album=album, limit=8)
        matches = (data.get("results", {}).get("albummatches", {}) or {}).get("album", [])
        out = []
        for row in matches[:8]:
            if artist.lower() not in (row.get("artist", "") or "").lower():
                continue
            out.append(
                AlbumMetadata(
                    title=row.get("name", ""),
                    artist=row.get("artist", ""),
                    cover_url=self._image(row.get("image", []), size="extralarge"),
                    external_ids={"lastfm": row.get("mbid", "") or ""},
                    provider=self.id,
                )
            )
        return out

    @staticmethod
    def _strip_links(text: str) -> str:
        import re

        return re.sub(r"<a[^>]*>.*?</a>", "", text or "").strip()

    @staticmethod
    def _image(images: list, size: str = "large") -> str:
        if not isinstance(images, list):
            return ""
        for image in images:
            if isinstance(image, dict) and image.get("size") == size:
                return image.get("#text", "") or ""
        for image in images:
            if isinstance(image, dict) and image.get("#text"):
                return image["#text"]
        return ""
