"""History + People screens."""
from __future__ import annotations

from datetime import datetime

from PyQt6.QtWidgets import (
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ui.components.common import EmptyState, FlowLayout, SectionHeader


def _rel_day(ts_ms: int) -> str:
    d = datetime.fromtimestamp(ts_ms / 1000).date()
    today = datetime.now().date()
    delta = (today - d).days
    return "Today" if delta <= 0 else "Yesterday" if delta == 1 else d.strftime("%b %d, %Y")


class HistoryScreen(QWidget):
    def __init__(self, container, parent=None):
        super().__init__(parent)
        self.c = container
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 8, 16, 16)
        root.addWidget(SectionHeader("Watch history", "completed playback sessions"))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        root.addWidget(scroll, 1)
        entries = self.c.history_repo.recent()
        if not entries:
            scroll.setWidget(EmptyState("No sessions yet",
                                        "Finished playbacks land here automatically."))
            return
        host = QWidget()
        vb = QVBoxLayout(host)
        vb.setSpacing(2)
        last_day = None
        for h in entries:
            day = _rel_day(h["finished_at"])
            if day != last_day:
                last_day = day
                lbl = QLabel(day.upper())
                lbl.setStyleSheet("color:#5c6478;font-size:11px;letter-spacing:2px;padding:12px 4px 4px")
                vb.addWidget(lbl)
            when = datetime.fromtimestamp(h["finished_at"] / 1000).strftime("%H:%M")
            row = QLabel(f"<b>{h['media_title']}</b> — <span style='color:#8b93a7'>{h['subtitle']}</span>"
                         f"<span style='float:right;color:#5c6478'> · {when}</span>")
            row.setStyleSheet("padding:6px 10px;background:#12151d;border-radius:8px")
            vb.addWidget(row)
        vb.addStretch(1)
        scroll.setWidget(host)


class PeopleScreen(QWidget):
    def __init__(self, container, parent=None):
        super().__init__(parent)
        self.c = container
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 8, 16, 16)
        root.addWidget(SectionHeader("People", "indexed from your library metadata"))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        root.addWidget(scroll, 1)
        people = self.c.people_repo.all_people()
        if not people:
            scroll.setWidget(EmptyState("No people indexed",
                                        "Enrich titles with metadata to build the cast index."))
            return
        host = QWidget()
        flow = FlowLayout(host)
        from PyQt6.QtWidgets import QPushButton

        for p in people:
            btn = QPushButton(f"{p['name']}\n{p['n']} titles")
            btn.setFixedSize(150, 56)
            btn.clicked.connect(lambda _=None, n=p["name"]:
                                self.c.open_media({"id": None, "kind": "person", "title": n}))
            flow.addWidget(btn)
        scroll.setWidget(host)


class PersonScreen(QWidget):
    """Filmography of one person (opened via kind='person' payload)."""
    def __init__(self, container, name: str = "", parent=None):
        super().__init__(parent)
        self.c = container
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 8, 16, 16)
        items = self.c.people_repo.items_for(name)
        root.addWidget(SectionHeader(name, f"{len(items)} titles in your library"))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        root.addWidget(scroll, 1)
        if not items:
            scroll.setWidget(EmptyState("Not found", f"“{name}” is not in the people index."))
            return
        host = QWidget()
        from ui.components.cards import MediaCard

        flow = FlowLayout(host)
        for item in items:
            card = MediaCard(self.c, item)
            card.openRequested.connect(self.c.open_media)
            flow.addWidget(card)
        scroll.setWidget(host)
