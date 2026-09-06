"""Person detail: bio, known for, filmography."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from ui.components.states import EmptyState
from ui.components.poster_card import PosterCard
from ui.screens.base import Screen


class PersonDetailScreen(Screen):
    title = "Person"

    def __init__(self, context, parent=None) -> None:
        super().__init__(context, parent)
        self.person_id = None
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.root.addWidget(self.scroll, 1)
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setSpacing(14)
        self.scroll.setWidget(self.content)

    def enter(self, person_id: int = 0, **params) -> None:
        self.person_id = person_id

    def refresh(self) -> None:
        if self.person_id is None:
            return

        def work():
            return self.context.services.people.person_detail(
                self.person_id, self.context.profile_id
            )

        from ui.app.context import run_async

        run_async(work, self._populate)

    def _populate(self, detail: dict | None) -> None:
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if detail is None:
            self.content_layout.addWidget(EmptyState("Person not found"))
            return

        header = QWidget()
        header_layout = QHBoxLayout(header)
        self.photo = QLabel()
        self.photo.setFixedSize(150, 225)
        self.photo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.photo.setStyleSheet("border-radius: 8px; background: #2a3040;")
        header_layout.addWidget(self.photo)
        info = QVBoxLayout()
        name = QLabel(detail["name"])
        name.setObjectName("ScreenTitle")
        name.setWordWrap(True)
        info.addWidget(name)
        from ui.components.detail_body import _fact_row

        for label, value in (
            ("Known for", ", ".join(sorted({entry["role"] for entry in detail["filmography"]}))[:60]),
            ("Born", detail.get("birthday") or ""),
            ("Died", detail.get("deathday") or ""),
            ("From", detail.get("place_of_birth") or ""),
            ("Credits", str(detail["credit_count"])),
        ):
            info.addWidget(_fact_row(label, value))
        ext = detail.get("external_ids", {})
        if ext.get("imdb"):
            from PyQt6.QtWidgets import QPushButton

            imdb_button = QPushButton("Open IMDb page")
            imdb_button.clicked.connect(
                lambda: self._open_imdb(ext["imdb"])
            )
            info.addWidget(imdb_button)
        info.addStretch(1)
        header_layout.addLayout(info, 1)
        self.content_layout.addWidget(header)
        self._load_photo()

        if detail.get("biography"):
            from ui.components.detail_body import _section_title

            self.content_layout.addWidget(_section_title("Biography"))
            bio = QLabel(detail["biography"])
            bio.setWordWrap(True)
            self.content_layout.addWidget(bio)

        if detail.get("known_for"):
            from ui.components.detail_body import _section_title

            self.content_layout.addWidget(_section_title("Known for"))
            row = QWidget()
            row_layout = QHBoxLayout(row)
            for entry in detail["known_for"]:
                card = PosterCard(
                    {"id": entry["media_id"], "title": entry["media_title"], "year": entry.get("media_year")},
                    width=140,
                )
                card.clicked.connect(lambda data, et=entry["media_type"]: self._open_media(et, data["id"]))
                self._load_card_art(card, entry)
                row_layout.addWidget(card)
            row_layout.addStretch(1)
            self.content_layout.addWidget(row)

        if detail.get("filmography"):
            from ui.components.detail_body import _section_title

            self.content_layout.addWidget(_section_title("Filmography"))
            from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem

            table = QTableWidget(len(detail["filmography"]), 3)
            table.setHorizontalHeaderLabels(["Year", "Title", "As"])
            table.verticalHeader().setVisible(False)
            table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
            for row_index, entry in enumerate(detail["filmography"]):
                year_item = QTableWidgetItem(str(entry.get("media_year") or ""))
                title_item = QTableWidgetItem(str(entry.get("media_title") or ""))
                role = entry.get("character") or entry.get("job") or entry.get("role", "")
                as_item = QTableWidgetItem(str(role))
                table.setItem(row_index, 0, year_item)
                table.setItem(row_index, 1, title_item)
                table.setItem(row_index, 2, as_item)
            table.cellDoubleClicked.connect(
                lambda r, _c: self._open_media(
                    detail["filmography"][r]["media_type"],
                    detail["filmography"][r]["media_id"],
                )
            )
            table.resizeColumnsToContents()
            self.content_layout.addWidget(table)
        self.content_layout.addStretch(1)

    def _load_photo(self) -> None:
        detail_url = ""
        # photo loaded via service result; fetch again from repo
        person = self.context.services.repos.people.get(self.person_id)
        if person is not None:
            detail_url = self.context.services.repos.artwork.local_path(
                "person", self.person_id, "profile"
            )
        context = self.context

        def handler(key, pixmap):
            self.photo.setPixmap(
                pixmap.scaled(
                    self.photo.size(),
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )

        if detail_url:
            context.images.ready.connect(handler)
            context.images.request(f"person-detail-{self.person_id}", detail_url, 300)
        else:
            self.photo.setText("👤")

    def _load_card_art(self, card: PosterCard, entry: dict) -> None:
        context = self.context

        def handler(key, pixmap, card=card):
            card.set_pixmap(pixmap)
            try:
                context.images.ready.disconnect(handler)
            except TypeError:
                pass

        context.images.ready.connect(handler)
        context.images.request(f"person-film-{id(card)}", entry.get("poster_path", ""), 300)

    def _open_media(self, media_type: str, media_id: int) -> None:
        if media_type == "movie":
            self.context.router.navigate("movie_detail", movie_id=media_id)
        elif media_type in ("tv_show", "episode"):
            show_id = media_id
            if media_type == "episode":
                episode = self.context.services.repos.tv.get_episode(media_id)
                show_id = episode.tv_show_id if episode else media_id
            self.context.router.navigate("show_detail", show_id=show_id)

    def _open_imdb(self, imdb_id: str) -> None:
        from app.metadata.providers.imdb import imdb_name_url
        from app.browser.engine import open_in_system_browser

        ok, info = open_in_system_browser(imdb_name_url(imdb_id))
        if not ok:
            self.context.toast("Could not open browser", "warning")
