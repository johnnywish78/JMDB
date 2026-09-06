"""Statistics screen: real numbers from the database."""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ui.components.detail_body import _section_title
from ui.screens.base import Screen


class StatCard(QWidget):
    def __init__(self, value: str, label: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("StatCard")
        layout = QVBoxLayout(self)
        value_label = QLabel(value)
        value_label.setObjectName("BigValue")
        layout.addWidget(value_label)
        name_label = QLabel(label)
        name_label.setObjectName("MutedLabel")
        layout.addWidget(name_label)


class BarList(QWidget):
    def __init__(self, entries: list[tuple[str, int]], parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        max_value = max((value for _name, value in entries), default=1) or 1
        for name, value in entries:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            name_label = QLabel(str(name))
            name_label.setFixedWidth(220)
            row.addWidget(name_label)
            bar = QLabel("█" * max(1, int(value / max_value * 34)))
            bar.setObjectName("MutedLabel")
            row.addWidget(bar, 1)
            count = QLabel(str(value))
            count.setObjectName("MutedLabel")
            row.addWidget(count)
            holder = QWidget()
            holder.setLayout(row)
            layout.addWidget(holder)
        layout.addStretch(1)


def format_hours(seconds: float) -> str:
    hours = seconds / 3600
    if hours >= 100:
        return f"{hours:.0f} h"
    if hours >= 1:
        return f"{hours:.1f} h"
    return f"{int(seconds // 60)} min"


class StatisticsScreen(Screen):
    title = "Statistics"

    def __init__(self, context, parent=None) -> None:
        super().__init__(context, parent)
        self.header = QLabel("Statistics")
        self.header.setObjectName("ScreenTitle")
        self.root.addWidget(self.header)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.root.addWidget(self.scroll, 1)
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setSpacing(18)
        self.scroll.setWidget(self.content)

    def refresh(self) -> None:
        from ui.app.context import run_async

        def work():
            svc = self.context.services
            profile = self.context.profile_id
            return {
                "overview": svc.statistics.overview(profile),
                "genres": svc.statistics.top_genres(10),
                "actors": svc.statistics.top_people("actor", 10),
                "directors": svc.statistics.top_people("director", 10),
                "months": svc.statistics.watch_time_by_month(profile, 12),
            }

        run_async(work, self._populate)

    def _populate(self, data: dict) -> None:
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        overview = data["overview"]

        grid = QGridLayout()
        grid.setSpacing(10)
        cards = [
            (str(overview["movies"]), "Movies"),
            (str(overview["tv_shows"]), "TV shows"),
            (str(overview["seasons"]), "Seasons"),
            (str(overview["episodes"]), "Episodes"),
            (str(overview["watched_movies"]), "Movies watched"),
            (str(overview["watched_episodes"]), "Episodes watched"),
            (format_hours(overview["watch_seconds"]), "Watch time"),
            (str(overview["artists"]), "Artists"),
            (str(overview["albums"]), "Albums"),
            (str(overview["tracks"]), "Tracks"),
            (str(overview["favorite_count"]), "Favorites"),
            (str(overview["watchlist_count"]), "Watchlist"),
            (str(overview["people"]), "People indexed"),
            (str(overview["files"]), "Media files"),
            (str(overview["artwork_cached"]), "Artwork cached"),
            (str(overview["missing_files"]), "Missing files"),
        ]
        for index, (value, label) in enumerate(cards):
            grid.addWidget(StatCard(value, label), index // 4, index % 4)
        holder = QWidget()
        holder.setLayout(grid)
        self.content_layout.addWidget(holder)

        if data["genres"]:
            self.content_layout.addWidget(_section_title("Top genres"))
            self.content_layout.addWidget(BarList(data["genres"]))
        if data["actors"]:
            self.content_layout.addWidget(_section_title("Top actors in library"))
            self.content_layout.addWidget(BarList(data["actors"]))
        if data["directors"]:
            self.content_layout.addWidget(_section_title("Top directors in library"))
            self.content_layout.addWidget(BarList(data["directors"]))
        if data["months"]:
            self.content_layout.addWidget(_section_title("Watch time by month (hours)"))
            self.content_layout.addWidget(
                BarList([(month, round(hours / 3600, 1)) for month, hours in data["months"]])
            )
        self.content_layout.addStretch(1)
