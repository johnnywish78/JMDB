"""Home screen: continue watching, trending, recently added, recommendations."""
from __future__ import annotations

from PyQt6.QtWidgets import QScrollArea, QVBoxLayout, QWidget

from app.domain.enums import parse_media_key
from ui.components.cards import MediaCard
from ui.components.common import FlowLayout, SectionHeader


class HomeScreen(QWidget):
    def __init__(self, container, parent=None):
        super().__init__(parent)
        self.c = container
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 8, 16, 16)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        outer.addWidget(self.scroll)
        self.body = QWidget()
        self.scroll.setWidget(self.body)
        self.lay = QVBoxLayout(self.body)
        self.lay.setSpacing(4)
        self.rebuild()

    def on_show(self) -> None:
        self.rebuild()

    # ------------------------------------------------------------------ rows
    def rebuild(self) -> None:
        while self.lay.count():
            item = self.lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._continue_row()
        self._grid_row("Trending films", self.c.media_repo.list("movie", "rating", limit=10))
        self._grid_row("Recently added", self.c.media_repo.list("movie", "added", limit=10)
                       + self.c.media_repo.list("show", "added", limit=6), mixed=True)
        self._grid_row("Recommended for you", self.c.reco.for_you(10))
        self.lay.addStretch(1)

    def _continue_row(self) -> None:
        items: list[tuple[dict, str]] = []
        for row in self.c.progress_repo.in_progress():
            parsed = parse_media_key(row["media_key"])
            if not parsed:
                continue
            kind, ref = parsed
            if kind == "m":
                media = self.c.media_repo.get(ref)
                if media:
                    items.append((media, f"resume {(row['position_s'] // 60)} min"))
            else:
                ep = self.c.episode_repo.get(ref)
                if ep:
                    show = self.c.media_repo.get(ep["show_id"])
                    if show:
                        items.append((show, f"S{ep['season']} E{ep['number']} · resume {row['position_s'] // 60} min"))
        if not items:
            return
        self._grid_row("Continue watching", [m for m, _ in items],
                       subtitles={m["id"]: s for m, s in items}, mixed=True)

    def _grid_row(self, title: str, items: list[dict], mixed: bool = False,
                  subtitles: dict[int, str] | None = None) -> None:
        if not items:
            return
        self.lay.addWidget(SectionHeader(title))
        host = QWidget()
        flow = FlowLayout(host, h_spacing=12, v_spacing=12)
        for item in items:
            card = MediaCard(self.c, item, subtitle=(subtitles or {}).get(item["id"], ""))
            card.openRequested.connect(self._open)
            card.playRequested.connect(self._play)
            flow.addWidget(card)
        self.lay.addWidget(host)

    # ---------------------------------------------------------------- actions
    def _open(self, item: dict) -> None:
        self.c.open_media(item)

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
