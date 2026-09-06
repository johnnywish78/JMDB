"""Provider abstraction: capabilities, health, and normalized result models."""
from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from app.metadata.http_client import HttpClient

logger = logging.getLogger(__name__)


@dataclass
class PersonCredit:
    name: str = ""
    role: str = "crew"  # actor | director | writer | producer | crew | guest_star
    character: str = ""
    job: str = ""
    photo_url: str = ""
    sort_order: int = 0
    tmdb_id: Optional[str] = None
    imdb_id: Optional[str] = None


@dataclass
class EpisodeMetadata:
    episode_number: int = 0
    title: str = ""
    overview: str = ""
    air_date: str = ""
    runtime_seconds: Optional[int] = None
    rating: Optional[float] = None
    still_url: str = ""
    guest_cast: list[PersonCredit] = field(default_factory=list)


@dataclass
class SeasonMetadata:
    season_number: int = 0
    title: str = ""
    overview: str = ""
    air_date: str = ""
    poster_url: str = ""
    episodes: list[EpisodeMetadata] = field(default_factory=list)


@dataclass
class MovieMetadata:
    title: str = ""
    original_title: str = ""
    year: Optional[int] = None
    release_date: str = ""
    runtime_seconds: Optional[int] = None
    overview: str = ""
    tagline: str = ""
    rating: Optional[float] = None
    vote_count: Optional[int] = None
    certification: str = ""
    languages: str = ""
    countries: str = ""
    genres: list[str] = field(default_factory=list)
    studios: list[str] = field(default_factory=list)
    collection: str = ""
    trailer_url: str = ""
    poster_url: str = ""
    backdrop_url: str = ""
    logo_url: str = ""
    cast: list[PersonCredit] = field(default_factory=list)
    crew: list[PersonCredit] = field(default_factory=list)
    external_ids: dict[str, str] = field(default_factory=dict)
    provider: str = ""


@dataclass
class ShowMetadata:
    title: str = ""
    original_title: str = ""
    first_air_date: str = ""
    last_air_date: str = ""
    status: str = ""
    overview: str = ""
    rating: Optional[float] = None
    vote_count: Optional[int] = None
    genres: list[str] = field(default_factory=list)
    networks: list[str] = field(default_factory=list)
    studios: list[str] = field(default_factory=list)
    poster_url: str = ""
    backdrop_url: str = ""
    logo_url: str = ""
    cast: list[PersonCredit] = field(default_factory=list)
    crew: list[PersonCredit] = field(default_factory=list)
    seasons: list[SeasonMetadata] = field(default_factory=list)
    external_ids: dict[str, str] = field(default_factory=dict)
    provider: str = ""


@dataclass
class ArtistMetadata:
    name: str = ""
    sort_name: str = ""
    biography: str = ""
    disambiguation: str = ""
    genres: list[str] = field(default_factory=list)
    photo_url: str = ""
    banner_url: str = ""
    external_ids: dict[str, str] = field(default_factory=dict)
    provider: str = ""


@dataclass
class AlbumMetadata:
    title: str = ""
    artist: str = ""
    year: Optional[int] = None
    release_date: str = ""
    genres: list[str] = field(default_factory=list)
    cover_url: str = ""
    track_count: int = 0
    external_ids: dict[str, str] = field(default_factory=dict)
    provider: str = ""


@dataclass
class PersonMetadata:
    name: str = ""
    biography: str = ""
    birthday: str = ""
    deathday: str = ""
    place_of_birth: str = ""
    photo_url: str = ""
    external_ids: dict[str, str] = field(default_factory=dict)
    provider: str = ""


class ProviderUnavailable(Exception):
    """Raised when a provider legitimately cannot serve a request
    (missing API key, no public API, cooldown after failures)."""


class MetadataProvider(ABC):
    """Base class for all metadata providers.

    Providers are pure infrastructure: they know HTTP and their API, never
    the database or the UI.
    """

    id = "base"
    display_name = "Base"
    requires_key = False
    key_provider_name = ""  # secrets store key when requires_key
    capabilities = {"movie", "tv", "person", "artist", "album"}
    # MediaBrainz etc. must not hammer their API: min seconds between calls
    min_request_interval = 0.0

    def __init__(self, http: HttpClient, api_key: str = "") -> None:
        self.http = http
        self.api_key = api_key
        self._consecutive_failures = 0
        self._cooldown_until = 0.0
        self._last_error = ""

    # -- lifecycle ---------------------------------------------------------
    def is_configured(self) -> bool:
        return not self.requires_key or bool(self.api_key)

    def in_cooldown(self) -> bool:
        return time.monotonic() < self._cooldown_until

    def health(self) -> dict:
        return {
            "id": self.id,
            "name": self.display_name,
            "configured": self.is_configured(),
            "available": self.is_configured() and not self.in_cooldown(),
            "cooldown": self.in_cooldown(),
            "consecutive_failures": self._consecutive_failures,
            "last_error": self._last_error,
        }

    def record_success(self) -> None:
        self._consecutive_failures = 0
        self._cooldown_until = 0.0
        self._last_error = ""

    def record_failure(self, error: str, cooldown_seconds: float = 60.0) -> None:
        self._consecutive_failures += 1
        self._last_error = error[:200]
        if self._consecutive_failures >= 3:
            self._cooldown_until = time.monotonic() + cooldown_seconds * min(self._consecutive_failures, 5)

    def _require_key(self) -> str:
        if self.requires_key and not self.api_key:
            raise ProviderUnavailable(
                f"{self.display_name} requires an API key (configure it in Settings)"
            )
        return self.api_key

    # -- capability probes ------------------------------------------------------
    def supports(self, capability: str) -> bool:
        return capability in self.capabilities

    # -- data methods (override what the provider supports) ------------------------
    def search_movie(self, title: str, year: int | None = None) -> list[MovieMetadata]:
        return []

    def movie_details(self, external_ref: str) -> MovieMetadata | None:
        return None

    def search_show(self, title: str) -> list[ShowMetadata]:
        return []

    def show_details(self, external_ref: str, seasons: bool = True) -> ShowMetadata | None:
        return None

    def search_artist(self, name: str) -> list[ArtistMetadata]:
        return []

    def artist_details(self, external_ref: str) -> ArtistMetadata | None:
        return None

    def search_album(self, artist: str, album: str) -> list[AlbumMetadata]:
        return []

    def person_details(self, external_ref: str) -> PersonMetadata | None:
        return None

    def find_person(self, name: str) -> list[PersonMetadata]:
        return []
