"""Home dashboard: hero, continue watching, and real content rows."""
from __future__ import annotations

import logging
import random

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.domain.events import (
    ArtworkUpdated,
    LibraryScanFinished,
    MetadataUpdated,
)
from ui.components.states import EmptyState, SectionHeader
from ui.components.poster_card import PosterCard
from ui.screens.base import Screen

logger = logging.getLogger(__name__)


class Row(QWidget):
    item_opened = pyqtSignal(dict)

    def __init__(self, title: str, more_route: str = "", parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 6)
        layout.setSpacing(8)
        header = SectionHeader(title, more_route)
        layout.addWidget(header)
        self.scroller = QScrollArea()
        self.scroller.setWidgetResizable(True)
        self.scroller.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroller.setFixedHeight(int(1.5 * 0 + 330))
        self.scroller.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroller.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        row_widget = QWidget()
        self.row_layout = QHBoxLayout(row_widget)
        self.row_layout.setContentsMargins(0, 0, 0, 0)
        self.row_layout.setSpacing(12)
        self.row_layout.addStretch(1)
        self.scroller.setWidget(row_widget)
        layout.addWidget(self.scroller)

    def set_items(self, rows: list[dict], show_progress: bool = False) -> None:
        while self.row_layout.count() > 1:
            item = self.row_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not rows:
            self.hide()
            return
        self.show()
        for row in rows:
            card = PosterCard(row, width=158, show_progress=show_progress)
            card.clicked.connect(self.item_opened.emit)
            self._load_art(card, row)
            self.row_layout.insertWidget(self.row_layout.count() - 1, card)

    def _load_art(self, card: PosterCard, row: dict) -> None:
        path = row.get("poster_path") or row.get("still_path") or row.get("cover_path") or ""
        key = f"home-{row.get('media_type', '')}-{row.get('id')}-{id(card)}"

        def handler(delivered_key, pixmap, card=card):
            if delivered_key == key:
                card.set_pixmap(pixmap)
                try:
                    self.window().context.images.ready.disconnect(handler)
                except (TypeError, AttributeError):
                    pass

        try:
            self.window().context.images.ready.connect(handler)
            self.window().context.images.request(key, path, 340)
        except AttributeError:
            pass


class Hero(QWidget):
    open_requested = pyqtSignal(dict)
    play_requested = pyqtSignal(dict)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("HeroBackdrop")
        self.setFixedHeight(360)
        self.setStyleSheet("border-radius: 14px;")
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)

        self.backdrop_label = QLabel()
        self.backdrop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.backdrop_label.setStyleSheet("border-radius: 14px; background: #1a1f2a;")
        self._layout.addWidget(self.backdrop_label)

        self.info = QWidget()
        info_layout = QVBoxLayout(self.info)
        info_layout.setContentsMargins(28, 24, 28, 24)
        info_layout.addStretch(1)
        self.title_label = QLabel("")
        self.title_label.setObjectName("HeroTitle")
        self.title_label.setWordWrap(True)
        info_layout.addWidget(self.title_label)
        self.meta_label = QLabel("")
        self.meta_label.setObjectName("HeroTagline")
        self.meta_label.setWordWrap(True)
        info_layout.addWidget(self.meta_label)
        buttons = QHBoxLayout()
        self.play_button = QPushButton("  ▶  Play")
        self.play_button.setObjectName("PlayButton")
        self.play_button.clicked.connect(lambda: self.play_requested.emit(self.data))
        self.details_button = QPushButton("Details")
        self.details_button.clicked.connect(lambda: self.open_requested.emit(self.data))
        buttons.addWidget(self.play_button)
        buttons.addWidget(self.details_button)
        buttons.addStretch(1)
        info_layout.addLayout(buttons)
        info_layout.addStretch(1)
        self.info.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.data: dict = {}

    def set_item(self, row: dict, backdrop_path: str, subtitle: str) -> None:
        self.data = row
        self.title_label.setText(str(row.get("title", "")))
        self.meta_label.setText(subtitle)
        self.play_button.setEnabled(True)
        if backdrop_path:
            key = f"hero-{row.get('id')}-{row.get('media_type', '')}"

            def handler(delivered_key, pixmap):
                if delivered_key == key:
                    from PyQt6.QtCore import Qt

                    self.backdrop_label.setPixmap(
                        pixmap.scaled(
                            self.backdrop_label.size(),
                            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                    )

            context = getattr(self.window(), "context", None)
            if context is not None:
                context.images.ready.connect(handler)
                context.images.request(key, backdrop_path, 1200)


class HomeScreen(Screen):
    title = "Home"

    def __init__(self, context, parent=None) -> None:
        super().__init__(context, parent)
        self.hero = Hero()
        self.root.addWidget(self.hero)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.root.addWidget(self.scroll, 1)
        self.rows_container = QWidget()
        self.rows_layout = QVBoxLayout(self.rows_container)
        self.rows_layout.setSpacing(18)
        self.rows_layout.addStretch(1)
        self.scroll.setWidget(self.rows_container)

        self.empty_state = EmptyState(
            "Welcome to JMDB",
            "Add a folder with your movies, TV shows, or music to get started.",
            "Add library folder",
        )
        self.empty_state.action.connect(lambda: self.context.router.navigate("settings"))
        self.empty_state.setVisible(False)
        self.root.addWidget(self.empty_state)

        context.subscribe(LibraryScanFinished, lambda e: self.refresh())
        context.subscribe(MetadataUpdated, lambda e: self.refresh())
        context.subscribe(ArtworkUpdated, lambda e: self.refresh())

    # -- data -------------------------------------------------------------
    def refresh(self) -> None:
        from ui.app.context import run_async

        def work():
            return self._gather()

        run_async(work, self._populate, lambda err: None)

    def _gather(self) -> dict:
        svc = self.context.services
        profile = self.context.profile_id
        data = {
            "continue": svc.playback.resume.continue_watching(profile, 14),
            "movies": svc.movies.recently_added(profile, 14),
            "episodes": svc.repos.tv.recent_episodes(profile, 14),
            "favorites": svc.repos.lists.favorites(profile),
            "watchlist": svc.repos.lists.watchlist(profile),
            "recently_played": svc.playback.history.recently_played(profile, 14),
            "recommendations": svc.recommendations.recommended(profile, 14),
            "albums": svc.repos.music.recent_albums(14),
            "stats": svc.statistics.overview(profile),
            "locations": len(svc.library.locations()),
            "hero_candidates": [],
        }
        # hero candidates: items WITH backdrops (artwork-driven, no hard-coding)
        data["hero_candidates"] = [
            dict(r, media_type="movie")
            for r in svc.repos.db.query(
                "SELECT m.id, m.title, m.overview, m.year, m.rating, 'movie' AS media_type,"
                " (SELECT a.local_path FROM artwork a WHERE a.owner_type='movie' AND a.owner_id=m.id"
                "  AND a.kind='backdrop' AND a.local_path<>'' LIMIT 1) AS backdrop_path"
                " FROM movies m WHERE EXISTS (SELECT 1 FROM artwork a WHERE a.owner_type='movie'"
                "  AND a.owner_id=m.id AND a.kind='backdrop' AND a.local_path<>'')"
                " ORDER BY m.rating DESC LIMIT 12"
            )
        ] + [
            dict(r, media_type="tv_show")
            for r in svc.repos.db.query(
                "SELECT s.id, s.title, s.overview, s.first_air_date, s.rating, 'tv_show' AS media_type,"
                " substr(s.first_air_date,1,4) AS year,"
                " (SELECT a.local_path FROM artwork a WHERE a.owner_type='tv_show' AND a.owner_id=s.id"
                "  AND a.kind='backdrop' AND a.local_path<>'' LIMIT 1) AS backdrop_path"
                " FROM tv_shows s WHERE EXISTS (SELECT 1 FROM artwork a WHERE a.owner_type='tv_show'"
                "  AND a.owner_id=s.id AND a.kind='backdrop' AND a.local_path<>'')"
                " ORDER BY s.rating DESC LIMIT 12"
            )
        ]
        return data

    def _populate(self, data: dict) -> None:
        stats = data["stats"]
        has_library = stats["files"] > 0
        self.empty_state.setVisible(not has_library)
        self.hero.setVisible(has_library)
        self.scroll.setVisible(has_library)

        # hero
        candidates = data["hero_candidates"]
        if candidates:
            hero = random.choice(candidates)
            subtitle_bits = []
            if hero.get("year"):
                subtitle_bits.append(str(hero["year"]))
            if hero.get("rating"):
                subtitle_bits.append(f"★ {hero['rating']:.1f}")
            media_type = hero.get("media_type")
            subtitle_bits.append("TV Series" if media_type == "tv_show" else "Movie")
            self.hero.set_item(hero, hero.get("backdrop_path", ""), " · ".join(subtitle_bits))
            for signal_name, handler in (
                ("open_requested", lambda row, mt=media_type: self._open_detail(mt, row)),
                ("play_requested", lambda row, mt=media_type: self._play(mt, row)),
            ):
                signal = getattr(self.hero, signal_name)
                previous = getattr(self, f"_hero_{signal_name}", None)
                if previous is not None:
                    try:
                        signal.disconnect(previous)
                    except TypeError:
                        pass
                signal.connect(handler)
                setattr(self, f"_hero_{signal_name}", handler)
        elif has_library:
            self.hero.hide()

        # clear previous rows
        while self.rows_layout.count() > 1:
            item = self.rows_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        rows = []
        if data["continue"]:
            rows.append(("Continue Watching", data["continue"], True))
        if data["movies"]:
            rows.append(("Recently Added Movies", data["movies"], False))
        if data["episodes"]:
            rows.append(("New Episodes", data["episodes"], False))
        if data["recently_played"]:
            rows.append(("Recently Played", data["recently_played"], False))
        if data["albums"]:
            rows.append(("New Music", data["albums"], False))
        if data["recommendations"]:
            rows.append(("Recommended for You", data["recommendations"], False))
        if data["favorites"]:
            rows.append(("Favorites", data["favorites"], False))
        if data["watchlist"]:
            rows.append(("Watchlist", data["watchlist"], False))
        for title, items, progress in rows:
            row = Row(title)
            row.item_opened.connect(self._open_item)
            row.set_items(items, show_progress=progress)
            self.rows_layout.insertWidget(self.rows_layout.count() - 1, row)

    # -- navigation actions --------------------------------------------------------
    def _open_item(self, row: dict) -> None:
        media_type = row.get("media_type", "")
        if media_type == "episode":
            self.context.router.navigate("episode_detail", episode_id=row["id"])
        elif media_type == "tv_show":
            self.context.router.navigate("show_detail", show_id=row["id"])
        elif media_type == "album":
            self.context.router.navigate("music_detail", album_id=row["id"])
        elif media_type == "artist":
            self.context.router.navigate("music", query=row.get("title", ""))
        elif media_type == "track":
            self.context.router.navigate("music_detail", album_id=row.get("album_id", 0))
        else:
            self._open_detail(media_type or "movie", row)

    def _open_detail(self, media_type: str, row: dict) -> None:
        if media_type == "tv_show":
            self.context.router.navigate("show_detail", show_id=row["id"])
        else:
            self.context.router.navigate("movie_detail", movie_id=row["id"])

    def _play(self, media_type: str, row: dict) -> None:
        svc = self.context.services
        try:
            if media_type == "tv_show":
                show = svc.tv.show_detail(row["id"], self.context.profile_id)
                if show and show.get("next_episode") and show["next_episode"].get("id"):
                    playable = svc.tv.playable(show["next_episode"]["id"])
                    if playable:
                        self.context.open_player(playable)
                        return
            else:
                playable = svc.movies.playable(row["id"])
                if playable:
                    self.context.open_player(playable)
        except Exception as exc:
            logger.exception("hero play failed")
            self.context.toast(f"Cannot play: {exc}", "error")
