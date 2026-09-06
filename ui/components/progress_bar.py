"""Progress overlay for cards (watch progress)."""
from __future__ import annotations

from PyQt6.QtWidgets import QProgressBar


class ProgressOverlay(QProgressBar):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("ProgressOverlay")
        self.setRange(0, 100)
        self.setTextVisible(False)
        self.setFixedHeight(4)

    def set_fraction(self, fraction: float) -> None:
        self.setValue(int(max(0.0, min(1.0, fraction)) * 100))
