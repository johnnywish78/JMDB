"""Playback history screen."""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QTableWidget,
    QTableWidgetItem,
    QLabel,
)

from ui.components.states import EmptyState
from ui.screens.base import Screen


class HistoryScreen(Screen):
    title = "History"

    def __init__(self, context, parent=None) -> None:
        super().__init__(context, parent)
        self.header = QLabel("Watch History")
        self.header.setObjectName("ScreenTitle")
        self.root.addWidget(self.header)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["When", "Title", "Type", "Position", "Completed"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.cellDoubleClicked.connect(self._open_entry)
        self.root.addWidget(self.table, 1)
        self.empty_state = EmptyState(
            "Nothing played yet",
            "Your playback sessions will be listed here.",
        )
        self.empty_state.setVisible(False)
        self.root.addWidget(self.empty_state)

    def refresh(self) -> None:
        from ui.app.context import run_async

        def work():
            return self.context.services.playback.history.list(self.context.profile_id, 200)

        run_async(work, self._populate)

    def _populate(self, rows: list[dict]) -> None:
        self.empty_state.setVisible(not rows)
        self.table.setVisible(bool(rows))
        self.table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            started = (row.get("started_at") or "").replace("T", " ")[:19]
            values = [
                started,
                row.get("title", ""),
                row.get("media_type", ""),
                f"{int(row.get('position_seconds') or 0) // 60} min",
                "✓" if row.get("completed") else "",
            ]
            for column, value in enumerate(values):
                self.table.setItem(index, column, QTableWidgetItem(value))
        self.table.resizeColumnsToContents()

    def _open_entry(self, row: int, _column: int) -> None:
        entries = self.context.services.playback.history.list(self.context.profile_id, 200)
        if row < len(entries):
            entry = entries[row]
            router = self.context.router
            if entry["media_type"] == "movie":
                router.navigate("movie_detail", movie_id=entry["media_id"])
            elif entry["media_type"] == "episode":
                router.navigate("episode_detail", episode_id=entry["media_id"])
