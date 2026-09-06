"""Screen base classes: Screen and the lazy-loading GridScreen."""
from __future__ import annotations

import logging

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QGridLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ui.components.states import EmptyState
from ui.components.poster_card import PosterCard

logger = logging.getLogger(__name__)


class Screen(QWidget):
    """Base class for all JMDB screens."""

    title = "JMDB"

    def __init__(self, context, parent=None) -> None:
        super().__init__(parent)
        self.context = context
        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(24, 18, 24, 18)
        self.root.setSpacing(14)

    def enter(self, **params) -> None:
        """Called with navigation parameters."""

    def refresh(self) -> None:
        """Reload data from services (never from cached widgets)."""


class GridScreen(Screen):
    """Scrollable poster grid with server-side pagination (lazy loading).

    Subclasses implement :meth:`fetch_page` returning (rows, total).
    """

    card_clicked = pyqtSignal(dict)
    empty_action_text = ""
    empty_hint = ""

    def __init__(self, context, parent=None) -> None:
        super().__init__(context, parent)
        self._page = 0
        self._per_page = 60
        self._total = -1
        self._loading = False
        self._rows: list[dict] = []
        self._art_handlers: list = []

        self.header = QLabel(self.title)
        self.header.setObjectName("ScreenTitle")
        self.root.addWidget(self.header)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.root.addWidget(self.scroll, 1)

        self.container = QWidget()
        self.grid = QGridLayout(self.container)
        self.grid.setSpacing(14)
        self.grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.scroll.setWidget(self.container)
        self.scroll.verticalScrollBar().rangeChanged.connect(self._check_fill)
        self.scroll.verticalScrollBar().valueChanged.connect(self._maybe_load_more)

        self.empty_state = EmptyState(
            getattr(self, "empty_message", "Nothing here yet"),
            self.empty_hint,
            self.empty_action_text,
        )
        self.empty_state.setVisible(False)
        self.root.addWidget(self.empty_state)

    # -- data -----------------------------------------------------------------
    def fetch_page(self, page: int, per_page: int) -> tuple[list[dict], int]:
        raise NotImplementedError

    def refresh(self) -> None:
        self._page = 0
        self._total = -1
        self._loading = False
        self._rows = []
        self._clear_grid()
        self._load_next_page()

    def _clear_grid(self) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _load_next_page(self) -> None:
        if self._loading:
            return
        if self._total >= 0 and len(self._rows) >= self._total:
            self._update_empty()
            return
        self._loading = True

        def work(page=self._page):
            return self.fetch_page(page, self._per_page)

        def done(result):
            rows, total = result
            self._loading = False
            self._page += 1
            self._total = total
            self._rows.extend(rows)
            self._append_cards(rows)
            self._update_empty()

        from ui.app.context import run_async

        run_async(work, done)

    # -- cards -------------------------------------------------------------------
    def make_card(self, row: dict) -> PosterCard:
        return PosterCard(row, width=int(self.context.services.settings.get("poster_card_width")))

    def _append_cards(self, rows: list[dict]) -> None:
        card_width = int(self.context.services.settings.get("poster_card_width"))
        columns = max(1, (max(400, self.scroll.width()) - 40) // (card_width + 24))
        for row in rows:
            card = self.make_card(row)
            card.clicked.connect(self._on_card_clicked)
            self._request_art(card, row)
            index = self.grid.count()
            self.grid.addWidget(card, index // columns, index % columns)
        self._check_fill()

    def _request_art(self, card: PosterCard, row: dict) -> None:
        path = row.get("poster_path") or row.get("still_path") or row.get("cover_path") or ""
        key = f"card-{row.get('id')}-{id(card)}"
        handler = self._make_art_handler(key, card)
        self._art_handlers.append(handler)
        self.context.images.ready.connect(handler)
        self.context.images.request(key, path, int(self.context.services.settings.get("poster_card_width")) * 2)

    def _make_art_handler(self, key: str, card: PosterCard):
        def handler(delivered_key: str, pixmap):
            if delivered_key == key:
                card.set_pixmap(pixmap)
                try:
                    self.context.images.ready.disconnect(handler)
                except TypeError:
                    pass
                if handler in self._art_handlers:
                    self._art_handlers.remove(handler)

        return handler

    def _on_card_clicked(self, data: dict) -> None:
        self.card_clicked.emit(data)

    # -- scrolling -----------------------------------------------------------------
    def _maybe_load_more(self, value: int) -> None:
        bar = self.scroll.verticalScrollBar()
        if bar.maximum() - value < 400:
            self._load_next_page()

    def _check_fill(self, *args) -> None:
        bar = self.scroll.verticalScrollBar()
        if bar.maximum() <= bar.minimum() and not self._loading:
            if self._total < 0 or len(self._rows) < self._total:
                self._load_next_page()

    def _update_empty(self) -> None:
        has_data = bool(self._rows)
        self.empty_state.setVisible(not has_data)
        self.scroll.setVisible(has_data)
