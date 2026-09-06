"""Global search screen: instant search + filters + grouped results."""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.search.filters import ALL_TYPES, SearchFilter
from ui.components.search_bar import SearchBar
from ui.components.states import EmptyState
from ui.screens.base import Screen

TYPE_LABELS = {
    "movie": "Movies",
    "tv_show": "TV Shows",
    "episode": "Episodes",
    "person": "People",
    "artist": "Artists",
    "album": "Albums",
    "track": "Tracks",
    "collection": "Collections",
}


class SearchScreen(Screen):
    title = "Search"

    def __init__(self, context, parent=None) -> None:
        super().__init__(context, parent)
        self.header = QLabel("Search")
        self.header.setObjectName("ScreenTitle")
        self.root.addWidget(self.header)
        self.search_bar = SearchBar("Search movies, TV, episodes, people, music…")
        self.root.addWidget(self.search_bar)
        self.search_bar.query_changed.connect(lambda _q: self.refresh())
        self.search_bar.submitted.connect(lambda _q: self.refresh())

        # filter panel
        filter_row = QHBoxLayout()
        self.type_checks: dict[str, QCheckBox] = {}
        for type_key in sorted(ALL_TYPES):
            check = QCheckBox(TYPE_LABELS[type_key])
            check.setChecked(True)
            check.toggled.connect(lambda _on: self.refresh())
            self.type_checks[type_key] = check
            filter_row.addWidget(check)
        filter_row.addStretch(1)
        self.genre_box = QComboBox()
        self.genre_box.addItem("All genres")
        self.genre_box.currentIndexChanged.connect(lambda _i: self.refresh())
        filter_row.addWidget(self.genre_box)
        self.year_from_box = QComboBox()
        self.year_from_box.addItem("From year")
        for year in range(2030, 1930, -1):
            self.year_from_box.addItem(str(year), year)
        self.year_from_box.currentIndexChanged.connect(lambda _i: self.refresh())
        self.year_to_box = QComboBox()
        self.year_to_box.addItem("To year")
        for year in range(2030, 1930, -1):
            self.year_to_box.addItem(str(year), year)
        self.year_to_box.currentIndexChanged.connect(lambda _i: self.refresh())
        filter_row.addWidget(self.year_from_box)
        filter_row.addWidget(self.year_to_box)
        self.min_rating_box = QComboBox()
        self.min_rating_box.addItem("Any rating")
        for rating in range(1, 10):
            self.min_rating_box.addItem(f"★ {rating}+", float(rating))
        self.min_rating_box.currentIndexChanged.connect(lambda _i: self.refresh())
        filter_row.addWidget(self.min_rating_box)
        self.unwatched_only = QCheckBox("Unwatched")
        self.unwatched_only.toggled.connect(lambda _on: self.refresh())
        self.favorites_only = QCheckBox("Favorites")
        self.favorites_only.toggled.connect(lambda _on: self.refresh())
        filter_row.addWidget(self.unwatched_only)
        filter_row.addWidget(self.favorites_only)
        self.root.addLayout(filter_row)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.root.addWidget(self.scroll, 1)
        self.results_container = QWidget()
        self.results_layout = QVBoxLayout(self.results_container)
        self.results_layout.setSpacing(16)
        self.scroll.setWidget(self.results_container)
        self.empty_state = EmptyState(
            "Start typing to search your library",
            "Search across movies, shows, episodes, people, albums, tracks, and collections.",
        )
        self.root.addWidget(self.empty_state)
        self._last_query = ""

    def focus_search(self) -> None:
        self.search_bar.entry.setFocus()

    def hideEvent(self, event) -> None:
        # stop the pending debounce when navigating away: no stale queries
        # fire against a screen the user has left
        self.search_bar._debounce.stop()
        super().hideEvent(event)

    def enter(self, query: str = "", **params) -> None:
        if query:
            self.search_bar.set_text(query)
            self._last_query = query

    def refresh(self) -> None:
        query = self.search_bar.text()
        self._last_query = query
        if not query:
            self._set_results({})
            return
        genres = self.context.services.search.all_genres()
        if self.genre_box.count() - 1 != len(genres):
            self.genre_box.blockSignals(True)
            self.genre_box.clear()
            self.genre_box.addItem("All genres")
            for genre in genres:
                self.genre_box.addItem(genre)
            self.genre_box.blockSignals(False)

        def work():
            filters = SearchFilter(
                types={t for t, check in self.type_checks.items() if check.isChecked()},
                genre="" if self.genre_box.currentIndex() <= 0 else self.genre_box.currentText(),
                year_from=self.year_from_box.currentData(),
                year_to=self.year_to_box.currentData(),
                min_rating=self.min_rating_box.currentData(),
                unwatched_only=self.unwatched_only.isChecked(),
                favorites_only=self.favorites_only.isChecked(),
            )
            return self.context.services.search.search(
                query, filters, self.context.profile_id
            )

        from ui.app.context import run_async

        run_async(work, self._set_results)

    def _set_results(self, results: dict) -> None:
        while self.results_layout.count():
            item = self.results_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        query = self._last_query
        if not query:
            self.empty_state.setVisible(True)
            self.empty_state.findChildren(QLabel)[1].setText(
                "Search across movies, shows, episodes, people, albums, tracks, and collections."
            )
            self.scroll.setVisible(False)
            return
        self.empty_state.setVisible(not results)
        self.scroll.setVisible(bool(results))
        from ui.components.detail_body import _section_title
        from ui.components.media_card import MediaCard

        total = sum(len(rows) for rows in results.values())
        header = _section_title(f"Results for “{query}” ({total})")
        self.results_layout.addWidget(header)
        for type_key in ("movie", "tv_show", "episode", "person", "artist", "album", "track", "collection"):
            rows = results.get(type_key)
            if not rows:
                continue
            self.results_layout.addWidget(_section_title(TYPE_LABELS[type_key]))
            grid_holder = QWidget()
            grid = QGridLayout(grid_holder)
            grid.setSpacing(8)
            for index, row in enumerate(rows):
                subtitle = ""
                if type_key == "episode":
                    subtitle = f"{row.get('show_title', '')} · S{row.get('season_number')}E{row.get('episode_number')}"
                elif type_key in ("album", "artist", "track"):
                    subtitle = row.get("show_title", "") or ""
                else:
                    subtitle = str(row.get("year") or "")
                card = MediaCard(row.get("title", ""), subtitle)
                card.clicked.connect(
                    lambda _=None, r=row, t=type_key: self._open_result(t, r)
                )
                self._load_art(card, row)
                grid.addWidget(card, index // 2, index % 2)
            self.results_layout.addWidget(grid_holder)
        self.results_layout.addStretch(1)

    def _load_art(self, card, row: dict) -> None:
        context = self.context

        def handler(key, pixmap, card=card):
            card.set_cover_pixmap(pixmap)
            try:
                context.images.ready.disconnect(handler)
            except TypeError:
                pass

        context.images.ready.connect(handler)
        context.images.request(
            f"search-{row.get('id')}-{id(card)}", row.get("poster_path", ""), 160
        )

    def _open_result(self, type_key: str, row: dict) -> None:
        router = self.context.router
        if type_key == "movie":
            router.navigate("movie_detail", movie_id=row["id"])
        elif type_key == "tv_show":
            router.navigate("show_detail", show_id=row["id"])
        elif type_key == "episode":
            router.navigate("episode_detail", episode_id=row["id"])
        elif type_key == "person":
            router.navigate("person_detail", person_id=row["id"])
        elif type_key == "album":
            router.navigate("music_detail", album_id=row["id"])
        elif type_key == "artist":
            router.navigate("music")
        elif type_key == "collection":
            router.navigate("collections")
