"""Season detail: episode list with stills, watched state, play."""
from __future__ import annotations

from PyQt6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget

from ui.components.states import EmptyState
from ui.screens.base import Screen


class SeasonDetailScreen(Screen):
    title = "Season"

    def __init__(self, context, parent=None) -> None:
        super().__init__(context, parent)
        self.season_id = None
        self.heading = QLabel("")
        self.heading.setObjectName("ScreenTitle")
        self.root.addWidget(self.heading)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.root.addWidget(self.scroll, 1)
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setSpacing(10)
        self.scroll.setWidget(self.content)

    def enter(self, season_id: int = 0, **params) -> None:
        self.season_id = season_id

    def refresh(self) -> None:
        if self.season_id is None:
            return

        def work():
            return self.context.services.tv.season_detail(
                self.season_id, self.context.profile_id
            )

        from ui.app.context import run_async

        run_async(work, self._populate)

    def _populate(self, detail: dict | None) -> None:
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if detail is None:
            self.content_layout.addWidget(EmptyState("Season not found"))
            return
        self._current_episodes = detail["episodes"]
        self.heading.setText(
            f"{detail['show_title']} — {detail['title']}"
        )
        from PyQt6.QtWidgets import QPushButton

        play_all = QPushButton("  ▶  Play season")
        play_all.setObjectName("PrimaryButton")
        play_all.clicked.connect(lambda: self._play_season(detail))
        self.content_layout.addWidget(play_all)

        from ui.components.episode_card import EpisodeCard

        for episode in detail["episodes"]:
            card = EpisodeCard(episode)
            card.clicked.connect(
                lambda ep: self.context.router.navigate("episode_detail", episode_id=ep["id"])
            )
            card.play_requested.connect(self._play_episode)
            self._load_still(card, episode)
            self.content_layout.addWidget(card)
        self.content_layout.addStretch(1)

    def _load_still(self, card, episode: dict) -> None:
        context = self.context

        def handler(key, pixmap, card=card):
            card.set_still_pixmap(pixmap)
            try:
                context.images.ready.disconnect(handler)
            except TypeError:
                pass

        context.images.ready.connect(handler)
        context.images.request(
            f"epstill-{episode['id']}-{id(card)}", episode.get("still_path", ""), 320
        )

    def _play_episode(self, episode: dict) -> None:
        playable = self.context.services.tv.playable(episode["id"])
        if playable is None:
            self.context.toast("No file for this episode", "warning")
            return
        # queue: remaining episodes of the season
        queue = []
        for ep in self._current_episodes:
            if ep.get("file_path"):
                item = self.context.services.tv.playable(ep["id"])
                if item:
                    queue.append(item)
        self.context.open_player(playable, queue or None)

    def _play_season(self, detail: dict) -> None:
        queue = []
        for ep in detail["episodes"]:
            if ep.get("file_path"):
                item = self.context.services.tv.playable(ep["id"])
                if item:
                    queue.append(item)
        if not queue:
            self.context.toast("No playable episodes in this season", "warning")
            return
        self.context.open_player(queue[0], queue)

    _current_episodes: list = []
