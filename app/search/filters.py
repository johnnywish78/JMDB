"""Search filters."""
from __future__ import annotations

from dataclasses import dataclass, field

ALL_TYPES = {"movie", "tv_show", "episode", "person", "artist", "album", "track", "collection"}


@dataclass
class SearchFilter:
    types: set[str] = field(default_factory=lambda: set(ALL_TYPES))
    genre: str = ""
    year_from: int | None = None
    year_to: int | None = None
    min_rating: float | None = None
    favorites_only: bool = False
    watchlist_only: bool = False
    unwatched_only: bool = False
    watched_only: bool = False
