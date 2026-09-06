"""Music catalog: artists/albums/tracks read-models."""
from __future__ import annotations

from app.database.repositories import Repositories
from app.domain.value_objects import PlayableItem


class MusicCatalog:
    def __init__(self, repos: Repositories) -> None:
        self.repos = repos

    def list_artists(self, page=0, per_page=60, query="") -> tuple[list[dict], int]:
        return self.repos.music.list_artists(page, per_page, query)

    def list_albums(self, page=0, per_page=60, query="") -> tuple[list[dict], int]:
        return self.repos.music.list_albums(page, per_page, query)

    def search_tracks(self, query: str, limit: int = 50) -> list[dict]:
        return self.repos.music.search_tracks(query, limit)

    def artist_detail(self, artist_id: int, profile_id: int) -> dict | None:
        artist = self.repos.music.get_artist(artist_id)
        if artist is None:
            return None
        return {
            "id": artist.id,
            "name": artist.name,
            "sort_name": artist.sort_name,
            "biography": artist.biography,
            "disambiguation": artist.disambiguation,
            "genres": self.repos.music.artist_genres(artist_id),
            "photo_path": self.repos.artwork.local_path("artist", artist_id, "profile")
            or self.repos.artwork.local_path("artist", artist_id, "artist_banner"),
            "banner_path": self.repos.artwork.local_path("artist", artist_id, "artist_banner"),
            "external_ids": self.repos.external_ids.all_for("artist", artist_id),
            "albums": self.repos.music.albums_for_artist(artist_id),
            "album_count": self.repos.music.count_albums(),
            "is_favorite": self.repos.lists.is_favorite(profile_id, "artist", artist_id),
        }

    def album_detail(self, album_id: int, profile_id: int) -> dict | None:
        album = self.repos.music.get_album(album_id)
        if album is None:
            return None
        artist = self.repos.music.get_artist(album.artist_id)
        tracks = self.repos.music.tracks_for_album(album_id)
        return {
            "id": album.id,
            "title": album.title,
            "year": album.year,
            "release_date": album.release_date,
            "track_count": album.track_count or len(tracks),
            "genres": self.repos.music.album_genres(album_id),
            "artist_id": album.artist_id,
            "artist_name": artist.name if artist else "",
            "cover_path": self.repos.artwork.local_path("album", album_id, "album_cover"),
            "external_ids": self.repos.external_ids.all_for("album", album_id),
            "tracks": tracks,
            "is_favorite": self.repos.lists.is_favorite(profile_id, "album", album_id),
        }

    def playable(self, track_id: int) -> PlayableItem | None:
        track = self.repos.music.get_track(track_id)
        if track is None:
            return None
        media_file = self.repos.files.primary_file("track", track_id)
        if media_file is None:
            return None
        album = self.repos.music.get_album(track.album_id)
        artist = self.repos.music.get_artist(track.artist_id)
        return PlayableItem(
            media_type="track",
            media_id=track_id,
            media_file_id=media_file.id,
            path=media_file.path,
            title=track.title,
            subtitle=f"{artist.name if artist else ''} · {album.title if album else ''}".strip(" ·"),
            duration_seconds=float(track.duration_seconds or 0),
            artwork_path=self.repos.artwork.local_path("album", track.album_id, "album_cover"),
        )

    def album_playables(self, album_id: int) -> list[PlayableItem]:
        out = []
        for track in self.repos.music.tracks_for_album(album_id):
            if track.get("file_path"):
                playable = self.playable(track["id"])
                if playable:
                    out.append(playable)
        return out

    def recently_played(self, profile_id: int, limit: int = 20) -> list[dict]:
        return self.repos.music.recently_played_tracks(profile_id, limit)
