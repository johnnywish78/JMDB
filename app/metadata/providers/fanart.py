"""Fanart.tv provider — secondary artwork source (requires personal API key)."""
from __future__ import annotations

from app.metadata.http_client import HttpClient
from app.metadata.providers.base import MetadataProvider

BASE = "https://webservice.fanart.tv/v3"


class FanartProvider(MetadataProvider):
    """Artwork-only provider: posters/backgrounds/logos by TVDB or TMDB id."""

    id = "fanarttv"
    display_name = "Fanart.tv"
    requires_key = True
    key_provider_name = "fanarttv"
    capabilities = {"artwork"}
    min_request_interval = 0.5

    def artwork_for_tv(self, tvdb_id: str) -> dict[str, list[str]]:
        key = self._require_key()
        data = self.http.get_json(
            f"{BASE}/tv/{tvdb_id}", params={"api_key": key}, provider=self.id
        )
        return self._extract(data)

    def artwork_for_movie(self, tmdb_id: str) -> dict[str, list[str]]:
        key = self._require_key()
        data = self.http.get_json(
            f"{BASE}/movies/{tmdb_id}", params={"api_key": key}, provider=self.id
        )
        return self._extract(data)

    @staticmethod
    def _extract(data: dict) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        mapping = {
            "poster": ("tvposter", "movieposter"),
            "backdrop": ("showbackground", "moviebackground"),
            "logo": ("hdtvlogo", "movielogo", "clearlogo"),
        }
        for kind, sections in mapping.items():
            urls = []
            for section in sections:
                for entry in data.get(section, []) or []:
                    url = entry.get("url", "")
                    if url:
                        urls.append(url)
            out[kind] = urls
        return out
