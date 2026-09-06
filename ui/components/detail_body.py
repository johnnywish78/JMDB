"""DetailBody: overview, facts, cast, files, and lists for detail screens."""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ui.app.context import asset_path
from ui.components.person_card import PersonCard


def _fact_row(label: str, value: str) -> QWidget:
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 2, 0, 2)
    name = QLabel(label)
    name.setObjectName("MutedLabel")
    name.setFixedWidth(120)
    layout.addWidget(name)
    text = QLabel(value or "—")
    text.setWordWrap(True)
    layout.addWidget(text, 1)
    return row


def _section_title(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("SectionHeader")
    return label


class DetailBody(QWidget):
    person_clicked = pyqtSignal(int)
    add_to_collection = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        self.layout_ref = layout

    def _clear(self) -> None:
        while self.layout_ref.count():
            item = self.layout_ref.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                while item.layout().count():
                    sub = item.layout().takeAt(0)
                    if sub.widget():
                        sub.widget().deleteLater()

    # -- movie -----------------------------------------------------------------
    def set_movie(self, detail: dict, context) -> None:
        self._clear()
        layout = self.layout_ref
        # overview
        if detail.get("overview"):
            layout.addWidget(_section_title("Overview"))
            overview = QLabel(detail["overview"])
            overview.setWordWrap(True)
            overview.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            layout.addWidget(overview)

        # facts grid
        facts = QWidget()
        facts_layout = QGridLayout(facts)
        facts_layout.setContentsMargins(0, 0, 0, 0)
        facts_layout.setSpacing(10)
        column = 0
        fact_pairs = [
            ("Genres", ", ".join(detail.get("genres", []))),
            ("Released", detail.get("release_date") or ""),
            ("Runtime", f"{detail['runtime_seconds'] // 60} min" if detail.get("runtime_seconds") else ""),
            ("Certification", detail.get("certification") or ""),
            ("Original title", detail.get("original_title") or ""),
            ("Languages", detail.get("languages") or ""),
            ("Countries", detail.get("countries") or ""),
            ("Studios", ", ".join(detail.get("studios", []))),
            ("Your rating", f"{detail['user_rating']:.0f}/10" if detail.get("user_rating") else "not rated"),
        ]
        ext = detail.get("external_ids", {})
        if ext.get("imdb"):
            fact_pairs.append(("IMDb", f"tt-linked · {ext['imdb']}"))
        providers = [k for k in ext if k not in ("trailer",)]
        if providers:
            fact_pairs.append(("Metadata sources", ", ".join(sorted(providers))))
        for i, (label, value) in enumerate(fact_pairs):
            facts_layout.addWidget(_fact_row(label, value), i, column)
        layout.addWidget(facts)

        # trailer link
        if detail.get("trailer_url"):
            trailer_button = QPushButton("▶ Watch trailer (opens browser)")
            trailer_button.setObjectName("FlatIconButton")
            trailer_button.clicked.connect(
                lambda: self._open_external(detail["trailer_url"])
            )
            layout.addWidget(trailer_button)

        # franchise
        if detail.get("franchise"):
            layout.addWidget(_section_title(f"Collection: {detail['franchise']['name']}"))
            posters = QWidget()
            posters_layout = QHBoxLayout(posters)
            for movie in detail.get("franchise_movies", [])[:8]:
                from ui.components.poster_card import PosterCard

                card = PosterCard(movie)
                card.clicked.connect(
                    lambda data: context.router.navigate("movie_detail", movie_id=data["id"])
                )
                self._load_card_art(context, card, movie)
                posters_layout.addWidget(card)
            layout.addWidget(posters)

        # cast & crew
        credits = detail.get("credits", [])
        if credits:
            layout.addWidget(_section_title("Cast & Crew"))
            cast_row = QWidget()
            cast_layout = QHBoxLayout(cast_row)
            cast_layout.setContentsMargins(0, 0, 0, 0)
            cast_layout.setSpacing(10)
            for credit in credits[:16]:
                card = PersonCard(credit)
                card.clicked.connect(self.person_clicked.emit)
                self._load_person_art(context, card, credit)
                cast_layout.addWidget(card)
            cast_layout.addStretch(1)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QScrollArea.Shape.NoFrame)
            scroll.setFixedHeight(230)
            scroll.setWidget(cast_row)
            layout.addWidget(scroll)

        # files
        layout.addWidget(_section_title("Files"))
        for media_file in detail.get("files", []):
            size_mb = media_file.get("size_bytes", 0) / (1024 * 1024)
            layout.addWidget(
                _fact_row(
                    f".{media_file.get('container', '?')}",
                    f"{media_file['path']}  ({size_mb:.0f} MB)",
                )
            )
        if not detail.get("files"):
            layout.addWidget(QLabel("No file linked (missing or never scanned)."))

        add_collection = QPushButton("＋ Add to collection")
        add_collection.clicked.connect(self.add_to_collection.emit)
        layout.addWidget(add_collection)
        layout.addStretch(1)

    def _load_card_art(self, context, card, row: dict) -> None:
        def handler(key, pixmap, card=card):
            card.set_pixmap(pixmap)
            try:
                context.images.ready.disconnect(handler)
            except TypeError:
                pass

        context.images.ready.connect(handler)
        context.images.request(f"body-{id(card)}", row.get("poster_path", ""), 360)

    def _load_person_art(self, context, card: PersonCard, credit: dict) -> None:
        def handler(key, pixmap, card=card):
            card.set_pixmap(pixmap)
            try:
                context.images.ready.disconnect(handler)
            except TypeError:
                pass

        context.images.ready.connect(handler)
        context.images.request(
            f"person-{credit.get('person_id')}-{id(card)}", credit.get("photo_path", ""), 240
        )

    @staticmethod
    def _open_external(url: str) -> None:
        from app.browser.engine import open_in_system_browser

        open_in_system_browser(url)
