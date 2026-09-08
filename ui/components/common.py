"""Shared widgets: FlowLayout (wraps children), SectionHeader, EmptyState."""
from __future__ import annotations

from PyQt6.QtCore import QRect, QSize, Qt
from PyQt6.QtWidgets import QLabel, QLayout, QLayoutItem, QSizePolicy, QVBoxLayout, QWidget


class FlowLayout(QLayout):
    """Classic Qt 'flow layout': children flow left→right, wrapping by width."""

    def __init__(self, parent=None, margin: int = 0, h_spacing: int = 12, v_spacing: int = 12):
        super().__init__(parent)
        self._items: list[QLayoutItem] = []
        self.setContentsMargins(margin, margin, margin, margin)
        self._h = h_spacing
        self._v = v_spacing

    def __del__(self):  # avoid leaks when layouts are rebuilt
        while self.count():
            self.takeAt(0)

    def addItem(self, item: QLayoutItem) -> None:
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def clear(self) -> None:
        while self._items:
            item = self.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        return size + QSize(m.left() + m.right(), m.top() + m.bottom())

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        m = self.contentsMargins()
        effective = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x, y, line_h = effective.x(), effective.y(), 0
        for item in self._items:
            hint = item.sizeHint()
            next_x = x + hint.width() + self._h
            if next_x - self._h > effective.right() and line_h > 0:
                x = effective.x()
                y = y + line_h + self._v
                next_x = x + hint.width() + self._h
                line_h = 0
            if not test_only:
                item.setGeometry(QRect(x, y, hint.width(), hint.height()))
            x = next_x
            line_h = max(line_h, hint.height())
        return y + line_h - rect.y() + m.bottom()


class SectionHeader(QWidget):
    def __init__(self, title: str, subtitle: str = "", parent=None):
        super().__init__(parent)
        from PyQt6.QtWidgets import QHBoxLayout

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 14, 0, 6)
        title_lbl = QLabel(title)
        title_lbl.setObjectName("SectionTitle")
        lay.addWidget(title_lbl)
        if subtitle:
            sub = QLabel(subtitle)
            sub.setObjectName("Muted")
            lay.addWidget(sub)
        lay.addStretch(1)


class EmptyState(QWidget):
    def __init__(self, title: str, message: str, parent=None):
        super().__init__(parent)
        self.setObjectName("EmptyState")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 32, 24, 32)
        head = QLabel(title)
        head.setStyleSheet("font-size:16px;font-weight:600")
        head.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body = QLabel(message)
        body.setWordWrap(True)
        body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body.setObjectName("Muted")
        lay.addWidget(head)
        lay.addWidget(body)
