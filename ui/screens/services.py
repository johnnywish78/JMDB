"""Services launcher grid + embedded browser screen (with bookmarks)."""
from __future__ import annotations

from PyQt6.QtCore import Qt, QPoint, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.browser.engine import BrowserWidget, engine_available
from ui.components.common import FlowLayout, SectionHeader


# ─── service card painter (renders an SVG-like icon from code) ────────────────

def _paint_service_icon(painter: QPainter, key: str, x: int, y: int, size: int) -> None:
    """Draw a simple geometric icon for each service."""
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    r = size // 2
    cx, cy = x + r, y + r

    if key == "youtube":
        # Red rounded rectangle with play triangle
        painter.setBrush(QColor(255, 0, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(x + 2, y + int(size * 0.25), size - 4, size - int(size * 0.5), r * 0.4, r * 0.4)
        tri_size = size // 4
        painter.setBrush(QColor("white"))
        painter.drawPolygon(
            QPoint(cx, cy - tri_size // 2),
            QPoint(cx, cy + tri_size // 2),
            QPoint(cx + tri_size, cy),
        )
    elif key == "telegram":
        # Blue paper plane
        painter.setBrush(QColor(42, 187, 238))
        painter.setPen(Qt.PenStyle.NoPen)
        pts = [
            QPoint(x + size // 4, y + size // 2),
            QPoint(x + size - size // 6, y + size // 6),
            QPoint(x + size // 3, y + size - size // 6),
            QPoint(x + size // 6, y + size // 2),
        ]
        painter.drawPolygon(*pts)
    elif key == "spotify":
        # Green circle with three arcs
        painter.setBrush(QColor(29, 185, 84))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(x + 4, y + 4, size - 8, size - 8)
        painter.setPen(QColor("white"))
        painter.setLineWidth(max(2, size // 12))
        painter.drawArc(x + size // 4, y + size // 3, size // 2, size // 2, 16 * 30, 16 * -120)
        painter.drawArc(x + size // 4, y + size // 3, size // 2, size // 2, 16 * 60, 16 * -100)
        painter.drawArc(x + size // 4, y + size // 3, size // 2, size // 2, 16 * 90, 16 * -80)
    elif key == "tvtime":
        # Orange circle with clock hands
        painter.setBrush(QColor(245, 166, 35))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(x + 4, y + 4, size - 8, size - 8)
        painter.setPen(QColor("white"))
        painter.setLineWidth(max(2, size // 10))
        painter.drawLine(cx, cy, cx, y + int(size * 0.18))
        painter.drawLine(cx, cy, cx + int(r * 0.6), cy)
        painter.setPointSize(max(6, size // 10))


class ServiceCard(QWidget):
    """Branded tile for one external service."""

    clicked = pyqtSignal(object)   # ServiceInfo

    def __init__(self, svc, parent=None):
        super().__init__(parent)
        self.svc = svc
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(220, 110)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(8)

        # Icon row
        icon_row = QHBoxLayout()
        icon_row.setSpacing(10)
        self.icon_lbl = QLabel("")
        self.icon_lbl.setFixedSize(56, 56)
        self.icon_lbl.setStyleSheet(f"border-radius:12px; background:{svc.color};")
        self._render_icon()
        icon_row.addWidget(self.icon_lbl)

        title = QLabel(svc.name)
        title.setStyleSheet("font-size:16px;font-weight:700;color:palette(text)")
        title.setTextFormat(Qt.TextFormat.RichText)
        icon_row.addWidget(title)
        icon_row.addStretch(1)
        root.addLayout(icon_row)

        # Note
        note = QLabel(svc.note)
        note.setObjectName("Muted")
        note.setWordWrap(True)
        root.addWidget(note)

        # Open button
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self.btn_embed = QPushButton("Open in JMDB")
        self.btn_embed.setProperty("accent", True)
        self.btn_embed.clicked.connect(lambda: self.clicked.emit(svc))
        btn_row.addWidget(self.btn_embed)
        self.btn_ext = QPushButton("↗ External")
        self.btn_ext.clicked.connect(lambda: self._external())
        btn_row.addWidget(self.btn_ext)
        btn_row.addStretch(1)
        root.addLayout(btn_row)

    def _render_icon(self) -> None:
        from PyQt6.QtGui import QPixmap
        pix = QPixmap(56, 56)
        pix.fill(QColor(self.svc.color))
        p = QPainter(pix)
        _paint_service_icon(p, self.svc.key, 0, 0, 56)
        p.end()
        self.icon_lbl.setPixmap(pix.scaled(56, 56, Qt.AspectRatioMode.KeepAspectRatio,
                                            Qt.TransformationMode.SmoothTransformation))

    def _external(self) -> None:
        from app.services.service_manager import ServiceManager
        ServiceManager.open_external(self.svc.url)


class ServicesScreen(QWidget):
    def __init__(self, container, parent=None):
        super().__init__(parent)
        self.c = container
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 8, 16, 16)
        root.addWidget(SectionHeader("Services",
                                     "launcher hub — JMDB stores no third-party credentials"))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        root.addWidget(scroll, 1)
        host = QWidget()
        flow = FlowLayout(host, h_spacing=16, v_spacing=16)
        for svc in self.c.services.services():
            card = ServiceCard(svc)
            card.clicked.connect(self._open)
            flow.addWidget(card)
        scroll.setWidget(host)

    def _open(self, svc) -> None:
        if engine_available() and self.c.on_open_url:
            self.c.on_open_url(svc.url)
        else:
            from app.services.service_manager import ServiceManager
            ServiceManager.open_external(svc.url)


class BrowserScreen(QWidget):
    def __init__(self, container, url: str = "", parent=None):
        super().__init__(parent)
        self.c = container
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        avail = engine_available()
        label_text = "Web browser"
        sub_text = "bookmarks persist in your database" if avail else "embedded engine unavailable — use external browser"
        root.addWidget(SectionHeader(label_text, sub_text))
        self.browser = BrowserWidget(container.bookmarks)
        root.addWidget(self.browser, 1)

        bmk_row = QHBoxLayout()
        bmk_row.setContentsMargins(12, 4, 12, 8)
        bmk_row.addWidget(QLabel("Bookmarks:"))
        for b in self.c.bookmarks.all():
            chip = QPushButton(b["name"])
            chip.setFixedHeight(26)
            chip.clicked.connect(lambda _=None, u=b["url"]: self.browser.open_url(u))
            bmk_row.addWidget(chip)
        bmk_row.addStretch(1)
        root.addLayout(bmk_row)
        if url:
            self.browser.open_url(url)

    def open_url(self, url: str) -> None:
        self.browser.open_url(url)
