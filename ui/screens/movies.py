"""Movies library screen: filters + lazy grid."""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ui.screens.base import GridScreen


class MoviesScreen(GridScreen):
    title = "Movies"
    empty_hint = "Movies appear here after you scan a library folder."
    empty_action_text = "Open library settings"

    def __init__(self, context, parent=None) -> None:
        super().__init__(context, parent)
        self.empty_state.action.connect(
            lambda: self.context.router.navigate("settings")
        )
        self.empty_state.setVisible(False)

        filters = QHBoxLayout()
        filters.setSpacing(8)
        self.sort_box = QComboBox()
        self.sort_box.addItems(["Sort: Title", "Sort: Year", "Sort: Rating", "Sort: Recently added"])
        self.sort_box.currentIndexChanged.connect(self._on_filter)
        self.genre_box = QComboBox()
        self.genre_box.addItem("All genres")
        self.genre_box.currentIndexChanged.connect(self._on_filter)
        self.view_box = QComboBox()
        self.view_box.addItems(["All", "Unwatched", "Watched", "Favorites", "Watchlist"])
        self.view_box.currentIndexChanged.connect(self._on_filter)
        self.year_box = QComboBox()
        self.year_box.addItem("Any year")
        for decade in range(2020, 1940, -10):
            self.year_box.addItem(f"{decade}s", decade)
        self.year_box.currentIndexChanged.connect(self._on_filter)
        self.count_label = QLabel("")
        self.count_label.setObjectName("MutedLabel")
        filters.addWidget(self.sort_box)
        filters.addWidget(self.genre_box)
        filters.addWidget(self.view_box)
        filters.addWidget(self.year_box)
        filters.addStretch(1)
        filters.addWidget(self.count_label)
        self.root.insertLayout(1, filters)

        self.card_clicked.connect(self._open_movie)

    def refresh(self) -> None:
        self._load_genres()
        super().refresh()

    def _load_genres(self) -> None:
        current = self.genre_box.currentText()
        self.genre_box.blockSignals(True)
        self.genre_box.clear()
        self.genre_box.addItem("All genres")
        for genre in self.context.services.search.all_genres():
            self.genre_box.addItem(genre)
        if current:
            index = self.genre_box.findText(current)
            if index >= 0:
                self.genre_box.setCurrentIndex(index)
        self.genre_box.blockSignals(False)

    def _on_filter(self) -> None:
        self.refresh()

    def _filters(self) -> dict:
        sort = ["title", "year", "rating", "added"][self.sort_box.currentIndex()]
        view = self.view_box.currentIndex()
        year = self.year_box.currentData()
        genre = self.genre_box.currentText()
        return {
            "sort": sort,
            "genre": "" if genre == "All genres" else genre,
            "year_from": year if year else None,
            "year_to": year + 9 if year else None,
            "unwatched_only": view == 1,
            "watched_only": view == 2,
            "favorites_only": view == 3,
            "watchlist_only": view == 4,
        }

    def fetch_page(self, page: int, per_page: int) -> tuple[list[dict], int]:
        return self.context.services.movies.list_page(
            self.context.profile_id, page=page, per_page=per_page, **self._filters()
        )

    def _append_cards(self, rows: list[dict]) -> None:
        super()._append_cards(rows)
        total = self._total if self._total >= 0 else len(self._rows)
        self.count_label.setText(f"{len(self._rows)} of {total} movies")

    def _open_movie(self, row: dict) -> None:
        self.context.router.navigate("movie_detail", movie_id=row["id"])
