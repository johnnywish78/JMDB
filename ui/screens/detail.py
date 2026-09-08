"""Detail screen for a movie or show: header, actions, rating, cast, episodes."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.domain.value_objects import human_minutes
from ui.components.common import EmptyState, SectionHeader


class DetailScreen(QWidget):
    """params: media_id=int"""

    def __init__(self, container, media_id: int = 0, parent=None):
        super().__init__(parent)
        self.c = container
        self.media_id = int(media_id)
        self.item = self.c.media_repo.get(self.media_id)
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 8, 16, 16)
        if not self.item:
            root.addWidget(EmptyState("Not found", "This title is not in the library."))
            return
        self.root = root
        self._header()
        self._cast()
        if self.item["kind"] == "show":
            self._episodes_section()
        root.addStretch(1)

    # --------------------------------------------------------------- header
    def _header(self) -> None:
        item = self.item
        box = QWidget()
        box.setObjectName("Panel")
        hb = QHBoxLayout(box)
        hb.setContentsMargins(18, 18, 18, 18)
        hb.setSpacing(20)

        poster = QLabel()
        poster.setFixedSize(200, 300)
        poster.setStyleSheet("border-radius:10px")
        poster.setPixmap(self.c.artwork.poster_pixmap(item, 200, 300))
        hb.addWidget(poster, 0, Qt.AlignmentFlag.AlignTop)

        right = QVBoxLayout()
        title = QLabel(item["title"])
        title.setStyleSheet("font-size:24px;font-weight:700")
        title.setWordWrap(True)
        right.addWidget(title)

        if item.get("original_title") and item["original_title"] != item["title"]:
            orig = QLabel(f"<i>{item['original_title']}</i>")
            orig.setObjectName("Muted")
            right.addWidget(orig)

        meta_bits = [str(item.get("year") or ""), human_minutes(item.get("runtime_min") or 0),
                     " · ".join(item.get("genres") or []), f"★ {item.get('rating', 0):.1f}"]
        if item["kind"] == "show":
            meta_bits.append(f"{len(item.get('seasons') or [])} seasons")
        elif item["kind"] == "music":
            meta_bits.append("Music")
        meta = QLabel(" · ".join(b for b in meta_bits if b))
        meta.setObjectName("Muted")
        right.addWidget(meta)

        # IDs row
        id_bits = []
        if item.get("tmdb_id"):
            id_bits.append(f"TMDB {item['tmdb_id']}")
        if item.get("imdb_id"):
            id_bits.append(f"IMDb {item['imdb_id']}")
        if id_bits:
            ids_lbl = QLabel(" · ".join(id_bits))
            ids_lbl.setObjectName("Muted")
            right.addWidget(ids_lbl)

        ov = QLabel(item.get("overview") or "No synopsis yet — enrich via metadata providers.")
        ov.setWordWrap(True)
        ov.setObjectName("Muted")
        right.addWidget(ov)

        # actions
        actions = QHBoxLayout()
        self.btn_play = QPushButton(self._play_label())
        self.btn_play.setProperty("accent", True)
        self.btn_play.clicked.connect(self._play)
        actions.addWidget(self.btn_play)
        if item["kind"] == "movie":
            watched = item["id"] in self.c.state_repo.watched_movies()
            self.btn_watched = QPushButton("✓ Watched" if watched else "Mark watched")
            self.btn_watched.setCheckable(True)
            self.btn_watched.setChecked(watched)
            self.btn_watched.toggled.connect(self._toggle_watched)
            actions.addWidget(self.btn_watched)
        self.btn_fav = QPushButton("♥ Favorite" if item["id"] in self.c.state_repo.favorites() else "♡ Favorite")
        self.btn_fav.clicked.connect(self._toggle_fav)
        self.btn_wl = QPushButton("✓ Watchlist" if item["id"] in self.c.state_repo.watchlist() else "+ Watchlist")
        self.btn_wl.clicked.connect(self._toggle_wl)
        actions.addWidget(self.btn_fav)
        actions.addWidget(self.btn_wl)

        # Re-enrich button
        self.btn_reenrich = QPushButton("↻ Re-enrich")
        self.btn_reenrich.setToolTip("Re-fetch metadata from providers")
        self.btn_reenrich.clicked.connect(self._reenrich)
        actions.addWidget(self.btn_reenrich)

        actions.addStretch(1)
        right.addLayout(actions)

        # personal rating
        rate = QHBoxLayout()
        rate.addWidget(QLabel("Your rating:"))
        self.rate_spin = QSpinBox()
        self.rate_spin.setRange(0, 10)
        self.rate_spin.setSpecialValueText("—")
        self.rate_spin.setValue(self.c.state_repo.ratings_map().get(item["id"], 0))
        self.rate_spin.valueChanged.connect(
            lambda v: self.c.state_repo.set_rating(item["id"], v or None))
        rate.addWidget(self.rate_spin)
        rate.addStretch(1)
        right.addLayout(rate)
        right.addStretch(1)
        hb.addLayout(right, 1)
        self.root.addWidget(box)

    def _play_label(self) -> str:
        if self.item["kind"] == "show":
            ep = self.c.episode_repo.next_unwatched(self.media_id)
            return f"▶ Play S{ep['season']}E{ep['number']}" if ep else "▶ Play again"
        saved = self.c.progress_repo.get(f"m:{self.media_id}")
        return f"▶ Resume {(saved['position_s'] // 60)} min" if saved else "▶ Play"

    def _play(self) -> None:
        if self.item["kind"] == "show":
            ep = self.c.episode_repo.next_unwatched(self.media_id) \
                or (self.c.episode_repo.for_show(self.media_id) or [None])[0]
            if not ep:
                self._toast("No episodes indexed for this show.")
                return
            payload = self.c.playback.payload_episode(self.item, ep)
        else:
            payload = self.c.playback.payload_movie(self.item)
        if self.c.on_play_payload:
            self.c.on_play_payload(payload)

    def _toggle_watched(self, checked: bool) -> None:
        self.c.state_repo.mark_movie_watched(self.media_id, checked)
        self.btn_watched.setText("✓ Watched" if checked else "Mark watched")
        self.c.bus.emit("media.state_changed", id=self.media_id)

    def _toggle_fav(self) -> None:
        state = self.c.state_repo.toggle_favorite(self.media_id)
        self.btn_fav.setText("♥ Favorite" if state else "♡ Favorite")
        self.c.bus.emit("media.state_changed", id=self.media_id)

    def _toggle_wl(self) -> None:
        state = self.c.state_repo.toggle_watchlist(self.media_id)
        self.btn_wl.setText("✓ Watchlist" if state else "+ Watchlist")
        self.c.bus.emit("media.state_changed", id=self.media_id)

    def _reenrich(self) -> None:
        from app.library.media_detector import detect
        detected = detect(self.item.get("file_path", ""))
        result = self.c.metadata.re_enrich(
            self.media_id, detected, media_repo=self.c.media_repo, clear_cache=True)
        if result:
            self._toast(f"Re-enriched: {result.get('_raw_title', '')}")
            self.item = self.c.media_repo.get(self.media_id)
            self.rebuild()
        else:
            self._toast("Re-enrichment did not find new metadata.")

    # ----------------------------------------------------------------- cast
    def _cast(self) -> None:
        people = self.c.people_repo.for_media(self.media_id)
        if not people:
            return
        self.root.addWidget(SectionHeader("Cast & crew"))
        chips = QHBoxLayout()
        chips.setSpacing(8)
        for person in people[:12]:
            btn = QPushButton(f"{person['name']}\n{person['role']}")
            btn.setStyleSheet("text-align:left")
            btn.clicked.connect(lambda _=None, n=person["name"]: self._open_person(n))
            chips.addWidget(btn)
        chips.addStretch(1)
        self.root.addLayout(chips)

    def _open_person(self, name: str) -> None:
        self.c.open_media({"id": None, "kind": "person", "title": name})

    # ------------------------------------------------------------- episodes
    def _episodes_section(self) -> None:
        seasons = self.item.get("seasons") or []
        if not seasons:
            return
        self.root.addWidget(SectionHeader("Episodes", f"{len(seasons)} seasons"))
        tabs = QTabWidget()
        watched = self.c.episode_repo.watched_ids(self.media_id)
        for sn in seasons:
            eps = self.c.episode_repo.for_show(self.media_id, sn)
            page = QScrollArea()
            page.setWidgetResizable(True)
            host = QWidget()
            vb = QVBoxLayout(host)
            vb.setSpacing(6)
            for ep in eps:
                vb.addWidget(self._episode_row(ep, ep["id"] in watched))
            vb.addStretch(1)
            page.setWidget(host)
            tabs.addTab(page, f"Season {sn}")
        self.root.addWidget(tabs)

    def _episode_row(self, ep: dict, watched: bool) -> QWidget:
        row = QWidget()
        row.setObjectName("Panel")
        hb = QHBoxLayout(row)
        hb.setContentsMargins(10, 8, 10, 8)
        num = QLabel(f"{ep['season']}·{ep['number']}")
        num.setFixedWidth(46)
        num.setStyleSheet("font-weight:700")
        name = QLabel(ep.get("title") or f"Episode {ep['number']}")
        dur = QLabel(human_minutes(ep.get("runtime_min") or self.item.get("runtime_min") or 0))
        dur.setObjectName("Muted")
        btn_play = QPushButton("▶")
        btn_play.setFixedWidth(42)
        btn_play.clicked.connect(lambda _=None, e=ep: self._play_episode(e))
        btn_state = QPushButton("✓" if watched else "○")
        btn_state.setFixedWidth(42)
        btn_state.setToolTip("Toggle watched")
        btn_state.clicked.connect(lambda _=None, e=ep, w=watched, r=row: self._toggle_ep(e, w, r))
        hb.addWidget(num)
        hb.addWidget(name, 1)
        hb.addWidget(dur)
        hb.addWidget(btn_play)
        hb.addWidget(btn_state)
        if watched:
            name.setStyleSheet("color:#43d19e")
        return row

    def _play_episode(self, ep: dict) -> None:
        payload = self.c.playback.payload_episode(self.item, ep)
        if self.c.on_play_payload:
            self.c.on_play_payload(payload)

    def _toggle_ep(self, ep: dict, watched: bool, row: QWidget) -> None:
        if watched:
            self.c.episode_repo.mark_unwatched(ep["id"])
        else:
            self.c.episode_repo.mark_watched(ep["id"])
        # MainWindow subscribes to this and re-renders the current detail page
        self.c.bus.emit("media.state_changed", id=self.media_id)

    def _toast(self, msg: str) -> None:
        window = self.window()
        if window and hasattr(window, "statusBar"):
            window.statusBar().showMessage(msg, 4000)

    def on_show(self) -> None:
        """Re-query watched/favorite flags when the page is revisited."""
        self.btn_fav.setText("♥ Favorite" if self.media_id in self.c.state_repo.favorites() else "♡ Favorite")
        self.btn_wl.setText("✓ Watchlist" if self.media_id in self.c.state_repo.watchlist() else "+ Watchlist")
        self.btn_play.setText(self._play_label())

    def rebuild(self) -> None:
        """Refresh the entire detail view after metadata changes."""
        while self.root.count():
            item = self.root.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        self.item = self.c.media_repo.get(self.media_id)
        if not self.item:
            self.root.addWidget(EmptyState("Not found", "This title is no longer in the library."))
            return
        self.media_id = self.item["id"]
        self._header()
        self._cast()
        if self.item["kind"] == "show":
            self._episodes_section()
        self.root.addStretch(1)
