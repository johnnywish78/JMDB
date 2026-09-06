"""Provider manager: priority, fallback, caching, health, partial results.

Chain example for movies: TMDB → OMDb → iTunes → (give up, keep local data).
A failing provider never destroys good metadata: errors are recorded, the
provider enters a cooldown after repeated failures, and the next provider
in line gets a chance.
"""
from __future__ import annotations

import logging

from app.database.repositories import Repositories
from app.domain.events import EventBus, ProviderHealthChanged
from app.metadata.cache import MetadataCache
from app.metadata.normalization import match_confidence, normalize_title
from app.metadata.providers.base import (
    AlbumMetadata,
    ArtistMetadata,
    MetadataProvider,
    MovieMetadata,
    PersonMetadata,
    ProviderUnavailable,
    ShowMetadata,
)

logger = logging.getLogger(__name__)

MIN_CONFIDENCE = 0.55


class ProviderManager:
    def __init__(
        self,
        providers: list[MetadataProvider],
        repos: Repositories,
        events: EventBus,
        cache: MetadataCache,
        priority: list[str] | None = None,
        music_priority: list[str] | None = None,
    ) -> None:
        self.providers = {p.id: p for p in providers}
        self.repos = repos
        self.events = events
        self.cache = cache
        self.priority = priority or ["tmdb", "omdb", "tvmaze", "itunes"]
        self.music_priority = music_priority or ["musicbrainz", "theaudiodb", "lastfm"]

    # -- chains ------------------------------------------------------------
    def _chain(self, capability: str, music: bool = False) -> list[MetadataProvider]:
        order = self.music_priority if music else self.priority
        chain = [self.providers[p] for p in order if p in self.providers]
        chain += [p for p in self.providers.values() if p not in chain]
        return [p for p in chain if p.supports(capability) and p.is_configured()]

    def set_priority(self, priority: list[str], music: bool = False) -> None:
        if music:
            self.music_priority = priority
        else:
            self.priority = priority

    # -- movie resolution ------------------------------------------------------
    def resolve_movie(self, title: str, year: int | None) -> tuple[MovieMetadata | None, str]:
        """Search → pick best match → fetch details. Returns (metadata, provider_id)."""
        cache_key = f"{normalize_title(title)}:{year or ''}"
        for provider in self._chain("movie"):
            cached = self.cache.get(provider.id, "movie:full", cache_key)
            if cached:
                return MovieMetadata(**cached), provider.id
            try:
                results = provider.search_movie(title, year)
                best, confidence = None, 0.0
                for result in results:
                    score = match_confidence(title, result.title, year, result.year)
                    if score > confidence:
                        best, confidence = result, score
                if best is None or confidence < MIN_CONFIDENCE:
                    continue
                details = best
                ref = best.external_ids.get(provider.id) or best.external_ids.get("imdb")
                if ref and provider.id == "tmdb":
                    fetched = provider.movie_details(ref)
                    if fetched:
                        details = fetched
                elif provider.id == "omdb" and best.external_ids.get("imdb"):
                    fetched = provider.detail_by_imdb_id(best.external_ids["imdb"])
                    if fetched:
                        details = fetched
                provider.record_success()
                self.cache.put(provider.id, "movie:full", cache_key, details.__dict__)
                return details, provider.id
            except ProviderUnavailable:
                continue
            except Exception as exc:
                self._record_provider_error(provider, exc)
                continue
        return None, ""

    # -- show resolution -----------------------------------------------------------
    def resolve_show(self, title: str, with_seasons: bool = True) -> tuple[ShowMetadata | None, str]:
        cache_key = normalize_title(title)
        for provider in self._chain("tv"):
            cached = self.cache.get(provider.id, "tv:full", cache_key)
            if cached:
                return ShowMetadata(**cached), provider.id
            try:
                results = provider.search_show(title)
                best, confidence = None, 0.0
                for result in results:
                    score = match_confidence(title, result.title)
                    if score > confidence:
                        best, confidence = result, score
                if best is None or confidence < MIN_CONFIDENCE:
                    continue
                details = best
                ref = best.external_ids.get(provider.id)
                if ref and with_seasons:
                    fetched = provider.show_details(ref)
                    if fetched:
                        details = fetched
                provider.record_success()
                self.cache.put(provider.id, "tv:full", cache_key, details.__dict__)
                return details, provider.id
            except ProviderUnavailable:
                continue
            except Exception as exc:
                self._record_provider_error(provider, exc)
                continue
        return None, ""

    def refresh_show(self, external_provider: str, external_ref: str) -> ShowMetadata | None:
        provider = self.providers.get(external_provider)
        if provider is None or not provider.is_configured():
            return None
        try:
            return provider.show_details(external_ref, seasons=True)
        except Exception as exc:
            self._record_provider_error(provider, exc)
            return None

    # -- people --------------------------------------------------------------------
    def resolve_person(self, name: str) -> PersonMetadata | None:
        for provider in self._chain("person"):
            try:
                matches = provider.find_person(name)
                best, confidence = None, 0.0
                for match in matches:
                    score = match_confidence(name, match.name)
                    if score > confidence:
                        best, confidence = match, score
                if best is None or confidence < 0.85:
                    continue
                ref = best.external_ids.get(provider.id)
                details = provider.person_details(ref) if ref else None
                provider.record_success()
                return details or best
            except ProviderUnavailable:
                continue
            except Exception as exc:
                self._record_provider_error(provider, exc)
                continue
        return None

    # -- music -------------------------------------------------------------------------
    def resolve_artist(self, name: str) -> tuple[ArtistMetadata | None, str]:
        for provider in self._chain("artist", music=True):
            try:
                matches = provider.search_artist(name)
                best, confidence = None, 0.0
                for match in matches:
                    score = match_confidence(name, match.name)
                    if score > confidence:
                        best, confidence = match, score
                if best is None or confidence < MIN_CONFIDENCE:
                    continue
                ref = best.external_ids.get(provider.id)
                details = provider.artist_details(ref) if ref else None
                provider.record_success()
                return (details or best), provider.id
            except ProviderUnavailable:
                continue
            except Exception as exc:
                self._record_provider_error(provider, exc)
                continue
        return None, ""

    def resolve_album(self, artist: str, album: str) -> tuple[AlbumMetadata | None, str]:
        for provider in self._chain("album", music=True):
            try:
                matches = provider.search_album(artist, album)
                best, confidence = None, 0.0
                for match in matches:
                    score = match_confidence(f"{artist} {album}", f"{match.artist} {match.title}")
                    if score > confidence:
                        best, confidence = match, score
                if best is None or confidence < 0.45:
                    continue
                provider.record_success()
                return best, provider.id
            except ProviderUnavailable:
                continue
            except Exception as exc:
                self._record_provider_error(provider, exc)
                continue
        return None, ""

    # -- health -------------------------------------------------------------------
    def _record_provider_error(self, provider: MetadataProvider, exc: Exception) -> None:
        message = str(exc)
        provider.record_failure(message)
        logger.warning("provider %s failed: %s", provider.id, message)
        if provider.in_cooldown():
            self.events.publish(
                ProviderHealthChanged(
                    provider=provider.id, healthy=False, message=message
                )
            )

    def health_report(self) -> list[dict]:
        return [p.health() for p in self.providers.values()]

    def provider_status_summary(self) -> dict[str, dict]:
        return {p.id: p.health() for p in self.providers.values()}
