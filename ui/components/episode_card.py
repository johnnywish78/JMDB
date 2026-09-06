"""EpisodeCard: still + number/title + watched state + play."""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ui.app.context import icon
from ui.components.progress_bar import ProgressOverlay


class EpisodeCard(QWidget):
    clicked = pyqtSignal(dict)
    play_requested = pyqtSignal(dict)

    def __init__(self, episode: dict, parent=None) -> None:
        super().__init__(parent)
        self.episode = episode
        self.setObjectName("CardPanel")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        self.still = QLabel()
        self.still.setFixedSize(150, 84)
        self.still.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.still.setText("📺")
        layout.addWidget(self.still)

        text = QVBoxLayout()
        text.setSpacing(2)
        number = f"S{episode.get('season_number', 0):02d}E{episode.get('episode_number', 0):02d}"
        title = episode.get("title") or f"Episode {episode.get('episode_number', '?')}"
        self.heading = QLabel(f"{number} · {title}")
        self.heading.setObjectName("PosterTitle")
        text.addWidget(self.heading)
        overview = episode.get("overview") or ""
        self.overview = QLabel(overview[:140] + ("…" if len(overview) > 140 else ""))
        self.overview.setObjectName("MutedLabel")
        self.overview.setWordWrap(True)
        text.addWidget(self.overview)

        meta_bits = []
        if episode.get("air_date"):
            meta_bits.append(str(episode["air_date"]))
        if episode.get("file_path"):
            meta_bits.append("▶ available")
        else:
            meta_bits.append("no file")
        self.meta = QLabel(" · ".join(meta_bits))
        self.meta.setObjectName("PosterYear")
        text.addWidget(self.meta)

        if episode.get("position_seconds") and episode.get("duration_seconds"):
            progress = ProgressOverlay()
            progress.set_fraction(
                episode["position_seconds"] / max(1.0, episode["duration_seconds"])
            )
            text.addWidget(progress)
        layout.addLayout(text, 1)

        self.play_button = QPushButton()
        self.play_button.setObjectName("FlatIconButton")
        self.play_button.setIcon(icon("play"))
        self.play_button.setToolTip("Play episode")
        self.play_button.setEnabled(bool(episode.get("file_path")))
        self.play_button.clicked.connect(
            lambda: self.play_requested.emit(self.episode)
        )
        layout.addWidget(self.play_button, 0, Qt.AlignmentFlag.AlignTop)

        if episode.get("watched"):
            check = QLabel("✓")
            check.setToolTip("Watched")
            check.setObjectName("PosterYear")
            layout.insertWidget(0, check)

    def set_still_pixmap(self, pixmap) -> None:
        if pixmap and not pixmap.isNull():
            self.still.setPixmap(
                pixmap.scaled(
                    self.still.size(),
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.episode)
        super().mousePressEvent(event)
