"""TV show detail: seasons overview, next episode, cast."""
from __future__ import annotations

import logging

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget

from app.domain.events import MetadataUpdated
from ui.components.detail_hero import DetailHero
from ui.components.states import EmptyState
from ui.screens.base import Screen

logger = logging.getLogger(__name__)


class ShowDetailScreen(Screen):
    title = "TV Show"

    def __init__(self, context, parent=None) -> None:
        super().__init__(context, parent)
        self.show_id = None
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.root.addWidget(self.scroll, 1)
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setSpacing(16)
        self.scroll.setWidget(self.content)
        context.subscribe(MetadataUpdated, self._on_metadata_updated)

    def enter(self, show_id: int = 0, **params) -> None:
        self.show_id = show_id

    def refresh(self) -> None:
        if self.show_id is None:
            return

        def work():
            return self.context.services.tv.show_detail(
                self.show_id, self.context.profile_id
            )

        from ui.app.context import run_async

        run_async(work, self._populate)

    def _on_metadata_updated(self, event) -> None:
        if event.media_type == "tv_show" and event.media_id == self.show_id:
            self.refresh()

    def _populate(self, detail: dict | None) -> None:
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if detail is None:
            self.content_layout.addWidget(EmptyState("Show not found"))
            return

        hero = DetailHero()
        hero.set_show(detail)
        hero.play_clicked.connect(lambda: self._play_next(detail))
        hero.refresh_clicked.connect(lambda: self._refresh_metadata(detail["id"]))
        hero.favorite_toggled.connect(lambda on: self._toggle("favorite", detail, on))
        hero.watchlist_toggled.connect(lambda on: self._toggle("watchlist", detail, on))
        self.content_layout.addWidget(hero)

        # overview + facts
        from ui.components.detail_body import _fact_row, _section_title

        if detail.get("overview"):
            self.content_layout.addWidget(_section_title("Overview"))
            overview = QLabel(detail["overview"])
            overview.setWordWrap(True)
            self.content_layout.addWidget(overview)

        progress = QLabel(
            f"{detail['watched_count']} / {detail['episode_count']} episodes watched"
        )
        progress.setObjectName("SectionHeader")
        self.content_layout.addWidget(progress)

        from ui.components.detail_body import DetailBody

        facts = QWidget()
        facts_layout = QVBoxLayout(facts)
        facts_layout.setContentsMargins(0, 0, 0, 0)
        for label, value in (
            ("First aired", detail.get("first_air_date") or ""),
            ("Last aired", detail.get("last_air_date") or ""),
            ("Status", detail.get("status") or ""),
            ("Genres", ", ".join(detail.get("genres", []))),
            ("Networks", ", ".join(detail.get("networks", []))),
            ("Studios", ", ".join(detail.get("studios", []))),
            ("Rating", f"★ {detail['rating']:.1f}" if detail.get("rating") else ""),
        ):
            facts_layout.addWidget(_fact_row(label, value))
        self.content_layout.addWidget(facts)

        # seasons
        self.content_layout.addWidget(_section_title("Seasons"))
        from ui.components.season_card import SeasonCard

        for season in detail["seasons"]:
            card = SeasonCard(season)
            card.open_requested.connect(
                lambda season_id=season["id"]: self.context.router.navigate(
                    "season_detail", season_id=season_id
                )
            )
            card.mark_watched.connect(
                lambda season_id=season["id"]: self._mark_season_watched(season_id)
            )
            self._load_season_art(card, season)
            self.content_layout.addWidget(card)

        # cast
        if detail.get("credits"):
            self.content_layout.addWidget(_section_title("Cast"))
            cast_row = QWidget()
            from PyQt6.QtWidgets import QHBoxLayout

            cast_layout = QHBoxLayout(cast_row)
            cast_layout.setContentsMargins(0, 0, 0, 0)
            from ui.components.person_card import PersonCard

            for credit in detail["credits"][:16]:
                person = PersonCard(credit)
                person.clicked.connect(
                    lambda pid: self.context.router.navigate("person_detail", person_id=pid)
                )
                self._load_person_art(person, credit)
                cast_layout.addWidget(person)
            cast_layout.addStretch(1)
            self.content_layout.addWidget(cast_row)
        self.content_layout.addStretch(1)

    def _load_season_art(self, card, season: dict) -> None:
        context = self.context

        def handler(key, pixmap, card=card):
            card.set_pixmap(pixmap)
            try:
                context.images.ready.disconnect(handler)
            except TypeError:
                pass

        context.images.ready.connect(handler)
        context.images.request(
            f"season-{season['id']}-{id(card)}",
            season.get("poster_path") or season.get("show_poster_path", ""),
            400,
        )

    def _load_person_art(self, card, credit: dict) -> None:
        context = self.context

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

    # -- actions -------------------------------------------------------------------
    def _play_next(self, detail: dict) -> None:
        svc = self.context.services
        next_episode = detail.get("next_episode")
        if next_episode and next_episode.get("id"):
            playable = svc.tv.playable(next_episode["id"])
            if playable:
                self.context.open_player(playable)
                return
        self.context.toast("No unwatched episode with a file found", "warning")

    def _refresh_metadata(self, show_id: int) -> None:
        from ui.app.context import run_async

        self.context.toast("Refreshing show metadata…")

        def work():
            return self.context.services.metadata.enrich_show(show_id, force=True)

        def done(ok):
            self.context.toast(
                "Show metadata refreshed" if ok else "No metadata found", "success" if ok else "warning"
            )
            self.refresh()

        run_async(work, done)

    def _toggle(self, kind: str, detail: dict, on: bool) -> None:
        lists = self.context.services.repos.lists
        if kind == "favorite":
            lists.set_favorite(self.context.profile_id, "tv_show", detail["id"], on)
        else:
            lists.set_watchlist(self.context.profile_id, "tv_show", detail["id"], on)
        self.refresh()

    def _mark_season_watched(self, season_id: int) -> None:
        count = self.context.services.playback.mark_season_watched(
            self.context.profile_id, season_id
        )
        self.context.toast(f"Marked {count} episodes watched", "success")
        self.refresh()
