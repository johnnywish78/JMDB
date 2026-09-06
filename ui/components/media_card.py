"""Reusable cards: media list card with cover + labels."""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget


class MediaCard(QWidget):
    clicked = pyqtSignal()
    double_clicked = pyqtSignal()

    def __init__(self, title: str, subtitle: str = "", badge: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("CardPanel")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        self.cover = QLabel()
        self.cover.setFixedSize(56, 78)
        self.cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.cover)
        text = QVBoxLayout()
        text.setSpacing(2)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("PosterTitle")
        self.title_label.setWordWrap(True)
        text.addWidget(self.title_label)
        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setObjectName("PosterYear")
        self.subtitle_label.setWordWrap(True)
        text.addWidget(self.subtitle_label)
        if badge:
            badge_label = QLabel(badge)
            badge_label.setObjectName("MutedLabel")
            text.addWidget(badge_label)
        text.addStretch(1)
        layout.addLayout(text, 1)

    def set_cover_pixmap(self, pixmap) -> None:
        if pixmap and not pixmap.isNull():
            self.cover.setPixmap(
                pixmap.scaled(
                    self.cover.size(),
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )

    def set_cover_text(self, glyph: str) -> None:
        self.cover.setText(glyph)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit()
        super().mouseDoubleClickEvent(event)
