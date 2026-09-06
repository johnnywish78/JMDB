"""Season card for show detail."""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ui.app.context import icon
from ui.components.progress_bar import ProgressOverlay


class SeasonCard(QWidget):
    open_requested = pyqtSignal(int)
    mark_watched = pyqtSignal(int)

    def __init__(self, season: dict, parent=None) -> None:
        super().__init__(parent)
        self.season_id = season["id"]
        self.setObjectName("CardPanel")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(14)

        self.poster = QLabel()
        self.poster.setFixedSize(92, 138)
        self.poster.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.poster.setText("📺")
        layout.addWidget(self.poster)

        text = QVBoxLayout()
        text.setSpacing(4)
        title = QLabel(season.get("title") or f"Season {season['season_number']}")
        title.setObjectName("SectionHeader")
        text.addWidget(title)
        meta = QLabel(
            f"{season.get('episode_count', 0)} episodes"
            f" · {season.get('watched_count', 0)} watched"
        )
        meta.setObjectName("MutedLabel")
        text.addWidget(meta)
        if season.get("air_date"):
            aired = QLabel(f"Aired {season['air_date']}")
            aired.setObjectName("PosterYear")
            text.addWidget(aired)
        progress = ProgressOverlay()
        if season.get("episode_count"):
            progress.set_fraction(season.get("watched_count", 0) / season["episode_count"])
        text.addWidget(progress)
        layout.addLayout(text, 1)

        self.mark_watched_button = QPushButton("Mark season watched")
        self.mark_watched_button.clicked.connect(
            lambda: self.mark_watched.emit(self.season_id)
        )
        if season.get("episode_count") and (
            season.get("watched_count", 0) >= season["episode_count"]
        ):
            self.mark_watched_button.setText("✓ Watched")
            self.mark_watched_button.setEnabled(False)
        layout.addWidget(self.mark_watched_button, 0, Qt.AlignmentFlag.AlignVCenter)

    def set_pixmap(self, pixmap) -> None:
        if pixmap and not pixmap.isNull():
            self.poster.setPixmap(
                pixmap.scaled(
                    self.poster.size(),
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.open_requested.emit(self.season_id)
        super().mousePressEvent(event)
