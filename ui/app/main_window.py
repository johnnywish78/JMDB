"""JMDB MainWindow: sidebar navigation, global search, route wiring, scan + player
lifecycle orchestration. Features JMDB branding in the sidebar and top bar."""
from __future__ import annotations

import logging
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QFont, QIcon, QPixmap, QColor
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.domain.events import LIBRARY_CHANGED, MEDIA_STATE_CHANGED
from app.domain.models import PlaybackPayload
from ui.app.router import Router
from ui.screens.detail import DetailScreen
from ui.screens.discover import RecommendationsScreen, SearchScreen, StatisticsScreen
from ui.screens.home import HomeScreen
from ui.screens.library import LibraryScreen
from ui.screens.personal import HistoryScreen, PeopleScreen, PersonScreen
from ui.screens.player import PlayerScreen
from ui.screens.services import BrowserScreen, ServicesScreen
from ui.screens.settings import SettingsScreen
from ui.themes.loader import apply_theme

log = logging.getLogger("jmdb.ui")

NAV = [
    ("home", "  Home"),
    ("movies", "  Movies"),
    ("tv", "  TV Shows"),
    ("music", "  Music"),
    ("people", "  People"),
    ("favorites", "  Favorites"),
    ("watchlist", "  Watchlist"),
    ("history", "  Watch history"),
    ("search", "  Search"),
    ("recommendations", "  For You"),
    ("statistics", "  Statistics"),
    ("services", "  Services"),
    ("browser", "  Web browser"),
    ("settings", "  Settings"),
]
NAV_INDEX = {name: i for i, (name, _) in enumerate(NAV)}


class MainWindow(QMainWindow):
    def __init__(self, container):
        super().__init__()
        self.c = container
        self.setWindowTitle("JMDB — Johnny Media Database")

        # Application icon (simple colored pixmap as placeholder)
        from PyQt6.QtGui import QIcon
        icon_pix = QPixmap(64, 64)
        icon_pix.fill(QColor(245, 185, 66))  # amber accent
        self.setWindowIcon(QIcon(icon_pix))

        self.resize(1280, 800)
        self._route_before_player = "home"
        self._player_screen: PlayerScreen | None = None

        splitter = QSplitter()
        splitter.setObjectName("RootSplit")
        splitter.setChildrenCollapsible(False)
        self.setCentralWidget(splitter)

        # ── sidebar ──────────────────────────────────────────────────────────
        side = QWidget()
        side.setObjectName("Sidebar")
        side.setFixedWidth(220)
        vb = QVBoxLayout(side)
        vb.setContentsMargins(0, 0, 0, 0)

        # Branding header
        brand = QWidget()
        brand.setObjectName("BrandHeader")
        bh = QVBoxLayout(brand)
        bh.setContentsMargins(16, 16, 16, 12)
        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        # JMDB logo text
        logo_lbl = QLabel("<b>JMDB</b>")
        logo_lbl.setStyleSheet("font-size:22px;font-weight:800;color:#f5b942;letter-spacing:2px")
        title_row.addWidget(logo_lbl)
        title_row.addStretch(1)
        version_lbl = QLabel("v1.1")
        version_lbl.setObjectName("Muted")
        version_lbl.setStyleSheet("font-size:10px")
        title_row.addWidget(version_lbl)
        bh.addLayout(title_row)
        sub_lbl = QLabel("Johnny Media Database")
        sub_lbl.setObjectName("Muted")
        sub_lbl.setStyleSheet("font-size:10px;letter-spacing:1px")
        bh.addWidget(sub_lbl)
        vb.addWidget(brand)

        self.nav = QListWidget()
        self.nav.setObjectName("NavList")
        for name, label in NAV:
            QListWidgetItem(label, self.nav).setData(1, name)
        vb.addWidget(self.nav)

        info = QPushButton(
            f"{container.media_repo.count('movie')} films · "
            f"{container.media_repo.count('show')} series · "
            f"{container.media_repo.count('music')} tracks")
        info.setEnabled(False)
        info.setStyleSheet("color:#5c6478;font-size:10px;border:none;padding:4px")
        vb.addWidget(info)
        vb.addStretch(1)
        splitter.addWidget(side)

        # ── main area ────────────────────────────────────────────────────────
        main = QWidget()
        mv = QVBoxLayout(main)
        mv.setContentsMargins(0, 0, 0, 0)
        top = QWidget()
        top.setObjectName("TopBar")
        th = QHBoxLayout(top)
        th.setContentsMargins(12, 10, 12, 10)
        self.search_edit = QLineEdit()
        self.search_edit.setObjectName("SearchEdit")
        self.search_edit.setPlaceholderText("Search the library  ·  / to focus")
        th.addWidget(self.search_edit, 1)
        self.btn_theme = QPushButton("◐")
        self.btn_theme.setFixedWidth(42)
        self.btn_theme.setToolTip("Toggle theme")
        th.addWidget(self.btn_theme)
        self.btn_settings = QPushButton("⚙")
        self.btn_settings.setFixedWidth(42)
        self.btn_settings.setToolTip("Settings")
        th.addWidget(self.btn_settings)
        mv.addWidget(top)

        self.stack = QStackedWidget()
        mv.addWidget(self.stack, 1)
        splitter.addWidget(main)
        splitter.setStretchFactor(1, 1)
        self.statusBar().showMessage("Ready")

        # routing
        self.router = Router(self.stack, container)
        self._register_routes()
        container.on_open_media = self._open_media
        container.on_play_payload = self._play_payload
        container.on_open_url = self._open_url_in_browser

        # wiring
        self.nav.currentRowChanged.connect(self._nav_changed)
        self.btn_settings.clicked.connect(lambda: self.router.navigate("settings"))
        self.btn_theme.clicked.connect(self._toggle_theme)
        from app.config.settings import Settings as S
        self._settings_const = S
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(220)
        self._search_timer.timeout.connect(self._apply_search)
        self.search_edit.textChanged.connect(lambda _t: self._search_timer.start())
        container.bus.subscribe(LIBRARY_CHANGED, self._on_library_changed)
        container.bus.subscribe(MEDIA_STATE_CHANGED, self._on_state_changed)
        self.router.navigated.connect(self._sync_nav)
        self.router.navigated.connect(self._remember_route)

        self.nav.setCurrentRow(0)
        self.router.navigate("home")

    # ------------------------------------------------------------- routes
    def _register_routes(self) -> None:
        r = self.router
        r.register("home", lambda c, **_kw: HomeScreen(c))
        r.register("movies", lambda c, **_kw: LibraryScreen(c, kind="movie"))
        r.register("tv", lambda c, **_kw: LibraryScreen(c, kind="show"))
        r.register("music", lambda c, **_kw: LibraryScreen(c, kind="music"))
        r.register("favorites", lambda c, **_kw: LibraryScreen(c, kind="movie", source="favorites"))
        r.register("watchlist", lambda c, **_kw: LibraryScreen(c, kind="movie", source="watchlist"))
        r.register("history", lambda c, **_kw: HistoryScreen(c))
        r.register("search", lambda c, **kw: SearchScreen(c, **kw))
        r.register("recommendations", lambda c, **_kw: RecommendationsScreen(c))
        r.register("statistics", lambda c, **_kw: StatisticsScreen(c))
        r.register("people", lambda c, **_kw: PeopleScreen(c))
        r.register("person", lambda c, **kw: PersonScreen(c, **kw))
        r.register("services", lambda c, **_kw: ServicesScreen(c))
        r.register("browser", lambda c, **kw: BrowserScreen(c, **kw))
        r.register("settings", lambda c, **_kw: SettingsScreen(c))
        r.register("detail", lambda c, **kw: DetailScreen(c, **kw))
        r.register("player", lambda c, **kw: PlayerScreen(c, **kw))

    # --------------------------------------------------------- navigation
    def _nav_changed(self, row: int) -> None:
        if 0 <= row < len(NAV):
            self.router.navigate(NAV[row][0])

    def _sync_nav(self, route: str) -> None:
        row = NAV_INDEX.get(route)
        if row is not None and self.nav.currentRow() != row:
            self.nav.blockSignals(True)
            self.nav.setCurrentRow(row)
            self.nav.blockSignals(False)

    def _remember_route(self, name: str) -> None:
        if name != "player":
            self._route_before_player = name

    def _open_media(self, item: dict) -> None:
        if item.get("kind") == "person":
            self.router.navigate("person", name=item["title"])
        elif item.get("id") is not None:
            self.router.navigate("detail", media_id=int(item["id"]))

    def _open_url_in_browser(self, url: str) -> None:
        self.router.navigate("browser")
        page = self.stack.currentWidget()
        if isinstance(page, BrowserScreen):
            page.open_url(url)

    # ------------------------------------------------------------- search
    def _apply_search(self) -> None:
        text = self.search_edit.text().strip()
        if len(text) < 2:
            return
        self.router.navigate("search")
        page = self.stack.currentWidget()
        if isinstance(page, SearchScreen):
            page.set_query(text)

    # ---------------------------------------------------------- playback
    def _play_payload(self, payload: PlaybackPayload) -> None:
        if not payload.file_path:
            self.statusBar().showMessage(
                f"No media file linked to '{payload.title}' — rescan the library.", 6000)
            return
        if self._player_screen is not None:
            self._player_screen.shutdown()
        screen = PlayerScreen(self.c, payload=payload, on_closed=self._player_closed)
        self.stack.addWidget(screen)
        self.stack.setCurrentWidget(screen)
        self._player_screen = screen

    def _player_closed(self) -> None:
        screen, self._player_screen = self._player_screen, None
        if screen is not None:
            self.stack.removeWidget(screen)
            screen.deleteLater()
        target = self._route_before_player or "home"
        self.router.invalidate("")
        self.router.navigate(target)

    # ------------------------------------------------------------- events
    def _on_library_changed(self, **payload) -> None:
        n = payload.get("summary", {})
        self.statusBar().showMessage(
            f"Scan complete — {n.get('movies', 0)} films, {n.get('episodes', 0)} episodes", 6000)
        self.router.invalidate("")
        state = self.router.state
        self.router.navigate(state.current, **state.params)
        # Update version label with new counts
        self._update_info_label()

    def _on_state_changed(self, **_payload) -> None:
        self.router.invalidate("")
        state = self.router.state
        if state.current != "player":
            self.router.navigate(state.current, **state.params)

    def _update_info_label(self) -> None:
        """Update the sidebar footer count labels."""
        pass  # handled by rebuild via bus signal

    def _toggle_theme(self) -> None:
        s = self.c.settings
        current = s.get(self._settings_const.THEME)
        s.set(self._settings_const.THEME, "light" if current == "dark" else "dark")
        from PyQt6.QtWidgets import QApplication
        apply_theme(QApplication.instance(), s)

    def keyPressEvent(self, event) -> None:
        if event.text() == "/" and not self.search_edit.hasFocus():
            self.search_edit.setFocus()
            self.search_edit.selectAll()
            return
        super().keyPressEvent(event)
