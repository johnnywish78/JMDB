"""Application UI state (selection memory, transient filters)."""
from __future__ import annotations


class AppState:
    """Transient, non-persistent UI state (not a data source of truth)."""

    def __init__(self) -> None:
        self.last_movie_filters: dict = {}
        self.last_show_filters: dict = {}
        self.last_search_query: str = ""
        self.selected_collection_id: int | None = None
        self.player_open: bool = False
