"""Application services: the layer between UI and domain/infrastructure.

The UI talks ONLY to this aggregate. It owns no widgets; every method is
safe to call from any thread (repositories serialize DB access).
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

from app.config.paths import Paths
from app.config.secrets import SecretsStore
from app.config.settings import SettingsService
from app.database.connection import Database
from app.database.repositories import Repositories
from app.domain.events import (
    ArtworkUpdated,
    EventBus,
    LibraryScanFinished,
    MediaAdded,
    MetadataUpdated,
)
from app.domain.models import Profile
from app.library.duplicate_detector import DuplicateDetector
from app.library.filesystem import is_valid_media_root
from app.library.probe import ProbeTools
from app.library.scanner import LibraryScanner, ScanOptions
from app.media.collections import CollectionsService
from app.media.movies import MovieCatalog
from app.media.music import MusicCatalog
from app.media.people import PeopleCatalog
from app.media.tv import TvCatalog
from app.metadata.artwork import ArtworkManager
from app.metadata.cache import MetadataCache
from app.metadata.http_client import HttpClient, RateLimit
from app.metadata.manager import ProviderManager
from app.metadata.providers.apple_itunes import ItunesProvider
from app.metadata.providers.base import MetadataProvider
from app.metadata.providers.fanart import FanartProvider
from app.metadata.providers.lastfm import LastFmProvider
from app.metadata.providers.musicbrainz import MusicBrainzProvider
from app.metadata.providers.omdb import OmdbProvider
from app.metadata.providers.theaudiodb import TheAudioDbProvider
from app.metadata.providers.tmdb import TmdbProvider
from app.metadata.providers.tvmaze import TvMazeProvider
from app.metadata.providers.tvtime import TvTimeProvider
from app.playback.audio import AudioService
from app.playback.service import PlaybackService
from app.playback.subtitles import SubtitleService
from app.recommendations.engine import RecommendationEngine
from app.search.engine import SearchService
from app.search.index import SearchIndex
from app.services.service_manager import ServiceManager, ServiceRegistry
from app.statistics.service import StatisticsService
from app.browser.bookmarks import Bookmarks
from app.browser.downloads import DownloadsManager
from app.browser.history import BrowserHistory

logger = logging.getLogger(__name__)


class MetadataService:
    """Applies provider metadata to the database (merge, never destroy)."""

    def __init__(
        self,
        repos: Repositories,
        events: EventBus,
        manager: ProviderManager,
        artwork: ArtworkManager,
        index: SearchIndex,
    ) -> None:
        self.repos = repos
        self.events = events
        self.manager = manager
        self.artwork = artwork
        self.index = index

    # -- movies ---------------------------------------------------------------
    def enrich_movie(self, movie_id: int, force: bool = False, profile_id: int = 1) -> bool:
        movie = self.repos.movies.get(movie_id)
        if movie is None:
            return False
        if not force and movie.overview:
            return True  # already enriched
        metadata, provider_id = self.manager.resolve_movie(movie.title, movie.year)
        if metadata is None:
            return False

        updates = {}
        for source_field, db_field in (
            ("title", "title"),
            ("original_title", "original_title"),
            ("release_date", "release_date"),
            ("runtime_seconds", "runtime_seconds"),
            ("overview", "overview"),
            ("tagline", "tagline"),
            ("rating", "rating"),
            ("vote_count", "vote_count"),
            ("certification", "certification"),
            ("languages", "languages"),
            ("countries", "countries"),
        ):
            value = getattr(metadata, source_field)
            current = getattr(movie, db_field)
            if value and (current in (None, "", 0) or force):
                if source_field != "title" or force:
                    updates[db_field] = value
        if metadata.title and (not movie.title or force):
            updates["title"] = metadata.title
        if updates:
            self.repos.movies.update(movie_id, updates)

        if metadata.genres:
            self.repos.taxonomy.set_genres("movie", movie_id, metadata.genres)
        if metadata.studios:
            self.repos.taxonomy.set_studios("movie", movie_id, metadata.studios)
        if metadata.cast or metadata.crew:
            self.repos.people.replace_credits(
                "movie", movie_id,
                [c.__dict__ for c in (metadata.cast + metadata.crew)],
            )
            self._enrich_people_photos(metadata.cast + metadata.crew)
        for provider, value in metadata.external_ids.items():
            self.repos.external_ids.set("movie", movie_id, provider, value)
        if metadata.trailer_url:
            self.repos.external_ids.set("movie", movie_id, "trailer", metadata.trailer_url)
        if metadata.collection:
            franchise = self.repos.movies.get_or_create_collection(
                metadata.collection, ""
            )
            self.repos.movies.update(movie_id, {"collection_id": franchise.id})

        artwork_count = 0
        for kind, url in (
            ("poster", metadata.poster_url),
            ("backdrop", metadata.backdrop_url),
            ("logo", metadata.logo_url),
        ):
            if url:
                path = self.artwork.ensure_artwork("movie", movie_id, kind, url)
                if path:
                    artwork_count += 1
                    self.events.publish(
                        ArtworkUpdated(owner_type="movie", owner_id=movie_id, kind=kind)
                    )
        self.repos.metadata_sources.record("movie", movie_id, provider_id)
        self.index.update("movie", movie_id)
        self.events.publish(
            MetadataUpdated(
                media_type="movie", media_id=movie_id,
                provider=provider_id, artwork_downloaded=artwork_count,
            )
        )
        return True

    # -- shows -----------------------------------------------------------------
    def enrich_show(self, show_id: int, force: bool = False) -> bool:
        show = self.repos.tv.get_show(show_id)
        if show is None:
            return False
        if not force and show.overview:
            return True
        metadata, provider_id = self.manager.resolve_show(show.title)
        if metadata is None:
            return False

        updates = {}
        for source_field, db_field in (
            ("title", "title"),
            ("first_air_date", "first_air_date"),
            ("last_air_date", "last_air_date"),
            ("status", "status"),
            ("overview", "overview"),
            ("rating", "rating"),
            ("vote_count", "vote_count"),
        ):
            value = getattr(metadata, source_field)
            current = getattr(show, db_field)
            if value and (current in (None, "", 0) or force):
                if source_field != "title" or force:
                    updates[db_field] = value
        if updates:
            self.repos.tv.update_show(show_id, updates)
        if metadata.genres:
            self.repos.taxonomy.set_genres("tv_show", show_id, metadata.genres)
        if metadata.networks:
            self.repos.taxonomy.set_networks(show_id, metadata.networks)
        if metadata.cast or metadata.crew:
            self.repos.people.replace_credits(
                "tv_show", show_id,
                [c.__dict__ for c in (metadata.cast + metadata.crew)],
            )
            self._enrich_people_photos(metadata.cast + metadata.crew)
        for provider, value in metadata.external_ids.items():
            self.repos.external_ids.set("tv_show", show_id, provider, value)

        for season in metadata.seasons:
            season_id = self.repos.tv.get_or_create_season(show_id, season.season_number)
            season_updates = {}
            if season.title and not self.repos.tv.get_season(season_id).title:
                season_updates["title"] = season.title
            if season.overview:
                season_updates["overview"] = season.overview
            if season.air_date:
                season_updates["air_date"] = season.air_date
            if season_updates:
                self.repos.tv.update_season(season_id, season_updates)
            for episode in season.episodes:
                episode_id, _ = self.repos.tv.get_or_create_episode(
                    show_id, season_id, season.season_number, episode.episode_number
                )
                episode_updates = {}
                existing = self.repos.tv.get_episode(episode_id)
                if episode.title and (not existing.title or force):
                    episode_updates["title"] = episode.title
                if episode.overview and (not existing.overview or force):
                    episode_updates["overview"] = episode.overview
                if episode.air_date and not existing.air_date:
                    episode_updates["air_date"] = episode.air_date
                if episode.runtime_seconds and not existing.runtime_seconds:
                    episode_updates["runtime_seconds"] = episode.runtime_seconds
                if episode.rating is not None and existing.rating is None:
                    episode_updates["rating"] = episode.rating
                if episode_updates:
                    self.repos.tv.update_episode(episode_id, episode_updates)
                if episode.still_url:
                    self.artwork.ensure_artwork(
                        "episode", episode_id, "still", episode.still_url
                    )
                if episode.guest_cast:
                    self.repos.people.replace_credits(
                        "episode", episode_id,
                        [
                            {**c.__dict__, "role": "guest_star"}
                            for c in episode.guest_cast
                        ],
                    )
            if season.poster_url:
                self.artwork.ensure_artwork(
                    "season", season_id, "season_poster", season.poster_url
                )

        artwork_count = 0
        for kind, url in (("poster", metadata.poster_url), ("backdrop", metadata.backdrop_url), ("logo", metadata.logo_url)):
            if url:
                path = self.artwork.ensure_artwork("tv_show", show_id, kind, url)
                if path:
                    artwork_count += 1
        self.repos.metadata_sources.record("tv_show", show_id, provider_id)
        self.index.update("tv_show", show_id)
        self.events.publish(
            MetadataUpdated(
                media_type="tv_show", media_id=show_id,
                provider=provider_id, artwork_downloaded=artwork_count,
            )
        )
        return True

    # -- music ------------------------------------------------------------------
    def enrich_artist(self, artist_id: int, force: bool = False) -> bool:
        artist = self.repos.music.get_artist(artist_id)
        if artist is None:
            return False
        if not force and artist.biography:
            return True
        metadata, provider_id = self.manager.resolve_artist(artist.name)
        if metadata is None:
            return False
        updates = {}
        if metadata.biography and (not artist.biography or force):
            updates["biography"] = metadata.biography
        if metadata.sort_name and not artist.sort_name:
            updates["sort_name"] = metadata.sort_name
        if metadata.disambiguation and not artist.disambiguation:
            updates["disambiguation"] = metadata.disambiguation
        if updates:
            self.repos.music.update_artist(artist_id, updates)
        if metadata.genres:
            self.repos.music.set_artist_genres(artist_id, metadata.genres)
        for provider, value in metadata.external_ids.items():
            self.repos.external_ids.set("artist", artist_id, provider, value)
        artwork_count = 0
        if metadata.photo_url:
            path = self.artwork.ensure_artwork("artist", artist_id, "profile", metadata.photo_url)
            artwork_count += 1 if path else 0
        if metadata.banner_url:
            path = self.artwork.ensure_artwork("artist", artist_id, "artist_banner", metadata.banner_url)
            artwork_count += 1 if path else 0
        self.repos.metadata_sources.record("artist", artist_id, provider_id)
        self.index.update("artist", artist_id)
        self.events.publish(
            MetadataUpdated(media_type="artist", media_id=artist_id,
                            provider=provider_id, artwork_downloaded=artwork_count)
        )
        return True

    def enrich_album(self, album_id: int, force: bool = False) -> bool:
        album = self.repos.music.get_album(album_id)
        if album is None:
            return False
        artist = self.repos.music.get_artist(album.artist_id)
        artist_name = artist.name if artist else ""
        if not force and self.repos.artwork.get("album", album_id, "album_cover"):
            return True
        metadata, provider_id = self.manager.resolve_album(artist_name, album.title)
        if metadata is None:
            return False
        updates = {}
        if metadata.year and not album.year:
            updates["year"] = metadata.year
        if metadata.release_date and not album.release_date:
            updates["release_date"] = metadata.release_date
        if updates:
            self.repos.music.update_album(album_id, updates)
        if metadata.genres:
            self.repos.music.set_album_genres(album_id, metadata.genres)
        for provider, value in metadata.external_ids.items():
            self.repos.external_ids.set("album", album_id, provider, value)
        artwork_count = 0
        if metadata.cover_url:
            path = self.artwork.ensure_artwork("album", album_id, "album_cover", metadata.cover_url)
            artwork_count += 1 if path else 0
        self.repos.metadata_sources.record("album", album_id, provider_id)
        self.index.update("album", album_id)
        self.events.publish(
            MetadataUpdated(media_type="album", media_id=album_id,
                            provider=provider_id, artwork_downloaded=artwork_count)
        )
        return True

    def _enrich_people_photos(self, credits) -> None:
        """Best-effort photo + details for credited people (no failure propagation)."""
        for credit in credits[:15]:
            try:
                if not credit.photo_url:
                    continue
                person = self.repos.people.find_by_name(credit.name)
                if person is None:
                    continue
                existing = self.repos.artwork.get("person", person.id, "profile")
                if existing is None:
                    self.artwork.ensure_artwork(
                        "person", person.id, "profile", credit.photo_url
                    )
            except Exception:
                logger.debug("person photo enrichment failed for %s", credit.name)

    # -- batch ---------------------------------------------------------------------
    def enrich_pending(self, limit: int = 40) -> tuple[int, int]:
        """Enrich items lacking metadata. Returns (processed, succeeded)."""
        processed = succeeded = 0
        for movie_id in self.repos.movies.ids_needing_metadata(limit):
            ok = self.enrich_movie(movie_id)
            processed += 1
            succeeded += 1 if ok else 0
            if processed >= limit:
                return processed, succeeded
        for show_id in [
            r["id"]
            for r in self.repos.db.query(
                "SELECT id FROM tv_shows WHERE overview='' ORDER BY added_at LIMIT ?", (limit,)
            )
        ]:
            ok = self.enrich_show(show_id)
            processed += 1
            succeeded += 1 if ok else 0
            if processed >= limit:
                break
        return processed, succeeded


class LibraryService:
    """Library locations + scanning orchestration (no Qt)."""

    def __init__(
        self,
        repos: Repositories,
        events: EventBus,
        probe_tools: ProbeTools,
        settings: SettingsService,
        index: SearchIndex,
    ) -> None:
        self.repos = repos
        self.db = repos.db
        self.events = events
        self.probe_tools = probe_tools
        self.settings = settings
        self.index = index
        self.scanner = LibraryScanner(
            self.db, repos, events, probe_tools, self._options()
        )
        self.duplicates = DuplicateDetector(repos)

    def _options(self) -> ScanOptions:
        return ScanOptions(
            probe_files=bool(self.settings.get("probe_media_files")),
            checksum_min_mb=int(self.settings.get("duplicate_min_size_mb")),
            include_hidden=bool(self.settings.get("scan_hidden_directories")),
            follow_symlinks=bool(self.settings.get("follow_symlinks")),
        )

    # -- locations ---------------------------------------------------------------
    def add_location(self, path: str, label: str = "") -> tuple[bool, str]:
        expanded = os.path.expanduser(path.strip())
        if not is_valid_media_root(expanded):
            return False, f"Not a readable directory: {expanded}"
        # store the canonical path so "/x/media", "/x/media/" and symlinks
        # to the same folder can never become duplicate library entries
        canonical = os.path.realpath(expanded)
        for existing in self.repos.locations.list():
            try:
                if os.path.realpath(existing.path) == canonical:
                    return False, "This folder is already in your library."
            except OSError:
                continue
        self.repos.locations.add(canonical, label)
        logger.info("library location added: %s", canonical)
        return True, f"Added {canonical}"

    def remove_location(self, location_id: int) -> None:
        self.repos.locations.remove(location_id)

    def locations(self):
        return self.repos.locations.list()

    def location_file_counts(self) -> dict[int, int]:
        return self.repos.locations.file_counts()

    # -- scanning -------------------------------------------------------------------
    def scan_all(self):
        self.scanner.options = self._options()
        counts = self.scanner.scan_all()
        self.index.rebuild()
        return counts

    def scan_location(self, location_id: int):
        self.scanner.options = self._options()
        counts = self.scanner.scan_location(location_id)
        self.index.rebuild()
        return counts

    def pause(self) -> None:
        self.scanner.pause()

    def resume(self) -> None:
        self.scanner.resume()

    def cancel(self) -> None:
        self.scanner.cancel()

    @property
    def scanning(self) -> bool:
        return False  # coordinator (UI) tracks thread liveness

    def library_summary(self) -> dict:
        return {
            "movies": self.repos.movies.count(),
            "shows": self.repos.tv.count_shows(),
            "episodes": self.repos.tv.count_episodes(),
            "artists": self.repos.music.count_artists(),
            "albums": self.repos.music.count_albums(),
            "tracks": self.repos.music.count_tracks(),
            "files": self.repos.files.count(),
            "missing": self.repos.files.count(missing=True),
        }


@dataclass
class AppServices:
    """Everything the UI needs, wired and ready."""

    paths: Paths
    settings: SettingsService
    secrets: SecretsStore
    events: EventBus
    db: Database
    repos: Repositories
    profile: Profile
    http: HttpClient
    providers: dict[str, MetadataProvider]
    provider_manager: ProviderManager
    metadata: MetadataService
    library: LibraryService
    movies: MovieCatalog
    tv: TvCatalog
    music: MusicCatalog
    people: PeopleCatalog
    collections: CollectionsService
    playback: PlaybackService
    search: SearchService
    search_index: SearchIndex
    statistics: StatisticsService
    recommendations: RecommendationEngine
    artwork: ArtworkManager
    browser_history: BrowserHistory
    bookmarks: Bookmarks
    downloads_manager: DownloadsManager
    service_manager: ServiceManager
    subtitles: SubtitleService
    audio: AudioService

    def diagnostics(self) -> dict:
        from app.browser.engine import detect_system_browsers, webengine_available
        from app.playback.service import _load_backends

        webengine_ok, webengine_reason = webengine_available()
        return {
            "python": _python_version(),
            "pyqt6": _pyqt_version(),
            "webengine": "available" if webengine_ok else f"unavailable ({webengine_reason})",
            "database_path": str(self.paths.database_file),
            "database_version": _db_version(self.db),
            "playback_backends": {
                backend_id: {
                    "available": info["available"],
                    "reason": info["reason"],
                }
                for backend_id, info in self.playback.backend_availability().items()
            },
            "browsers": [
                {"key": b.key, "name": b.name, "path": b.path, "drm": b.drm_capable}
                for b in detect_system_browsers()
            ],
            "probe_tools": self.library.probe_tools.describe(),
            "providers": self.provider_manager.health_report(),
            "library_locations": [
                {"path": loc.path, "status": loc.last_scan_status}
                for loc in self.library.locations()
            ],
            "library_summary": self.library.library_summary(),
        }


def _python_version() -> str:
    import platform

    return platform.python_version()


def _pyqt_version() -> str:
    try:
        from PyQt6.QtCore import QT_VERSION_STR, PYQT_VERSION_STR

        return f"Qt {QT_VERSION_STR} / PyQt6 {PYQT_VERSION_STR}"
    except Exception:
        return "PyQt6 not importable"


def _db_version(db: Database) -> int:
    from app.database.migrations import current_version

    return current_version(db)


def build_services(
    paths: Paths,
    settings: SettingsService,
    secrets: SecretsStore,
    events: EventBus,
    db: Database,
    repos: Repositories,
    profile: Profile,
) -> AppServices:
    """Dependency wiring (the composition root)."""

    # HTTP + providers
    rate_limits = {}
    provider_specs = [
        (TmdbProvider, 0.25),
        (OmdbProvider, 0.25),
        (TvMazeProvider, 0.3),
        (ItunesProvider, 0.5),
        (MusicBrainzProvider, 1.1),
        (LastFmProvider, 0.25),
        (TheAudioDbProvider, 0.5),
        (FanartProvider, 0.5),
    ]
    providers: dict[str, MetadataProvider] = {}
    for cls, interval in provider_specs:
        if interval:
            rate_limits[cls.id] = RateLimit(min_interval=interval)
    http = HttpClient(
        timeout=float(settings.get("metadata_timeout_seconds")),
        retries=int(settings.get("metadata_retries")),
        rate_limits=rate_limits,
    )
    for cls, _ in provider_specs:
        key = secrets.get(cls.key_provider_name) if cls.key_provider_name else ""
        try:
            providers[cls.id] = cls(http, api_key=key)
        except Exception as exc:
            logger.warning("provider %s failed to initialize: %s", cls.id, exc)
    providers["tvtime"] = TvTimeProvider(http)

    cache = MetadataCache(repos.metadata_cache, ttl_days=int(settings.get("metadata_cache_days")))
    manager = ProviderManager(
        list(providers.values()),
        repos,
        events,
        cache,
        priority=list(settings.get("provider_priority")),
        music_priority=list(settings.get("music_provider_priority")),
    )

    artwork = ArtworkManager(paths, repos, http, quality=str(settings.get("artwork_quality")))
    index = SearchIndex(db)

    metadata = MetadataService(repos, events, manager, artwork, index)
    probe_tools = ProbeTools()
    library = LibraryService(repos, events, probe_tools, settings, index)

    playback = PlaybackService(repos, settings, events)
    search = SearchService(repos, index)
    stats = StatisticsService(repos)
    recs = RecommendationEngine(repos)
    registry = ServiceRegistry()
    service_manager = ServiceManager(
        registry, repos, preferred_browser=str(settings.get("browser_external"))
    )

    downloads_manager = DownloadsManager(paths, repos, events)

    services = AppServices(
        paths=paths,
        settings=settings,
        secrets=secrets,
        events=events,
        db=db,
        repos=repos,
        profile=profile,
        http=http,
        providers=providers,
        provider_manager=manager,
        metadata=metadata,
        library=library,
        movies=MovieCatalog(repos),
        tv=TvCatalog(repos),
        music=MusicCatalog(repos),
        people=PeopleCatalog(repos),
        collections=CollectionsService(repos, events),
        playback=playback,
        search=search,
        search_index=index,
        statistics=stats,
        recommendations=recs,
        artwork=artwork,
        browser_history=BrowserHistory(repos),
        bookmarks=Bookmarks(repos),
        downloads_manager=downloads_manager,
        service_manager=service_manager,
        subtitles=SubtitleService(repos),
        audio=AudioService(repos),
    )

    # keep artwork quality / provider order in sync with settings changes
    def on_setting_change(key: str, _old, new) -> None:
        if key == "artwork_quality":
            artwork.set_quality(str(new))
        elif key == "provider_priority":
            manager.set_priority(list(new))
        elif key == "music_provider_priority":
            manager.set_priority(list(new), music=True)
        elif key == "browser_external":
            service_manager.set_preferred_browser(str(new))

    settings.on_change(on_setting_change)
    return services
