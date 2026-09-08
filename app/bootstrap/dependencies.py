"""Dependency container: builds the object graph once, in strict layer order."""
from __future__ import annotations

from app.config.paths import AppPaths
from app.config.secrets import env
from app.config.settings import Settings
from app.database.connection import Database
from app.database.migrations import migrate
from app.database.repositories import (
    BookmarkRepository,
    EpisodeRepository,
    HistoryRepository,
    LibraryStateRepository,
    MediaRepository,
    PeopleRepository,
    ProgressRepository,
)
from app.domain.events import EventBus
from app.metadata.artwork import ArtworkStore
from app.metadata.cache import MetadataCache
from app.metadata.manager import MetadataManager
from app.recommendations.engine import RecommendationEngine
from app.search.engine import SearchEngine
from app.services.service_manager import ServiceManager
from app.statistics.service import StatisticsService


class Container:
    """Owns shared services. Shared with screens; closed on shutdown."""

    def __init__(self) -> None:
        self.paths = AppPaths().ensure()
        self.settings = Settings(self.paths.settings_path)
        self.bus = EventBus()

        self.db = Database(self.paths.db_path)
        self.db.connect()
        self.schema_version = migrate(self.db)

        self.media_repo = MediaRepository(self.db)
        self.episode_repo = EpisodeRepository(self.db)
        self.people_repo = PeopleRepository(self.db)
        self.state_repo = LibraryStateRepository(self.db)
        self.progress_repo = ProgressRepository(self.db)
        self.history_repo = HistoryRepository(self.db)
        self.bookmarks = BookmarkRepository(self.db)

        # metadata chain (keys from settings, env overrides)
        self.cache = MetadataCache(self.db)
        self.artwork = ArtworkStore(self.paths)
        self.metadata = MetadataManager(
            cache=self.cache,
            tmdb_key=env("TMDB_API_KEY") or self.settings.get(Settings.TMDB_API_KEY),
            omdb_key=env("OMDB_API_KEY") or self.settings.get(Settings.OMDB_API_KEY),
        )

        self.search = SearchEngine(self.db)
        self.reco = RecommendationEngine(self.db, self.episode_repo)
        self.stats = StatisticsService(self.db)
        self.services = ServiceManager(self.settings)

        from app.playback.service import PlaybackService

        self.playback = PlaybackService(
            self.state_repo, self.episode_repo, self.progress_repo,
            self.history_repo, self.settings, self.bus)

        # navigation hooks — MainWindow assigns router-bound callables here
        self.on_open_media = None   # (item: dict) -> None
        self.on_play_payload = None  # (payload: PlaybackPayload) -> None
        self.on_open_url = None      # (url: str) -> None

    def open_media(self, item: dict) -> None:
        if self.on_open_media:
            self.on_open_media(item)

    def close(self) -> None:
        self.db.close()
