"""Search, Recommendations and Statistics screens."""
from __future__ import annotations

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ui.components.cards import MediaCard
from ui.components.common import EmptyState, FlowLayout, SectionHeader


class SearchScreen(QWidget):
    """params: query=str (optional, from the global top-bar)."""

    def __init__(self, container, query: str = "", parent=None):
        super().__init__(parent)
        self.c = container
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 8, 16, 16)
        root.addWidget(SectionHeader("Search", "titles, genres, years"))
        self.edit = QLineEdit(query)
        self.edit.setObjectName("SearchEdit")
        self.edit.setPlaceholderText("Try 'Matrix', 'crime', '1999'…")
        root.addWidget(self.edit)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        root.addWidget(self.scroll, 1)
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(180)
        self._debounce.timeout.connect(self.run)
        self.edit.textChanged.connect(lambda _t: self._debounce.start())
        self.run()

    def run(self) -> None:
        q = self.edit.text().strip()
        if not q:
            self.scroll.setWidget(EmptyState(
                "Search the library", "Type at least two characters of a title, genre or year."))
            return
        results = self.c.search.search(q)
        host = QWidget()
        lay = QVBoxLayout(host)
        for kind, label in (("movie", "Movies"), ("show", "TV Shows")):
            subset = [m for m in results if m["kind"] == kind]
            if not subset:
                continue
            lay.addWidget(SectionHeader(label, f"{len(subset)} results"))
            flow_host = QWidget()
            flow = FlowLayout(flow_host)
            for item in subset:
                card = MediaCard(self.c, item)
                card.openRequested.connect(self.c.open_media)
                flow.addWidget(card)
            lay.addWidget(flow_host)
        if not self.c.search.search(q):
            lay.addWidget(EmptyState("No results", f"Nothing matches “{q}”."))
        lay.addStretch(1)
        self.scroll.setWidget(host)

    def set_query(self, text: str) -> None:
        self.edit.setText(text)


class RecommendationsScreen(QWidget):
    def __init__(self, container, parent=None):
        super().__init__(parent)
        self.c = container
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 8, 16, 16)
        aff = self.c.reco.affinity()
        top = sorted(aff.items(), key=lambda p: p[1], reverse=True)[:4]
        root.addWidget(SectionHeader("For You",
                                     "tuned to your taste" if top else "rate/favorite titles to tune"))
        if top:
            panel = QWidget()
            panel.setObjectName("Panel")
            ph = QHBoxLayout(panel)
            ph.setContentsMargins(14, 10, 14, 10)
            ph.addWidget(QLabel("Taste profile:"))
            for genre, weight in top:
                chip = QLabel(f"{genre} {weight:.1f}")
                chip.setStyleSheet("background:#1b202d;border-radius:10px;padding:5px 12px")
                ph.addWidget(chip)
            ph.addStretch(1)
            root.addWidget(panel)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        root.addWidget(scroll, 1)
        items = self.c.reco.for_you(18)
        host = QWidget()
        flow = FlowLayout(host)
        if not items:
            scroll.setWidget(EmptyState("All caught up", "Nothing left to recommend — yet."))
            return
        for item in items:
            card = MediaCard(self.c, item)
            card.openRequested.connect(self.c.open_media)
            flow.addWidget(card)
        scroll.setWidget(host)


class _BarsWidget(QWidget):
    """Minimal vertical bar chart (painted, no deps)."""

    def __init__(self, values: list[float], parent=None):
        super().__init__(parent)
        self.values = values
        self.setMinimumHeight(120)

    def paintEvent(self, event) -> None:
        if not self.values:
            return
        painter = QPainter(self)
        w = self.width() / len(self.values)
        peak = max(self.values) or 1
        for i, value in enumerate(self.values):
            h = max(3, (value / peak) * (self.height() - 14))
            painter.fillRect(int(i * w + 3), int(self.height() - h), int(w - 6), int(h),
                             QColor("#f5b942"))
        painter.end()


class StatisticsScreen(QWidget):
    def __init__(self, container, parent=None):
        super().__init__(parent)
        self.c = container
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 8, 16, 16)
        s = self.c.stats.overview()
        root.addWidget(SectionHeader("Statistics", "computed live from your database"))

        grid = QGridLayout()
        grid.setSpacing(10)
        cards = [
            (s["movies_watched"], "films watched"),
            (s["episodes_watched"], "episodes watched"),
            (f"{s['hours']}h", "total watch time"),
            (f"{s['streak']}d", "activity streak"),
            (s["avg_rating"] or "—", f"avg rating ({s['rated_count']})"),
            (s["favorites"], "favorites"),
        ]
        for i, (value, label) in enumerate(cards):
            cell = QWidget()
            cell.setObjectName("Panel")
            vb = QVBoxLayout(cell)
            vb.setContentsMargins(14, 12, 14, 12)
            v = QLabel(str(value))
            v.setStyleSheet("font-size:26px;font-weight:700;color:#f5b942")
            l = QLabel(label)
            l.setObjectName("Muted")
            vb.addWidget(v)
            vb.addWidget(l)
            grid.addWidget(cell, i // 3, i % 3)
        root.addLayout(grid)

        two = QHBoxLayout()
        panel_g = QWidget()
        panel_g.setObjectName("Panel")
        vg = QVBoxLayout(panel_g)
        vg.setContentsMargins(14, 12, 14, 12)
        vg.addWidget(QLabel("Genre distribution"))
        if s["top_genres"]:
            peak = s["top_genres"][0][1] or 1
            for genre, weight in s["top_genres"]:
                row = QWidget()
                rh = QHBoxLayout(row)
                rh.setContentsMargins(0, 0, 0, 0)
                rh.addWidget(QLabel(genre))
                from PyQt6.QtWidgets import QProgressBar

                bar = QProgressBar()
                bar.setRange(0, int(peak))
                bar.setValue(int(weight))
                bar.setTextVisible(False)
                bar.setFixedHeight(8)
                rh.addWidget(bar, 1)
                rh.addWidget(QLabel(f"{weight:.0f}"))
                vg.addWidget(row)
        else:
            vg.addWidget(QLabel("Watch something first."))
        two.addWidget(panel_g, 1)

        panel_a = QWidget()
        panel_a.setObjectName("Panel")
        va = QVBoxLayout(panel_a)
        va.setContentsMargins(14, 12, 14, 12)
        va.addWidget(QLabel("Activity · last 14 days"))
        va.addWidget(_BarsWidget([d["count"] for d in s["activity"]]))
        two.addWidget(panel_a, 1)
        root.addLayout(two)
        root.addStretch(1)
