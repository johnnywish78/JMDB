"""Shared UI states: empty, loading, error; plus section headers."""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.app.context import icon


class SectionHeader(QWidget):
    see_more = pyqtSignal()

    def __init__(self, title: str, more_route: str | None = None, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        label = QLabel(title)
        label.setObjectName("SectionHeader")
        layout.addWidget(label)
        layout.addStretch(1)
        if more_route:
            more = QPushButton("see more →")
            more.setObjectName("SectionMore")
            more.setCursor(Qt.CursorShape.PointingHandCursor)
            more.clicked.connect(self.see_more.emit)
            layout.addWidget(more)


class EmptyState(QWidget):
    """A friendly empty state with optional action button."""

    action = pyqtSignal()

    def __init__(
        self,
        message: str,
        hint: str = "",
        action_text: str = "",
        glyph: str = "📂",
        parent=None,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(10)
        icon_label = QLabel(glyph)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = icon_label.font()
        font.setPixelSize(46)
        icon_label.setFont(font)
        layout.addWidget(icon_label)
        message_label = QLabel(message)
        message_label.setObjectName("SectionHeader")
        message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message_label.setWordWrap(True)
        layout.addWidget(message_label)
        if hint:
            hint_label = QLabel(hint)
            hint_label.setObjectName("MutedLabel")
            hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            hint_label.setWordWrap(True)
            layout.addWidget(hint_label)
        self.action_button = None
        if action_text:
            button = QPushButton(action_text)
            button.setObjectName("PrimaryButton")
            button.clicked.connect(self.action.emit)
            layout.addWidget(button, 0, Qt.AlignmentFlag.AlignCenter)
            self.action_button = button


class LoadingState(QWidget):
    def __init__(self, message: str = "Loading…", parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label = QLabel(message)
        label.setObjectName("MutedLabel")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
        from PyQt6.QtWidgets import QProgressBar

        bar = QProgressBar()
        bar.setRange(0, 0)
        bar.setFixedWidth(240)
        layout.addWidget(bar, 0, Qt.AlignmentFlag.AlignCenter)


class ErrorState(QWidget):
    action = pyqtSignal()

    def __init__(self, message: str, action_text: str = "Retry", parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        glyph = QLabel("⚠️")
        glyph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(glyph)
        label = QLabel(message)
        label.setObjectName("SectionHeader")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setWordWrap(True)
        layout.addWidget(label)
        button = QPushButton(action_text)
        button.clicked.connect(self.action.emit)
        layout.addWidget(button, 0, Qt.AlignmentFlag.AlignCenter)
