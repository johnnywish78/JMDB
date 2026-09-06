"""Badges: rating, year/quality chips, watched checkmarks."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QWidget


class RatingBadge(QLabel):
    def __init__(self, rating: float | None, parent=None) -> None:
        super().__init__(parent)
        if rating is None:
            self.setText("—")
            self.setToolTip("No rating available")
        else:
            self.setText(f"★ {rating:.1f}")
            self.setToolTip(f"Rating: {rating:.1f}/10")
        self.setObjectName("RatingBadge")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setProperty("class", "badge")


class MetadataBadge(QLabel):
    def __init__(self, text: str, tooltip: str = "", parent=None) -> None:
        super().__init__(text, parent)
        self.setObjectName("MetadataBadge")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if tooltip:
            self.setToolTip(tooltip)


class BadgeRow(QWidget):
    def __init__(self, badges: list[str], ratings: float | None = None, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        if ratings is not None:
            layout.addWidget(RatingBadge(ratings))
        for text in badges:
            if text:
                layout.addWidget(MetadataBadge(str(text)))
        layout.addStretch(1)
