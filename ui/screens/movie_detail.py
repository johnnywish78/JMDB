"""Movie detail screen: real metadata, cast, files, actions."""
from __future__ import annotations

import logging

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.domain.events import MetadataUpdated
from ui.components.dialogs import confirm, text_input
from ui.components.metadata_badges import BadgeRow
from ui.components.person_card import PersonCard
from ui.screens.base import Screen

logger = logging.getLogger(__name__)


class MovieDetailScreen(Screen):
    title = "Movie"

    def __init__(self, context, parent=None) -> None:
        super().__init__(context, parent)
        self.movie_id = None
        self.back_button = None
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.root.addWidget(self.scroll, 1)
        self.content = QWidget()
        self.scroll.setWidget(self.content)
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(16)
        context.subscribe(MetadataUpdated, self._on_metadata_updated)

    def enter(self, movie_id: int = 0, **params) -> None:
        self.movie_id = movie_id

    def refresh(self) -> None:
        if self.movie_id is None:
            return

        def work():
            return self.context.services.movies.detail(
                self.movie_id, self.context.profile_id
            )

        from ui.app.context import run_async

        run_async(work, self._populate)

    def _on_metadata_updated(self, event) -> None:
        if event.media_type == "movie" and event.media_id == self.movie_id:
            self.refresh()

    # -- build -----------------------------------------------------------------
    def _populate(self, detail: dict | None) -> None:
        from ui.app.context import run_async
        from ui.components.states import EmptyState

        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if detail is None:
            self.content_layout.addWidget(EmptyState("Movie not found"))
            return

        from ui.components.detail_hero import DetailHero
        from ui.components.detail_body import DetailBody

        hero = DetailHero()
        hero.set_movie(detail)
        hero.play_clicked.connect(lambda: self._play(detail))
        hero.refresh_clicked.connect(lambda: self._refresh_metadata(detail["id"]))
        hero.favorite_toggled.connect(lambda on: self._toggle_favorite(detail, on))
        hero.watchlist_toggled.connect(lambda on: self._toggle_watchlist(detail, on))
        hero.watched_toggled.connect(lambda on: self._toggle_watched(detail, on))
        self.content_layout.addWidget(hero)

        body = DetailBody()
        body.set_movie(detail, self.context)
        body.person_clicked.connect(self._open_person)
        body.add_to_collection.connect(lambda: self._add_to_collection(detail))
        self.content_layout.addWidget(body)
        run_async(lambda: self._load_art_paths(detail), hero.apply_backdrop)

    def _load_art_paths(self, detail: dict) -> tuple:
        return detail.get("backdrop_path") or "", detail.get("poster_path") or ""

    # -- actions --------------------------------------------------------------------
    def _play(self, detail: dict) -> None:
        svc = self.context.services
        playable = svc.movies.playable(detail["id"])
        if playable is None:
            self.context.toast("No playable file linked to this movie", "warning")
            return
        resume = svc.playback.resume.resume_position(
            self.context.profile_id, "movie", detail["id"]
        )
        if resume and resume > 10:
            from PyQt6.QtWidgets import QMessageBox

            answer = QMessageBox.question(
                self,
                "Resume playback?",
                f"Resume from {int(resume // 60)}:{int(resume % 60):02d} or start over?",
                QMessageBox.StandardButton.Resume | QMessageBox.StandardButton.No,
            )
            if answer == QMessageBox.StandardButton.No:
                # player auto-resumes from the saved position; clear it to
                # honor "start over"
                svc.playback.resume.clear(
                    self.context.profile_id, "movie", detail["id"]
                )
        self.context.open_player(playable)

    def _refresh_metadata(self, movie_id: int) -> None:
        from ui.app.context import run_async

        self.context.toast("Refreshing metadata…")

        def work():
            return self.context.services.metadata.enrich_movie(
                movie_id, force=True, profile_id=self.context.profile_id
            )

        def done(ok):
            if ok:
                self.context.toast("Metadata refreshed", "success")
            else:
                self.context.toast(
                    "No metadata found (check provider keys in Settings)", "warning"
                )
            self.refresh()

        run_async(work, done)

    def _toggle_favorite(self, detail: dict, on: bool) -> None:
        self.context.services.repos.lists.set_favorite(
            self.context.profile_id, "movie", detail["id"], on
        )
        self.refresh()

    def _toggle_watchlist(self, detail: dict, on: bool) -> None:
        self.context.services.repos.lists.set_watchlist(
            self.context.profile_id, "movie", detail["id"], on
        )
        self.refresh()

    def _toggle_watched(self, detail: dict, on: bool) -> None:
        if on:
            self.context.services.playback.mark_watched(
                self.context.profile_id, "movie", detail["id"]
            )
        else:
            self.context.services.playback.mark_unwatched(
                self.context.profile_id, "movie", detail["id"]
            )
        self.refresh()

    def _open_person(self, person_id: int) -> None:
        self.context.router.navigate("person_detail", person_id=person_id)

    def _add_to_collection(self, detail: dict) -> None:
        collections = self.context.services.collections.list()
        names = [c["name"] for c in collections] + ["+ New collection…"]
        from PyQt6.QtWidgets import QInputDialog

        choice, ok = QInputDialog.getItem(
            self, "Add to collection", "Collection:", names, 0, False
        )
        if not ok:
            return
        try:
            if choice == "+ New collection…":
                name, ok = text_input(self, "New collection", "Name:")
                if not ok or not name.strip():
                    return
                collection = self.context.services.collections.create(name)
            else:
                collection = next(c for c in collections if c["name"] == choice)
            self.context.services.collections.add(collection["id"], "movie", detail["id"])
            self.context.toast(f"Added to {collection['name']}", "success")
        except ValueError as exc:
            self.context.toast(str(exc), "warning")
