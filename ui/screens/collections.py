"""Collections: list, create, rename, delete, open, reorder."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.components.dialogs import confirm, text_input
from ui.components.states import EmptyState
from ui.screens.base import Screen


class CollectionsScreen(Screen):
    title = "Collections"

    def __init__(self, context, parent=None) -> None:
        super().__init__(context, parent)
        self.header = QLabel("Collections")
        self.header.setObjectName("ScreenTitle")
        self.root.addWidget(self.header)

        body = QHBoxLayout()
        self.list = QListWidget()
        self.list.setMinimumWidth(280)
        self.list.itemSelectionChanged.connect(self._open_selected)
        body.addWidget(self.list)

        self.detail_container = QWidget()
        self.detail_layout = QVBoxLayout(self.detail_container)
        self.detail_title = QLabel("")
        self.detail_title.setObjectName("SectionHeader")
        self.detail_layout.addWidget(self.detail_title)
        self.items_label = QLabel("")
        self.items_label.setObjectName("MutedLabel")
        self.detail_layout.addWidget(self.items_label)
        self.items_list = QListWidget()
        self.items_list.itemDoubleClicked.connect(self._open_item)
        self.detail_layout.addWidget(self.items_list, 1)

        buttons = QHBoxLayout()
        new_button = QPushButton("＋ New collection")
        new_button.setObjectName("PrimaryButton")
        new_button.clicked.connect(self._create)
        rename_button = QPushButton("Rename")
        rename_button.clicked.connect(self._rename)
        delete_button = QPushButton("Delete")
        delete_button.setObjectName("DangerButton")
        delete_button.clicked.connect(self._delete)
        up_button = QPushButton("Move up")
        up_button.clicked.connect(lambda: self._move(-1))
        down_button = QPushButton("Move down")
        down_button.clicked.connect(lambda: self._move(1))
        remove_item_button = QPushButton("Remove selected item")
        remove_item_button.clicked.connect(self._remove_selected_item)
        for button in (new_button, rename_button, delete_button, up_button, down_button, remove_item_button):
            buttons.addWidget(button)
        self.detail_layout.addLayout(buttons)
        body.addWidget(self.detail_container, 1)
        self.root.addLayout(body, 1)

        self.empty_state = EmptyState(
            "No collections yet",
            "Create collections like 'Marvel', 'Oscar winners', or 'Christmas movies'.",
            "Create collection",
        )
        self.empty_state.action.connect(self._create)
        self.root.addWidget(self.empty_state)
        self._current_collection = None

    def refresh(self) -> None:
        collections = self.context.services.collections.list()
        self.empty_state.setVisible(not collections)
        self.list.setVisible(bool(collections))
        self.detail_container.setVisible(bool(collections))
        self.list.blockSignals(True)
        self.list.clear()
        for collection in collections:
            item = QListWidgetItem(f"{collection['name']}  ({collection['item_count']})")
            item.setData(Qt.ItemDataRole.UserRole, collection["id"])
            self.list.addItem(item)
        self.list.blockSignals(False)
        if self._current_collection:
            for i in range(self.list.count()):
                if self.list.item(i).data(Qt.ItemDataRole.UserRole) == self._current_collection:
                    self.list.setCurrentRow(i)
                    break
        self._load_items()

    def _open_selected(self) -> None:
        item = self.list.currentItem()
        if item is None:
            return
        self._current_collection = item.data(Qt.ItemDataRole.UserRole)
        self._load_items()

    def _load_items(self) -> None:
        self.items_list.clear()
        if self._current_collection is None:
            return
        collection = self.context.services.collections
        info = collection.items(self._current_collection)
        meta = next(
            (c for c in collection.list() if c["id"] == self._current_collection), None
        )
        self.detail_title.setText(meta["name"] if meta else "")
        self.items_label.setText(meta["description"] if meta else "")
        for entry in info:
            type_label = {
                "movie": "Movie", "tv_show": "TV", "artist": "Artist", "album": "Album"
            }.get(entry["media_type"], entry["media_type"])
            item = QListWidgetItem(
                f"{entry.get('title', '')} ({entry.get('year') or '—'}) · {type_label}"
            )
            item.setData(Qt.ItemDataRole.UserRole, entry)
            self.items_list.addItem(item)

    def _create(self) -> None:
        name, ok = text_input(self, "New collection", "Collection name:")
        if not ok or not name.strip():
            return
        try:
            collection = self.context.services.collections.create(name.strip())
            self._current_collection = collection.id
            self.context.toast(f"Created {collection.name}", "success")
        except ValueError as exc:
            self.context.toast(str(exc), "warning")
        self.refresh()

    def _rename(self) -> None:
        if self._current_collection is None:
            return
        meta = next(
            (c for c in self.context.services.collections.list()
             if c["id"] == self._current_collection), None
        )
        if meta is None:
            return
        name, ok = text_input(self, "Rename collection", "New name:", meta["name"])
        if not ok or not name.strip():
            return
        try:
            self.context.services.collections.rename(self._current_collection, name.strip())
            self.context.toast("Renamed", "success")
        except ValueError as exc:
            self.context.toast(str(exc), "warning")
        self.refresh()

    def _delete(self) -> None:
        if self._current_collection is None:
            return
        if confirm(self, "Delete collection", "Delete this collection? Items stay in your library."):
            self.context.services.collections.delete(self._current_collection)
            self._current_collection = None
            self.context.toast("Collection deleted", "success")
            self.refresh()

    def _move(self, delta: int) -> None:
        row = self.items_list.currentRow()
        if row < 0 or self._current_collection is None:
            return
        new_row = row + delta
        if not 0 <= new_row < self.items_list.count():
            return
        entries = [
            self.items_list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.items_list.count())
        ]
        entries[row], entries[new_row] = entries[new_row], entries[row]
        self.context.services.collections.reorder(
            self._current_collection,
            [(entry["media_type"], entry["media_id"]) for entry in entries],
        )
        self.refresh()
        self.items_list.setCurrentRow(new_row)

    def _remove_selected_item(self) -> None:
        item = self.items_list.currentItem()
        if item is None or self._current_collection is None:
            return
        entry = item.data(Qt.ItemDataRole.UserRole)
        self.context.services.collections.remove(
            self._current_collection, entry["media_type"], entry["media_id"]
        )
        self.refresh()

    def _open_item(self, item) -> None:
        entry = item.data(Qt.ItemDataRole.UserRole)
        router = self.context.router
        if entry["media_type"] == "movie":
            router.navigate("movie_detail", movie_id=entry["media_id"])
        elif entry["media_type"] == "tv_show":
            router.navigate("show_detail", show_id=entry["media_id"])
        elif entry["media_type"] == "album":
            router.navigate("music_detail", album_id=entry["media_id"])
