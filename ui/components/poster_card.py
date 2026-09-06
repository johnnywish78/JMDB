"""PosterCard: poster image + title/year + optional overlays."""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ui.components.progress_bar import ProgressOverlay


class PosterCard(QWidget):
    clicked = pyqtSignal(dict)
    double_clicked = pyqtSignal(dict)
    play_requested = pyqtSignal(dict)

    def __init__(
        self,
        data: dict,
        width: int = 180,
        show_progress: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.data = data
        self._width = width
        self.setObjectName("PosterCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 2)
        layout.setSpacing(4)

        self.poster = QLabel()
        self.poster.setFixedWidth(width)
        self.poster.setFixedHeight(int(width * 1.5))
        self.poster.setObjectName("PosterImage")
        self.poster.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.poster)

        self.title = QLabel(str(data.get("title", "")))
        self.title.setObjectName("PosterTitle")
        self.title.setWordWrap(True)
        self.title.setFixedWidth(width)
        layout.addWidget(self.title)

        year = data.get("year") or ""
        subtitle = data.get("subtitle", "")
        meta = str(subtitle or year)
        self.subtitle = QLabel(meta)
        self.subtitle.setObjectName("PosterYear")
        self.subtitle.setWordWrap(True)
        layout.addWidget(self.subtitle)

        self.progress = ProgressOverlay()
        if show_progress and data.get("position_seconds") and data.get("duration_seconds"):
            fraction = data["position_seconds"] / max(1.0, data["duration_seconds"])
            self.progress.set_fraction(fraction)
            layout.addWidget(self.progress)
        else:
            self.progress.hide()

    def set_pixmap(self, pixmap) -> None:
        if pixmap and not pixmap.isNull():
            self.poster.setPixmap(
                pixmap.scaled(
                    self.poster.size(),
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            self.poster.setText("")
        else:
            from ui.app.context import asset_path

            self.poster.setPixmap(str(asset_path("posters/placeholder.svg")))

    def show_placeholder(self, glyph: str = "🎞") -> None:
        self.poster.setText(glyph)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.data)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit(self.data)
        super().mouseDoubleClickEvent(event)
