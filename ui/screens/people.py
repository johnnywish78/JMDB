"""People screen: grid of people in the library."""
from __future__ import annotations

from PyQt6.QtWidgets import QGridLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from ui.components.person_card import PersonCard
from ui.components.states import EmptyState
from ui.screens.base import Screen


class PeopleScreen(Screen):
    title = "People"

    def __init__(self, context, parent=None) -> None:
        super().__init__(context, parent)
        self.header = QLabel("People")
        self.header.setObjectName("ScreenTitle")
        self.root.addWidget(self.header)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.root.addWidget(self.scroll, 1)
        self.container = QWidget()
        self.grid = QGridLayout(self.container)
        self.grid.setSpacing(12)
        self.scroll.setWidget(self.container)
        self.empty_state = EmptyState(
            "No people yet",
            "People appear after metadata is fetched for your movies and shows.",
        )
        self.empty_state.setVisible(False)
        self.root.addWidget(self.empty_state)
        self._page = 0

    def refresh(self) -> None:
        from ui.app.context import run_async

        def work():
            return self.context.services.people.list_page(0, 120)

        run_async(work, self._populate)

    def _populate(self, result) -> None:
        rows, total = result
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.empty_state.setVisible(not rows)
        self.scroll.setVisible(bool(rows))
        self.header.setText(f"People ({total})")
        columns = max(1, (max(500, self.width()) - 60) // 140)
        for index, person in enumerate(rows):
            card = PersonCard(person)
            card.clicked.connect(
                lambda pid: self.context.router.navigate("person_detail", person_id=pid)
            )
            self._load_photo(card, person)
            self.grid.addWidget(card, index // columns, index % columns)

    def _load_photo(self, card: PersonCard, person: dict) -> None:
        context = self.context

        def handler(key, pixmap, card=card):
            card.set_pixmap(pixmap)
            try:
                context.images.ready.disconnect(handler)
            except TypeError:
                pass

        context.images.ready.connect(handler)
        context.images.request(f"people-{person['id']}-{id(card)}", person.get("photo_path", ""), 240)
