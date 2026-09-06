"""JMDB main window: sidebar + topbar + routed screens + player."""
from __future__ import annotations

import logging

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import QHBoxLayout, QMainWindow, QWidget

from app.domain.events import (
    LibraryScanFinished,
    LibraryScanProgress,
    LibraryScanStarted,
    PlaybackFinished,
    SettingsChanged,
    ThemeChanged,
    ToastRequested,
)
from app.services_app.coordinator import AppServices
from ui.app.context import UIContext
from ui.app.router import Router
from ui.app.state import AppState
from ui.components.notifications import ToastManager
from ui.components.sidebar import Sidebar
from ui.components.topbar import Topbar
from ui.player.player_window import PlayerWindow
from ui.themes.system import ThemeManager

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self, services: AppServices, theme_manager: ThemeManager) -> None:
        super().__init__()
        self.services = services
        self.themes = theme_manager
        self.state = AppState()
        self.setWindowTitle("JMDB — Johnny Media Database")
        self.resize(1440, 900)
        self.toast_manager = ToastManager(self)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.sidebar = Sidebar()
        layout.addWidget(self.sidebar)

        right = QWidget()
        right_layout = QHBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        self.topbar = Topbar()
        self.router = Router(lambda: self.context)
        self.context = UIContext(
            services=services,
            bridge=self._make_bridge(),
            router=self.router,
            theme_manager=theme_manager,
            player_factory=self.open_player,
        )
        right_layout.addWidget(self.topbar, 0)
        right_layout.addWidget(self.router, 1)
        layout.addWidget(right, 1)

        self._player_window: PlayerWindow | None = None

        self._register_routes()
        self._connect_signals()
        self._install_shortcuts()

        # default screen
        startup = str(services.settings.get("startup_screen"))
        self.navigate_to(startup if self.router.has_route(startup) else "home")

    # -- wiring -----------------------------------------------------------------
    def _make_bridge(self):
        from ui.app.context import EventBridge

        return EventBridge(self.services.events)

    def _register_routes(self) -> None:
        from ui.screens.browser import BrowserScreen
        from ui.screens.collections import CollectionsScreen
        from ui.screens.episode_detail import EpisodeDetailScreen
        from ui.screens.favorites import FavoritesScreen
        from ui.screens.history import HistoryScreen
        from ui.screens.home import HomeScreen
        from ui.screens.movie_detail import MovieDetailScreen
        from ui.screens.movies import MoviesScreen
        from ui.screens.music import MusicScreen
        from ui.screens.music_detail import AlbumDetailScreen
        from ui.screens.people import PeopleScreen
        from ui.screens.person_detail import PersonDetailScreen
        from ui.screens.recommendations import RecommendationsScreen
        from ui.screens.search import SearchScreen
        from ui.screens.season_detail import SeasonDetailScreen
        from ui.screens.services import ServicesScreen
        from ui.screens.settings import SettingsScreen
        from ui.screens.show_detail import ShowDetailScreen
        from ui.screens.statistics import StatisticsScreen
        from ui.screens.tv import TvScreen
        from ui.screens.watchlist import WatchlistScreen

        factories = {
            "home": HomeScreen,
            "movies": MoviesScreen,
            "movie_detail": MovieDetailScreen,
            "tv": TvScreen,
            "show_detail": ShowDetailScreen,
            "season_detail": SeasonDetailScreen,
            "episode_detail": EpisodeDetailScreen,
            "music": MusicScreen,
            "music_detail": AlbumDetailScreen,
            "people": PeopleScreen,
            "person_detail": PersonDetailScreen,
            "collections": CollectionsScreen,
            "favorites": FavoritesScreen,
            "watchlist": WatchlistScreen,
            "history": HistoryScreen,
            "search": SearchScreen,
            "recommendations": RecommendationsScreen,
            "statistics": StatisticsScreen,
            "browser": BrowserScreen,
            "services": ServicesScreen,
            "settings": SettingsScreen,
        }
        for route, factory in factories.items():
            self.router.register(route, factory)
        logger.info("routes registered: %d", len(factories))

    def _connect_signals(self) -> None:
        self.sidebar.navigate_requested.connect(self.navigate_to)
        self.topbar.search_requested.connect(
            lambda text: self.navigate_to("search", query=text)
        )
        self.topbar.theme_toggled.connect(self._toggle_theme)
        self.router.currentChanged.connect(self._sync_sidebar)

        context = self.context
        context.subscribe(ToastRequested, self._on_toast)
        context.subscribe(LibraryScanStarted, lambda e: None)
        context.subscribe(LibraryScanProgress, lambda e: None)
        context.subscribe(LibraryScanFinished, self._on_scan_finished)
        context.subscribe(ThemeChanged, lambda e: self.topbar.set_theme_icon(e.theme))
        context.subscribe(PlaybackFinished, self._on_playback_finished)
        context.subscribe(SettingsChanged, self._on_settings_changed)
        self.topbar.set_theme_icon(self.themes.effective_theme())

    def _install_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+K"), self, activated=self._focus_search)
        QShortcut(QKeySequence("Ctrl+1"), self, activated=lambda: self.navigate_to("home"))
        QShortcut(QKeySequence("Ctrl+2"), self, activated=lambda: self.navigate_to("movies"))
        QShortcut(QKeySequence("Ctrl+3"), self, activated=lambda: self.navigate_to("tv"))
        QShortcut(QKeySequence("Ctrl+4"), self, activated=lambda: self.navigate_to("music"))
        QShortcut(QKeySequence("Ctrl+,"), self, activated=lambda: self.navigate_to("settings"))
        QShortcut(QKeySequence("F11"), self, activated=self._toggle_theme)

    # -- navigation -----------------------------------------------------------------
    def navigate_to(self, route: str, **params) -> None:
        try:
            self.router.navigate(route, **params)
        except Exception:
            logger.exception("navigation failed for %s", route)
            self.toast_manager.show(f"Cannot open '{route}'", "error")

    def _sync_sidebar(self) -> None:
        self.sidebar.set_active(self.router.current_route())

    def _focus_search(self) -> None:
        self.navigate_to("search")
        screen = self.router._screens.get("search")
        if screen is not None:
            screen.focus_search()

    # -- theming -----------------------------------------------------------------------
    def _toggle_theme(self) -> None:
        current = self.themes.effective_theme()
        self.themes.set_theme("light" if current == "dark" else "dark")

    # -- events --------------------------------------------------------------------------
    def _on_toast(self, event: ToastRequested) -> None:
        if event.level == "info" and not self.services.settings.get("notify_scan"):
            return
        self.toast_manager.show(event.message, event.level, int(self.services.settings.get("toast_duration_ms")))

    def _on_scan_finished(self, event: LibraryScanFinished) -> None:
        if event.status == "completed":
            message = (
                f"Scan finished: {event.files_seen} files, {event.movies_added} movies, "
                f"{event.shows_added} shows, {event.episodes_added} episodes"
            )
            level = "success" if event.errors == 0 else "warning"
        else:
            message = f"Scan {event.status}: {event.message or ''}".strip()
            level = "warning"
        if self.services.settings.get("notify_scan"):
            self.toast_manager.show(message, level, int(self.services.settings.get("toast_duration_ms")))
        current = self.router.current_route()
        if current in ("home", "movies", "tv", "music", "statistics", "collections"):
            screen = self.router._screens.get(current)
            if screen is not None:
                screen.refresh()

    def _on_playback_finished(self, event: PlaybackFinished) -> None:
        current = self.router.current_route()
        if current in ("home", "history", "tv", "show_detail", "season_detail"):
            screen = self.router._screens.get(current)
            if screen is not None:
                screen.refresh()

    def _on_settings_changed(self, event: SettingsChanged) -> None:
        if event.key == "theme":
            self.themes.apply()

    # -- player -----------------------------------------------------------------------------
    def open_player(self, playable, queue=None) -> None:
        from app.playback.controller import PlaybackController

        if self._player_window is None:
            self._player_window = PlayerWindow(self.context, self)
        if self.context.playback_controller is None:
            self.context.playback_controller = PlaybackController(
                self.services.playback, self.services.settings, self
            )
        self.state.player_open = True
        self._player_window.play(playable, queue)
        self._player_window.show()
        self._player_window.raise_()

    def close_player(self) -> None:
        if self._player_window is not None:
            self._player_window.close()
        self.state.player_open = False

    # -- shutdown ------------------------------------------------------------------------------
    def closeEvent(self, event) -> None:
        if self._player_window is not None:
            try:
                self._player_window.close()
            except Exception:
                pass
        if self.context.playback_controller is not None:
            try:
                self.context.playback_controller.stop()
            except Exception:
                pass
        self.context.bridge.shutdown()
        super().closeEvent(event)
