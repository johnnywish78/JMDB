"""Music repository: artists, albums, tracks, playlists."""
from __future__ import annotations

from typing import Any

from app.domain.models import MusicAlbum, MusicArtist, MusicTrack, Playlist
from app.database.repositories import BaseRepository, row_to_dataclass, rows_to_dataclasses

ALBUM_COVER_SUB = (
    "(SELECT a.local_path FROM artwork a WHERE a.owner_type='album' AND a.owner_id=al.id"
    " AND a.kind='album_cover' AND a.local_path<>'' ORDER BY a.id LIMIT 1) AS cover_path"
)


class MusicRepository(BaseRepository):
    # -- artists ---------------------------------------------------------------
    def get_artist(self, artist_id: int) -> MusicArtist | None:
        row = self.db.query_one("SELECT * FROM music_artists WHERE id=?", (artist_id,))
        return row_to_dataclass(row, MusicArtist) if row else None

    def find_artist(self, name: str) -> MusicArtist | None:
        row = self.db.query_one(
            "SELECT * FROM music_artists WHERE lower(name)=lower(?) LIMIT 1", (name,)
        )
        return row_to_dataclass(row, MusicArtist) if row else None

    def create_artist(self, artist: MusicArtist) -> int:
        cur = self.db.execute(
            "INSERT INTO music_artists (name, sort_name, biography, disambiguation) VALUES (?,?,?,?)",
            (artist.name, artist.sort_name, artist.biography, artist.disambiguation),
        )
        return int(cur.lastrowid)

    def update_artist(self, artist_id: int, values: dict[str, Any]) -> None:
        allowed = {"name", "sort_name", "biography", "disambiguation"}
        sets, params = [], []
        for key, value in values.items():
            if key in allowed:
                sets.append(f"{key}=?")
                params.append(value)
        if sets:
            params.append(artist_id)
            self.db.execute(f"UPDATE music_artists SET {', '.join(sets)} WHERE id=?", params)

    def list_artists(
        self, page: int = 0, per_page: int = 60, query: str = ""
    ) -> tuple[list[dict], int]:
        where, params = ["1=1"], []
        if query:
            where.append("ar.name LIKE ?")
            params.append(f"%{query}%")
        base = " AND ".join(where)
        total = int(self.db.scalar(f"SELECT COUNT(*) FROM music_artists ar WHERE {base}", params) or 0)
        rows = self.db.query(
            "SELECT ar.id, ar.name,"
            " (SELECT a.local_path FROM artwork a WHERE a.owner_type='artist' AND a.owner_id=ar.id"
            "  AND a.local_path<>'' ORDER BY a.id LIMIT 1) AS photo_path,"
            " (SELECT COUNT(*) FROM music_albums al WHERE al.artist_id=ar.id) AS album_count,"
            " (SELECT COUNT(*) FROM music_tracks t WHERE t.artist_id=ar.id) AS track_count"
            f" FROM music_artists ar WHERE {base}"
            " ORDER BY COALESCE(NULLIF(ar.sort_name,''), ar.name) COLLATE NOCASE LIMIT ? OFFSET ?",
            (*params, per_page, page * per_page),
        )
        return [dict(r) for r in rows], total

    def count_artists(self) -> int:
        return int(self.db.scalar("SELECT COUNT(*) FROM music_artists") or 0)

    # -- albums -----------------------------------------------------------------
    def get_album(self, album_id: int) -> MusicAlbum | None:
        row = self.db.query_one("SELECT * FROM music_albums WHERE id=?", (album_id,))
        return row_to_dataclass(row, MusicAlbum) if row else None

    def find_album(self, artist_id: int, title: str) -> MusicAlbum | None:
        row = self.db.query_one(
            "SELECT * FROM music_albums WHERE artist_id=? AND lower(title)=lower(?)",
            (artist_id, title),
        )
        return row_to_dataclass(row, MusicAlbum) if row else None

    def create_album(self, album: MusicAlbum) -> int:
        cur = self.db.execute(
            "INSERT INTO music_albums (artist_id, title, year, release_date, track_count)"
            " VALUES (?,?,?,?,?)",
            (album.artist_id, album.title, album.year, album.release_date, album.track_count),
        )
        return int(cur.lastrowid)

    def update_album(self, album_id: int, values: dict[str, Any]) -> None:
        allowed = {"title", "year", "release_date", "track_count", "artist_id"}
        sets, params = [], []
        for key, value in values.items():
            if key in allowed:
                sets.append(f"{key}=?")
                params.append(value)
        if sets:
            params.append(album_id)
            self.db.execute(f"UPDATE music_albums SET {', '.join(sets)} WHERE id=?", params)

    def albums_for_artist(self, artist_id: int) -> list[dict]:
        rows = self.db.query(
            f"SELECT al.id, al.title, al.year, al.track_count, {ALBUM_COVER_SUB}"
            " FROM music_albums al WHERE al.artist_id=? ORDER BY al.year, al.title",
            (artist_id,),
        )
        return [dict(r) for r in rows]

    def list_albums(
        self, page: int = 0, per_page: int = 60, query: str = ""
    ) -> tuple[list[dict], int]:
        where, params = ["1=1"], []
        if query:
            where.append("(al.title LIKE ? OR ar.name LIKE ?)")
            params.extend([f"%{query}%", f"%{query}%"])
        base = " AND ".join(where)
        total = int(
            self.db.scalar(
                f"SELECT COUNT(*) FROM music_albums al JOIN music_artists ar ON ar.id=al.artist_id WHERE {base}",
                params,
            )
            or 0
        )
        rows = self.db.query(
            f"SELECT al.id, al.title, al.year, al.track_count, ar.name AS artist_name,"
            f" ar.id AS artist_id, {ALBUM_COVER_SUB}"
            " FROM music_albums al JOIN music_artists ar ON ar.id=al.artist_id"
            f" WHERE {base} ORDER BY al.title COLLATE NOCASE LIMIT ? OFFSET ?",
            (*params, per_page, page * per_page),
        )
        return [dict(r) for r in rows], total

    def count_albums(self) -> int:
        return int(self.db.scalar("SELECT COUNT(*) FROM music_albums") or 0)

    # -- tracks -------------------------------------------------------------------
    def get_track(self, track_id: int) -> MusicTrack | None:
        row = self.db.query_one("SELECT * FROM music_tracks WHERE id=?", (track_id,))
        return row_to_dataclass(row, MusicTrack) if row else None

    def find_track(self, album_id: int, title: str, track_number: int | None) -> MusicTrack | None:
        if track_number is not None:
            row = self.db.query_one(
                "SELECT * FROM music_tracks WHERE album_id=? AND track_number=?",
                (album_id, track_number),
            )
            if row:
                return row_to_dataclass(row, MusicTrack)
        row = self.db.query_one(
            "SELECT * FROM music_tracks WHERE album_id=? AND lower(title)=lower(?)",
            (album_id, title),
        )
        return row_to_dataclass(row, MusicTrack) if row else None

    def create_track(self, track: MusicTrack) -> int:
        cur = self.db.execute(
            "INSERT INTO music_tracks (album_id, artist_id, title, track_number, disc_number, duration_seconds)"
            " VALUES (?,?,?,?,?,?)",
            (
                track.album_id, track.artist_id, track.title, track.track_number,
                track.disc_number, track.duration_seconds,
            ),
        )
        return int(cur.lastrowid)

    def tracks_for_album(self, album_id: int) -> list[dict]:
        rows = self.db.query(
            "SELECT t.id, t.title, t.track_number, t.disc_number, t.duration_seconds,"
            " t.artist_id, al.title AS album_title, al.id AS album_id,"
            " (SELECT ar.name FROM music_artists ar WHERE ar.id=t.artist_id) AS artist_name,"
            f" {ALBUM_COVER_SUB},"
            " (SELECT f.path FROM media_file_links l JOIN media_files f ON f.id=l.media_file_id"
            "  WHERE l.media_item_type='track' AND l.media_item_id=t.id AND f.is_missing=0"
            "  ORDER BY l.is_primary DESC LIMIT 1) AS file_path"
            " FROM music_tracks t JOIN music_albums al ON al.id=t.album_id"
            " WHERE t.album_id=? ORDER BY t.disc_number, t.track_number",
            (album_id,),
        )
        return [dict(r) for r in rows]

    def count_tracks(self) -> int:
        return int(self.db.scalar("SELECT COUNT(*) FROM music_tracks") or 0)

    def recent_albums(self, limit: int = 12) -> list[dict]:
        rows = self.db.query(
            f"SELECT al.id, al.title, al.year, ar.name AS artist_name, {ALBUM_COVER_SUB}"
            " FROM music_albums al JOIN music_artists ar ON ar.id=al.artist_id"
            " ORDER BY al.added_at DESC LIMIT ?",
            (limit,),
        )
        return [dict(r) for r in rows]

    def recently_played_tracks(self, profile_id: int, limit: int = 20) -> list[dict]:
        rows = self.db.query(
            "SELECT t.id, t.title, t.duration_seconds,"
            " (SELECT ar.name FROM music_artists ar WHERE ar.id=t.artist_id) AS artist_name,"
            " al.title AS album_title, al.id AS album_id,"
            f" {ALBUM_COVER_SUB}, MAX(h.started_at) AS last_played"
            " FROM playback_history h"
            " JOIN music_tracks t ON t.id=h.media_id AND h.media_type='track'"
            " JOIN music_albums al ON al.id=t.album_id"
            " WHERE h.profile_id=? GROUP BY t.id ORDER BY last_played DESC LIMIT ?",
            (profile_id, limit),
        )
        return [dict(r) for r in rows]

    def search_tracks(self, query: str, limit: int = 50) -> list[dict]:
        rows = self.db.query(
            "SELECT t.id, t.title, t.duration_seconds, t.artist_id, al.id AS album_id,"
            " (SELECT ar.name FROM music_artists ar WHERE ar.id=t.artist_id) AS artist_name,"
            f" {ALBUM_COVER_SUB}"
            " FROM music_tracks t JOIN music_albums al ON al.id=t.album_id"
            " WHERE t.title LIKE ? OR (SELECT ar.name FROM music_artists ar WHERE ar.id=t.artist_id) LIKE ?"
            " OR al.title LIKE ? LIMIT ?",
            (f"%{query}%", f"%{query}%", f"%{query}%", limit),
        )
        return [dict(r) for r in rows]

    # -- genres -----------------------------------------------------------------
    def music_genre_id(self, name: str) -> int:
        cur = self.db.execute("INSERT OR IGNORE INTO music_genres (name) VALUES (?)", (name.strip(),))
        if cur.lastrowid:
            return int(cur.lastrowid)
        return int(self.db.scalar("SELECT id FROM music_genres WHERE name=?", (name,)))

    def set_artist_genres(self, artist_id: int, names: list[str]) -> None:
        self.db.execute("DELETE FROM artist_genres WHERE artist_id=?", (artist_id,))
        for name in names:
            if name:
                self.db.execute(
                    "INSERT OR IGNORE INTO artist_genres (artist_id, genre_id) VALUES (?,?)",
                    (artist_id, self.music_genre_id(name)),
                )

    def artist_genres(self, artist_id: int) -> list[str]:
        rows = self.db.query(
            "SELECT g.name FROM music_genres g JOIN artist_genres ag ON ag.genre_id=g.id"
            " WHERE ag.artist_id=? ORDER BY g.name",
            (artist_id,),
        )
        return [r["name"] for r in rows]

    def set_album_genres(self, album_id: int, names: list[str]) -> None:
        self.db.execute("DELETE FROM album_genres WHERE album_id=?", (album_id,))
        for name in names:
            if name:
                self.db.execute(
                    "INSERT OR IGNORE INTO album_genres (album_id, genre_id) VALUES (?,?)",
                    (album_id, self.music_genre_id(name)),
                )

    def album_genres(self, album_id: int) -> list[str]:
        rows = self.db.query(
            "SELECT g.name FROM music_genres g JOIN album_genres ag ON ag.genre_id=g.id"
            " WHERE ag.album_id=? ORDER BY g.name",
            (album_id,),
        )
        return [r["name"] for r in rows]

    # -- playlists -----------------------------------------------------------------
    def playlists(self, profile_id: int) -> list[Playlist]:
        return rows_to_dataclasses(
            self.db.query(
                "SELECT * FROM playlists WHERE profile_id=? ORDER BY name COLLATE NOCASE",
                (profile_id,),
            ),
            Playlist,
        )

    def create_playlist(self, profile_id: int, name: str) -> Playlist:
        cur = self.db.execute(
            "INSERT INTO playlists (profile_id, name) VALUES (?,?)", (profile_id, name)
        )
        return Playlist(id=cur.lastrowid, profile_id=profile_id, name=name)

    def delete_playlist(self, playlist_id: int) -> None:
        self.db.execute("DELETE FROM playlists WHERE id=?", (playlist_id,))

    def rename_playlist(self, playlist_id: int, name: str) -> None:
        self.db.execute(
            "UPDATE playlists SET name=?, updated_at=datetime('now') WHERE id=?",
            (name, playlist_id),
        )

    def add_track_to_playlist(self, playlist_id: int, track_id: int) -> None:
        position = int(
            self.db.scalar(
                "SELECT COALESCE(MAX(position), -1) + 1 FROM playlist_tracks WHERE playlist_id=?",
                (playlist_id,),
            )
            or 0
        )
        self.db.execute(
            "INSERT OR IGNORE INTO playlist_tracks (playlist_id, track_id, position) VALUES (?,?,?)",
            (playlist_id, track_id, position),
        )

    def remove_track_from_playlist(self, playlist_id: int, track_id: int) -> None:
        self.db.execute(
            "DELETE FROM playlist_tracks WHERE playlist_id=? AND track_id=?",
            (playlist_id, track_id),
        )

    def playlist_tracks(self, playlist_id: int) -> list[dict]:
        rows = self.db.query(
            "SELECT t.id, t.title, t.duration_seconds, t.track_number,"
            " (SELECT ar.name FROM music_artists ar WHERE ar.id=t.artist_id) AS artist_name,"
            " (SELECT al.title FROM music_albums al WHERE al.id=t.album_id) AS album_title,"
            " pt.position,"
            " (SELECT f.path FROM media_file_links l JOIN media_files f ON f.id=l.media_file_id"
            "  WHERE l.media_item_type='track' AND l.media_item_id=t.id AND f.is_missing=0"
            "  ORDER BY l.is_primary DESC LIMIT 1) AS file_path"
            " FROM playlist_tracks pt JOIN music_tracks t ON t.id=pt.track_id"
            " WHERE pt.playlist_id=? ORDER BY pt.position",
            (playlist_id,),
        )
        return [dict(r) for r in rows]
