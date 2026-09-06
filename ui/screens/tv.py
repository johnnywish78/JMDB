"""TV shows library screen."""
from __future__ import annotations

from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QLabel

from ui.screens.base import GridScreen


class TvScreen(GridScreen):
    title = "TV Shows"
    empty_hint = "TV shows appear here after a scan finds episode files."
    empty_action_text = "Open library settings"

    def __init__(self, context, parent=None) -> None:
        super().__init__(context, parent)
        self.empty_state.action.connect(lambda: self.context.router.navigate("settings"))
        self.empty_state.setVisible(False)

        filters = QHBoxLayout()
        self.sort_box = QComboBox()
        self.sort_box.addItems(["Sort: Title", "Sort: Recently added", "Sort: Rating"])
        self.sort_box.currentIndexChanged.connect(lambda _i: self.refresh())
        self.genre_box = QComboBox()
        self.genre_box.addItem("All genres")
        self.genre_box.currentIndexChanged.connect(lambda _i: self.refresh())
        self.view_box = QComboBox()
        self.view_box.addItems(["All", "Unwatched", "Favorites", "Watchlist"])
        self.view_box.currentIndexChanged.connect(lambda _i: self.refresh())
        self.count_label = QLabel("")
        self.count_label.setObjectName("MutedLabel")
        filters.addWidget(self.sort_box)
        filters.addWidget(self.genre_box)
        filters.addWidget(self.view_box)
        filters.addStretch(1)
        filters.addWidget(self.count_label)
        self.root.insertLayout(1, filters)
        self.card_clicked.connect(self._open_show)

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

    def fetch_page(self, page: int, per_page: int) -> tuple[list[dict], int]:
        sort = ["title", "added", "rating"][self.sort_box.currentIndex()]
        view = self.view_box.currentIndex()
        genre = self.genre_box.currentText()
        return self.context.services.tv.list_shows(
            self.context.profile_id,
            page=page,
            per_page=per_page,
            sort=sort,
            genre="" if genre == "All genres" else genre,
            unwatched_only=view == 1,
            favorites_only=view == 2,
            watchlist_only=view == 3,
        )

    def _append_cards(self, rows: list[dict]) -> None:
        super()._append_cards(rows)
        total = self._total if self._total >= 0 else len(self._rows)
        self.count_label.setText(f"{len(self._rows)} of {total} shows")

    def _open_show(self, row: dict) -> None:
        self.context.router.navigate("show_detail", show_id=row["id"])
