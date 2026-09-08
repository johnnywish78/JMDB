"""Library grid: movies / series / music / favorites / watchlist with sort + genre filter."""
from __future__ import annotations

from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from ui.components.cards import MediaCard
from ui.components.common import EmptyState, FlowLayout, SectionHeader

SORTS = [("rating", "Top rated"), ("title", "Title A–Z"), ("newest", "Newest"), ("added", "Recently added")]


class LibraryScreen(QWidget):
    """params: kind='movie'|'show'|'music', source=None|'favorites'|'watchlist'"""

    def __init__(self, container, kind: str = "movie", source: str | None = None, parent=None):
        super().__init__(parent)
        self.c = container
        self.kind = kind
        self.source = source
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 8, 16, 16)

        title_map = {"movie": "Movies", "show": "TV Shows", "music": "Music"}
        title = title_map.get(kind, "Library")
        if source:
            title = source.capitalize()
        root.addWidget(SectionHeader(title, "indexed by the library scanner"))

        bar = QHBoxLayout()
        if not source:
            self.sort_box = QComboBox()
            for key, label in SORTS:
                self.sort_box.addItem(label, key)
            bar.addWidget(QLabel("Sort:"))
            bar.addWidget(self.sort_box)
            self.genre_box = QComboBox()
            self.genre_box.addItem("All genres", None)
            for g in self.c.media_repo.distinct_genres(kind):
                self.genre_box.addItem(g, g)
            bar.addWidget(self.genre_box)
            self.sort_box.currentIndexChanged.connect(lambda _i: self.rebuild())
            self.genre_box.currentIndexChanged.connect(lambda _i: self.rebuild())
        self.count_lbl = QLabel("")
        self.count_lbl.setObjectName("Muted")
        bar.addStretch(1)
        bar.addWidget(self.count_lbl)
        root.addLayout(bar)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        root.addWidget(self.scroll, 1)
        self.rebuild()

    def on_show(self) -> None:
        self.rebuild()

    def rebuild(self) -> None:
        if self.source == "favorites":
            ids = self.c.state_repo.favorites()
            items = self.c.media_repo.by_ids(sorted(ids))
            items = [it for it in items if it.get("kind") == self.kind]
        elif self.source == "watchlist":
            ids = self.c.state_repo.watchlist()
            items = self.c.media_repo.by_ids(sorted(ids))
            items = [it for it in items if it.get("kind") == self.kind]
        else:
            sort = self.sort_box.currentData()
            genre = self.genre_box.currentData()
            items = self.c.media_repo.list(self.kind, sort=sort or "rating", genre=genre)
        self.count_lbl.setText(f"{len(items)} items")

        body = QWidget()
        flow = FlowLayout(body, h_spacing=12, v_spacing=12)
        if not items:
            self.scroll.setWidget(EmptyState(
                "Nothing here yet",
                "Add library folders in Settings and run a scan, or come back after marking titles."))
            return
        for item in items:
            card = MediaCard(self.c, item)
            card.openRequested.connect(self.c.open_media)
            card.playRequested.connect(self._play)
            flow.addWidget(card)
        self.scroll.setWidget(body)

    def _play(self, item: dict) -> None:
        if item.get("kind") == "show":
            ep = self.c.episode_repo.next_unwatched(item["id"])
            if not ep:
                self.c.open_media(item)
                return
            payload = self.c.playback.payload_episode(item, ep)
        else:
            payload = self.c.playback.payload_movie(item)
        if self.c.on_play_payload:
            self.c.on_play_payload(payload)
