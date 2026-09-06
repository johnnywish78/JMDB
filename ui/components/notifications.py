"""Toast notifications."""
from __future__ import annotations

import logging

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QLabel, QWidget

logger = logging.getLogger(__name__)


class Toast(QLabel):
    def __init__(self, message: str, level: str = "info", parent=None) -> None:
        super().__init__(message, parent)
        self.setObjectName("Toast")
        self.setProperty("level", level)
        self.setWindowFlags(
            Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("padding: 10px 18px;")

    def show_and_auto_hide(self, duration_ms: int, on_done) -> None:
        self.adjustSize()
        self.show()
        QTimer.singleShot(duration_ms, lambda: (self.hide(), self.deleteLater(), on_done()))


class ToastManager:
    """Shows toasts stacked bottom-right of the main window."""

    def __init__(self, main_window) -> None:
        self._window = main_window
        self._active: list[Toast] = []

    def show(self, message: str, level: str = "info", duration_ms: int = 4000) -> None:
        if not message:
            return
        toast = Toast(message, level)
        margin = 24
        y = self._window.height() - margin - 46 * (len(self._active) + 1)
        toast.setParent(self._window)
        toast.move(self._window.width() - toast.width() - margin, max(margin, y))
        toast.show_and_auto_hide(duration_ms, lambda: self._forget(toast))
        self._active.append(toast)
        logger.info("toast[%s]: %s", level, message)

    def _forget(self, toast: Toast) -> None:
        if toast in self._active:
            self._active.remove(toast)
