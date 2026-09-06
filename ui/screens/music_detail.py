"""Album detail: track list + play."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ui.components.states import EmptyState
from ui.screens.base import Screen


class AlbumDetailScreen(Screen):
    title = "Album"

    def __init__(self, context, parent=None) -> None:
        super().__init__(context, parent)
        self.album_id = None
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.root.addWidget(self.scroll, 1)
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setSpacing(14)
        self.scroll.setWidget(self.content)

    def enter(self, album_id: int = 0, **params) -> None:
        self.album_id = album_id

    def refresh(self) -> None:
        if self.album_id is None:
            return

        def work():
            return self.context.services.music.album_detail(
                self.album_id, self.context.profile_id
            )

        from ui.app.context import run_async

        run_async(work, self._populate)

    def _populate(self, detail: dict | None) -> None:
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if detail is None:
            self.content_layout.addWidget(EmptyState("Album not found"))
            return

        header = QWidget()
        header_layout = QHBoxLayout(header)
        self.cover = QLabel()
        self.cover.setFixedSize(220, 220)
        self.cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover.setStyleSheet("border-radius: 10px; background: #2a3040;")
        header_layout.addWidget(self.cover)
        info = QVBoxLayout()
        title = QLabel(detail["title"])
        title.setObjectName("ScreenTitle")
        title.setWordWrap(True)
        info.addWidget(title)
        from ui.components.detail_body import _fact_row

        for label, value in (
            ("Artist", detail.get("artist_name", "")),
            ("Year", str(detail.get("year") or "")),
            ("Tracks", str(detail.get("track_count", ""))),
            ("Genres", ", ".join(detail.get("genres", []))),
        ):
            info.addWidget(_fact_row(label, value))

        from PyQt6.QtWidgets import QPushButton

        play_button = QPushButton("  ▶  Play album")
        play_button.setObjectName("PrimaryButton")
        play_button.clicked.connect(lambda: self._play_album())
        favorite_button = QPushButton("♥ Favorite")
        favorite_button.setCheckable(True)
        favorite_button.setChecked(bool(detail.get("is_favorite")))
        favorite_button.toggled.connect(
            lambda on: self._toggle_favorite(on)
        )
        buttons = QHBoxLayout()
        buttons.addWidget(play_button)
        buttons.addWidget(favorite_button)
        buttons.addStretch(1)
        info.addLayout(buttons)
        info.addStretch(1)
        header_layout.addLayout(info, 1)
        self.content_layout.addWidget(header)
        self._load_cover(detail.get("cover_path", ""))

        from ui.components.detail_body import _section_title

        self.content_layout.addWidget(_section_title("Tracks"))
        for track in detail["tracks"]:
            row = self._track_row(track)
            self.content_layout.addWidget(row)
        self.content_layout.addStretch(1)

    def _track_row(self, track: dict) -> QWidget:
        from ui.player.controls import format_time
        from PyQt6.QtWidgets import QPushButton

        row = QWidget()
        row.setObjectName("CardPanel")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(10, 6, 10, 6)
        number = QLabel(f"{track.get('track_number') or '·'}")
        number.setFixedWidth(32)
        layout.addWidget(number)
        title = QLabel(track["title"])
        layout.addWidget(title, 1)
        artist = QLabel(track.get("artist_name", ""))
        artist.setObjectName("MutedLabel")
        layout.addWidget(artist, 1)
        duration = format_time(track.get("duration_seconds") or 0)
        duration_label = QLabel(duration)
        duration_label.setObjectName("MutedLabel")
        layout.addWidget(duration_label)
        play_button = QPushButton()
        play_button.setObjectName("FlatIconButton")
        from ui.app.context import icon

        play_button.setIcon(icon("play"))
        play_button.setEnabled(bool(track.get("file_path")))
        play_button.setToolTip("Play track")
        play_button.clicked.connect(lambda _=False, t=track: self._play_track(t))
        layout.addWidget(play_button)
        return row

    def _load_cover(self, path: str) -> None:
        if not path:
            self.cover.setText("🎵")
            return
        context = self.context

        def handler(key, pixmap):
            self.cover.setPixmap(
                pixmap.scaled(
                    self.cover.size(),
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )

        context.images.ready.connect(handler)
        context.images.request(f"album-cover-{self.album_id}", path, 440)

    def _play_album(self) -> None:
        queue = self.context.services.music.album_playables(self.album_id)
        if not queue:
            self.context.toast("No playable tracks", "warning")
            return
        self.context.open_player(queue[0], queue)

    def _play_track(self, track: dict) -> None:
        playable = self.context.services.music.playable(track["id"])
        if playable is None:
            self.context.toast("No playable file", "warning")
            return
        queue = self.context.services.music.album_playables(self.album_id)
        self.context.open_player(playable, queue or None)

    def _toggle_favorite(self, on: bool) -> None:
        self.context.services.repos.lists.set_favorite(
            self.context.profile_id, "album", self.album_id, on
        )
