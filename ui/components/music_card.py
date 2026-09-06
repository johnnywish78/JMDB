"""MusicCard: square album/artist art + titles."""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class MusicCard(QWidget):
    clicked = pyqtSignal(dict)
    play_requested = pyqtSignal(dict)

    def __init__(self, data: dict, width: int = 170, parent=None) -> None:
        super().__init__(parent)
        self.data = data
        self.setObjectName("PosterCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 2)
        layout.setSpacing(4)
        self.art = QLabel()
        self.art.setFixedSize(width, width)
        self.art.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.art.setText("🎵")
        layout.addWidget(self.art)
        self.title = QLabel(str(data.get("title", "")))
        self.title.setObjectName("PosterTitle")
        self.title.setWordWrap(True)
        self.title.setFixedWidth(width)
        layout.addWidget(self.title)
        self.subtitle = QLabel(str(data.get("artist_name") or data.get("subtitle") or ""))
        self.subtitle.setObjectName("PosterYear")
        self.subtitle.setWordWrap(True)
        self.subtitle.setFixedWidth(width)
        layout.addWidget(self.subtitle)

    def set_pixmap(self, pixmap) -> None:
        if pixmap and not pixmap.isNull():
            self.art.setPixmap(
                pixmap.scaled(
                    self.art.size(),
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            self.art.setText("")

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.play_requested.emit(self.data)
        else:
            self.clicked.emit(self.data)
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.data)
        super().mousePressEvent(event)
