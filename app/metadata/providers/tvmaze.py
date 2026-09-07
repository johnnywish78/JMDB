"""TVmaze provider — free, keyless TV metadata (https://api.tvmaze.com)."""
from __future__ import annotations

from app.metadata.http_client import HttpClient
from app.metadata.normalization import clean_overview, iso_date
from app.metadata.providers.base import (
    EpisodeMetadata,
    MetadataProvider,
    PersonCredit,
    SeasonMetadata,
    ShowMetadata,
)

BASE = "https://api.tvmaze.com"


class TvMazeProvider(MetadataProvider):
    id = "tvmaze"
    display_name = "TVmaze"
    requires_key = False
    capabilities = {"tv"}
    min_request_interval = 0.3
    website = "https://www.tvmaze.com/api"
    supplies = "TV show, season and episode metadata (no key needed)"

    def test_connection(self, api_key: str = "") -> dict:
        try:
            data = self.http.get_json(f"{BASE}/search/shows", params={"q": "girls"}, provider=self.id)
            return {"ok": True, "detail": f"TVmaze reachable ({len(data)} results)"}
        except Exception as exc:
            return {"ok": False, "detail": str(exc)}

    def search_show(self, title: str) -> list[ShowMetadata]:
        data = self.http.get_json(
            f"{BASE}/search/shows", params={"q": title}, provider=self.id
        )
        results = []
        for row in data[:10]:
            show = row.get("show", {})
            image = show.get("image", {}) or {}
            results.append(
                ShowMetadata(
                    title=show.get("name", ""),
                    first_air_date=iso_date(show.get("premiered")),
                    overview=clean_overview(show.get("summary", "").replace("<p>", "").replace("</p>", "") if show.get("summary") else ""),
                    rating=(show.get("rating", {}) or {}).get("average"),
                    genres=show.get("genres", []) or [],
                    networks=[(show.get("network", {}) or {}).get("name", "")]
                    if show.get("network") else
                    [(show.get("webChannel", {}) or {}).get("name", "")]
                    if show.get("webChannel") else [],
                    status=show.get("status", ""),
                    poster_url=image.get("original", "") or image.get("medium", ""),
                    external_ids={"tvmaze": str(show.get("id", ""))},
                    provider=self.id,
                )
            )
        return results

    def show_details(self, external_ref: str, seasons: bool = True) -> ShowMetadata | None:
        show = self.http.get_json(f"{BASE}/shows/{external_ref}", params={"embed": ["cast", "crew"]}, provider=self.id)
        image = show.get("image", {}) or {}
        cast = [
            PersonCredit(
                name=(entry.get("person", {}) or {}).get("name", ""),
                role="actor",
                character=(entry.get("character", {}) or {}).get("name", ""),
                photo_url=((entry.get("person", {}) or {}).get("image", {}) or {}).get("medium", ""),
                sort_order=i,
            )
            for i, entry in enumerate((show.get("_embedded", {}) or {}).get("cast", [])[:25])
        ]
        crew = []
        for entry in (show.get("_embedded", {}) or {}).get("crew", [])[:25]:
            crew.append(
                PersonCredit(
                    name=(entry.get("person", {}) or {}).get("name", ""),
                    role=entry.get("type", "").lower()
                    if entry.get("type", "").lower() in ("director", "writer", "producer")
                    else "crew",
                    job=entry.get("type", ""),
                )
            )
        result = ShowMetadata(
            title=show.get("name", ""),
            first_air_date=iso_date(show.get("premiered")),
            status=show.get("status", ""),
            overview=clean_overview((show.get("summary") or "").replace("<p>", "").replace("</p>", "")),
            rating=(show.get("rating", {}) or {}).get("average"),
            genres=show.get("genres", []) or [],
            networks=[(show.get("network", {}) or {}).get("name", "")]
            if show.get("network") else
            [(show.get("webChannel", {}) or {}).get("name", "")]
            if show.get("webChannel") else [],
            poster_url=image.get("original", "") or image.get("medium", ""),
            cast=cast,
            crew=crew,
            external_ids={
                "tvmaze": str(show.get("id", "")),
                "imdb": (show.get("externals", {}) or {}).get("imdb", "") or "",
                "tvdb": str((show.get("externals", {}) or {}).get("thetvdb", "") or ""),
            },
            provider=self.id,
        )
        if seasons:
            season_rows = self.http.get_json(f"{BASE}/shows/{external_ref}/seasons", provider=self.id)
            for season_row in season_rows:
                season = SeasonMetadata(
                    season_number=season_row.get("number", 0) or 0,
                    title=season_row.get("name", ""),
                    overview=clean_overview((season_row.get("summary") or "").replace("<p>", "").replace("</p>", "")),
                    air_date=iso_date(season_row.get("premiereDate")),
                    poster_url=((season_row.get("image", {}) or {}).get("original", "")),
                )
                episode_rows = self.http.get_json(
                    f"{BASE}/seasons/{season_row.get('id')}/episodes", provider=self.id
                )
                for ep in episode_rows:
                    season.episodes.append(
                        EpisodeMetadata(
                            episode_number=ep.get("number", 0) or 0,
                            title=ep.get("name", ""),
                            overview=clean_overview((ep.get("summary") or "").replace("<p>", "").replace("</p>", "")),
                            air_date=iso_date(ep.get("airdate")),
                            runtime_seconds=(ep.get("runtime") or 0) * 60 or None,
                            rating=(ep.get("rating", {}) or {}).get("average"),
                            still_url=((ep.get("image", {}) or {}).get("original", "")),
                        )
                    )
                result.seasons.append(season)
        return result
