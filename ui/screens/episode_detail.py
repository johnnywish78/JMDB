"""Episode detail screen."""
from __future__ import annotations

from PyQt6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget

from ui.components.detail_body import _fact_row, _section_title
from ui.components.states import EmptyState
from ui.screens.base import Screen


class EpisodeDetailScreen(Screen):
    title = "Episode"

    def __init__(self, context, parent=None) -> None:
        super().__init__(context, parent)
        self.episode_id = None
        self.heading = QLabel("")
        self.heading.setObjectName("ScreenTitle")
        self.root.addWidget(self.heading)
        self.show_link = QLabel("")
        self.show_link.setObjectName("SectionMore")
        self.root.addWidget(self.show_link)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.root.addWidget(self.scroll, 1)
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setSpacing(14)
        self.scroll.setWidget(self.content)

    def enter(self, episode_id: int = 0, **params) -> None:
        self.episode_id = episode_id

    def refresh(self) -> None:
        if self.episode_id is None:
            return

        def work():
            return self.context.services.tv.episode_detail(
                self.episode_id, self.context.profile_id
            )

        from ui.app.context import run_async

        run_async(work, self._populate)

    def _populate(self, detail: dict | None) -> None:
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if detail is None:
            self.content_layout.addWidget(EmptyState("Episode not found"))
            return
        self.heading.setText(
            f"S{detail['season_number']:02d}E{detail['episode_number']:02d} · "
            f"{detail.get('title') or 'Episode'}"
        )
        self.show_link.setText(f"← {detail['show_title']}")
        self.show_link.setCursor(self.cursor())
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QPushButton

        self.show_link.setCursor(Qt.CursorShape.PointingHandCursor)
        self.show_link.mousePressEvent = lambda _e: self.context.router.navigate(
            "show_detail", show_id=detail["tv_show_id"]
        )

        facts = QWidget()
        facts_layout = QVBoxLayout(facts)
        facts_layout.setContentsMargins(0, 0, 0, 0)
        for label, value in (
            ("Aired", detail.get("air_date") or ""),
            ("Runtime", f"{detail['runtime_seconds'] // 60} min" if detail.get("runtime_seconds") else ""),
            ("Rating", f"★ {detail['rating']:.1f}" if detail.get("rating") else ""),
            ("Watched", "yes" if detail.get("watched") else "no"),
            (
                "Resume",
                f"{int(detail['position_seconds'] // 60)}:{int(detail['position_seconds'] % 60):02d}"
                if detail.get("position_seconds")
                else "—",
            ),
        ):
            facts_layout.addWidget(_fact_row(label, value))
        self.content_layout.addWidget(facts)

        if detail.get("overview"):
            self.content_layout.addWidget(_section_title("Overview"))
            from PyQt6.QtWidgets import QLabel

            overview = QLabel(detail["overview"])
            overview.setWordWrap(True)
            self.content_layout.addWidget(overview)

        self.content_layout.addWidget(_section_title("File"))
        for media_file in detail.get("files", []):
            self.content_layout.addWidget(
                _fact_row(f".{media_file.get('container', '?')}", media_file["path"])
            )
        if not detail.get("files"):
            self.content_layout.addWidget(QLabel("No file linked to this episode."))

        buttons = QWidget()
        from PyQt6.QtWidgets import QHBoxLayout

        buttons_layout = QHBoxLayout(buttons)
        play = QPushButton("  ▶  Play episode")
        play.setObjectName("PrimaryButton")
        play.setEnabled(bool(detail.get("files")))
        play.clicked.connect(lambda: self._play(detail))
        mark = QPushButton("✓ Mark watched" if not detail.get("watched") else "↺ Mark unwatched")
        mark.clicked.connect(lambda: self._toggle_watched(detail))
        buttons_layout.addWidget(play)
        buttons_layout.addWidget(mark)
        buttons_layout.addStretch(1)
        self.content_layout.addWidget(buttons)
        self.content_layout.addStretch(1)

    def _play(self, detail: dict) -> None:
        playable = self.context.services.tv.playable(detail["id"])
        if playable is None:
            self.context.toast("No file for this episode", "warning")
            return
        self.context.open_player(playable)

    def _toggle_watched(self, detail: dict) -> None:
        playback = self.context.services.playback
        if detail.get("watched"):
            playback.mark_unwatched(self.context.profile_id, "episode", detail["id"])
        else:
            playback.mark_watched(self.context.profile_id, "episode", detail["id"])
        self.refresh()
