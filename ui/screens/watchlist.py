"""Watchlist screen."""
from __future__ import annotations

from PyQt6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget

from ui.components.states import EmptyState
from ui.screens.base import Screen


class WatchlistScreen(Screen):
    title = "Watchlist"

    def __init__(self, context, parent=None) -> None:
        super().__init__(context, parent)
        self.header = QLabel("Watchlist")
        self.header.setObjectName("ScreenTitle")
        self.root.addWidget(self.header)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.root.addWidget(self.scroll, 1)
        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setSpacing(12)
        self.scroll.setWidget(self.container)
        self.empty_state = EmptyState(
            "Watchlist is empty",
            "Add movies and shows to your watchlist with the ＋ button.",
        )
        self.empty_state.setVisible(False)
        self.root.addWidget(self.empty_state)

    def refresh(self) -> None:
        from ui.app.context import run_async

        def work():
            return self.context.services.repos.lists.watchlist(self.context.profile_id)

        run_async(work, self._populate)

    def _populate(self, rows: list[dict]) -> None:
        while self.container_layout.count():
            item = self.container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.empty_state.setVisible(not rows)
        self.scroll.setVisible(bool(rows))
        self.header.setText(f"Watchlist ({len(rows)})")

        from PyQt6.QtWidgets import QGridLayout
        from ui.components.poster_card import PosterCard

        grid = QGridLayout()
        grid.setSpacing(12)
        columns = max(1, (max(500, self.width()) - 60) // 200)
        for index, row in enumerate(rows):
            card = PosterCard(row, width=170)
            card.clicked.connect(self._open_item)
            self._load_art(card, row)
            grid.addWidget(card, index // columns, index % columns)
        holder = QWidget()
        holder.setLayout(grid)
        self.container_layout.addWidget(holder)
        self.container_layout.addStretch(1)

    def _load_art(self, card, row: dict) -> None:
        context = self.context

        def handler(key, pixmap, card=card):
            card.set_pixmap(pixmap)
            try:
                context.images.ready.disconnect(handler)
            except TypeError:
                pass

        context.images.ready.connect(handler)
        context.images.request(f"wl-{row.get('media_type')}-{row.get('media_id')}-{id(card)}",
                               row.get("poster_path", ""), 360)

    def _open_item(self, row: dict) -> None:
        router = self.context.router
        if row.get("media_type") == "tv_show":
            router.navigate("show_detail", show_id=row["media_id"])
        else:
            router.navigate("movie_detail", movie_id=row["media_id"])
