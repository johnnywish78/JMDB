"""Recommendations screen (local engine, explained honestly)."""
from __future__ import annotations

from PyQt6.QtWidgets import QGridLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from ui.components.states import EmptyState
from ui.screens.base import Screen


class RecommendationsScreen(Screen):
    title = "Recommendations"

    def __init__(self, context, parent=None) -> None:
        super().__init__(context, parent)
        self.header = QLabel("Recommended for you")
        self.header.setObjectName("ScreenTitle")
        self.root.addWidget(self.header)
        explanation = QLabel(
            "Recommendations are computed locally from your genres, favorites, "
            "ratings, watch history, and shared cast/crew. No external service."
        )
        explanation.setObjectName("MutedLabel")
        explanation.setWordWrap(True)
        self.root.addWidget(explanation)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.root.addWidget(self.scroll, 1)
        self.container = QWidget()
        self.grid = QGridLayout(self.container)
        self.grid.setSpacing(12)
        self.scroll.setWidget(self.container)
        self.empty_state = EmptyState(
            "No recommendations yet",
            "Watch or favorite a few things and recommendations will appear here.",
        )
        self.empty_state.setVisible(False)
        self.root.addWidget(self.empty_state)

    def refresh(self) -> None:
        from ui.app.context import run_async

        def work():
            profile = self.context.profile_id
            return (
                self.context.services.recommendations.recommended_movies(profile, 12),
                self.context.services.recommendations.recommended_shows(profile, 12),
            )

        run_async(work, self._populate)

    def _populate(self, result) -> None:
        movies, shows = result
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        rows = []
        for row in movies:
            rows.append((row, "movie"))
        for row in shows:
            rows.append((row, "tv_show"))
        self.empty_state.setVisible(not rows)
        self.scroll.setVisible(bool(rows))
        from ui.components.poster_card import PosterCard

        columns = max(1, (max(500, self.width()) - 60) // 200)
        for index, (row, media_type) in enumerate(rows):
            card = PosterCard(row, width=170)
            card.clicked.connect(
                lambda data, mt=media_type: self._open(mt, data)
            )
            self._load_art(card, row)
            self.grid.addWidget(card, index // columns, index % columns)

    def _load_art(self, card, row: dict) -> None:
        context = self.context

        def handler(key, pixmap, card=card):
            card.set_pixmap(pixmap)
            try:
                context.images.ready.disconnect(handler)
            except TypeError:
                pass

        context.images.ready.connect(handler)
        context.images.request(f"rec-{row['id']}-{id(card)}", row.get("poster_path", ""), 360)

    def _open(self, media_type: str, data: dict) -> None:
        if media_type == "tv_show":
            self.context.router.navigate("show_detail", show_id=data["id"])
        else:
            self.context.router.navigate("movie_detail", movie_id=data["id"])
