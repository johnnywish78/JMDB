"""Music screen: artists / albums / tracks tabs."""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ui.components.music_card import MusicCard
from ui.components.states import EmptyState
from ui.screens.base import Screen


class MusicScreen(Screen):
    title = "Music"
    empty_hint = "Music appears after a scan indexes your audio files."

    def __init__(self, context, parent=None) -> None:
        super().__init__(context, parent)
        self.header = QLabel("Music")
        self.header.setObjectName("ScreenTitle")
        self.root.addWidget(self.header)

        self.tabs = QTabWidget()
        self.root.addWidget(self.tabs, 1)

        # Artists tab
        self.artists_tab = QWidget()
        artists_layout = QVBoxLayout(self.artists_tab)
        self.artist_search = QLineEdit()
        self.artist_search.setPlaceholderText("Filter artists…")
        self.artist_search.textChanged.connect(lambda _t: self.refresh())
        artists_layout.addWidget(self.artist_search)
        self.artists_scroll = QScrollArea()
        self.artists_scroll.setWidgetResizable(True)
        self.artists_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        artists_layout.addWidget(self.artists_scroll, 1)
        self.artists_container = QWidget()
        self.artists_grid = QGridLayout(self.artists_container)
        self.artists_grid.setSpacing(12)
        self.artists_scroll.setWidget(self.artists_container)
        self.tabs.addTab(self.artists_tab, "Artists")

        # Albums tab
        self.albums_tab = QWidget()
        albums_layout = QVBoxLayout(self.albums_tab)
        self.album_search = QLineEdit()
        self.album_search.setPlaceholderText("Filter albums…")
        self.album_search.textChanged.connect(lambda _t: self.refresh())
        albums_layout.addWidget(self.album_search)
        self.albums_scroll = QScrollArea()
        self.albums_scroll.setWidgetResizable(True)
        self.albums_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        albums_layout.addWidget(self.albums_scroll, 1)
        self.albums_container = QWidget()
        self.albums_grid = QGridLayout(self.albums_container)
        self.albums_grid.setSpacing(12)
        self.albums_scroll.setWidget(self.albums_container)
        self.tabs.addTab(self.albums_tab, "Albums")

        # Tracks tab (search)
        self.tracks_tab = QWidget()
        tracks_layout = QVBoxLayout(self.tracks_tab)
        self.track_search = QLineEdit()
        self.track_search.setPlaceholderText("Search tracks…")
        self.track_search.textChanged.connect(lambda _t: self.refresh())
        tracks_layout.addWidget(self.track_search)
        self.tracks_scroll = QScrollArea()
        self.tracks_scroll.setWidgetResizable(True)
        self.tracks_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        tracks_layout.addWidget(self.tracks_scroll, 1)
        self.tracks_container = QWidget()
        self.tracks_layout = QVBoxLayout(self.tracks_container)
        self.tracks_scroll.setWidget(self.tracks_container)
        self.tabs.addTab(self.tracks_tab, "Tracks")

        self.empty_state = EmptyState("No music yet", self.empty_hint)
        self.empty_state.setVisible(False)
        self.root.addWidget(self.empty_state)

    def refresh(self) -> None:
        from ui.app.context import run_async

        def work():
            artists, _ = self.context.services.music.list_artists(
                0, 120, self.artist_search.text().strip()
            )
            albums, _ = self.context.services.music.list_albums(
                0, 120, self.album_search.text().strip()
            )
            query = self.track_search.text().strip()
            tracks = self.context.services.music.search_tracks(query, 100) if query else []
            return artists, albums, tracks

        run_async(work, self._populate)

    def _populate(self, result) -> None:
        artists, albums, tracks = result
        for grid, rows in ((self.artists_grid, artists), (self.albums_grid, albums)):
            while grid.count():
                item = grid.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
        while self.tracks_layout.count():
            item = self.tracks_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        has_music = bool(artists or albums)
        self.empty_state.setVisible(not has_music)
        self.tabs.setVisible(has_music)

        columns = max(1, (max(500, self.width()) - 60) // 190)
        for index, artist in enumerate(artists):
            card = MusicCard({"id": artist["id"], "title": artist["name"], "subtitle": f"{artist.get('album_count', 0)} albums"})
            card.clicked.connect(
                lambda data: self.context.router.navigate("music", query=data["title"])
            )
            self._load_art(card, artist.get("photo_path", ""))
            self.artists_grid.addWidget(card, index // columns, index % columns)
        for index, album in enumerate(albums):
            card = MusicCard({"id": album["id"], "title": album["title"],
                              "artist_name": album.get("artist_name", "")})
            card.clicked.connect(
                lambda data: self.context.router.navigate("music_detail", album_id=data["id"])
            )
            card.play_requested.connect(
                lambda data: self._play_album(data["id"])
            )
            self._load_art(card, album.get("cover_path", ""))
            self.albums_grid.addWidget(card, index // columns, index % columns)
        if tracks:
            from ui.components.media_card import MediaCard

            for track in tracks:
                card = MediaCard(
                    track["title"],
                    f"{track.get('artist_name', '')} · {track.get('album_title', '')}",
                )
                card.double_clicked.connect(lambda _=None, t=track: self._play_track(t))
                self.tracks_layout.addWidget(card)
        self.tracks_layout.addStretch(1)

    def _load_art(self, card: MusicCard, path: str) -> None:
        context = self.context

        def handler(key, pixmap, card=card):
            card.set_pixmap(pixmap)
            try:
                context.images.ready.disconnect(handler)
            except TypeError:
                pass

        context.images.ready.connect(handler)
        context.images.request(f"music-{id(card)}", path, 340)

    def _play_album(self, album_id: int) -> None:
        queue = self.context.services.music.album_playables(album_id)
        if not queue:
            self.context.toast("No playable tracks", "warning")
            return
        self.context.open_player(queue[0], queue)

    def _play_track(self, track: dict) -> None:
        playable = self.context.services.music.playable(track["id"])
        if playable is None:
            self.context.toast("No playable file", "warning")
            return
        self.context.open_player(playable)
