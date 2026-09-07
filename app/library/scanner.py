"""The library scanner.

Pure Python (no Qt): walks configured library locations, indexes files,
matches movies / TV / music, attaches local artwork, probes media, and
detects duplicates. Progress is reported through the event bus; the scan
can be paused, resumed, and cancelled cooperatively.

A malformed filename, unreadable file, or probe failure never aborts the
scan — errors are counted, logged, and the scan continues.
"""
from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from app.database.connection import Database
from app.database.repositories import Repositories
from app.domain.events import (
    EventBus,
    LibraryScanFinished,
    LibraryScanProgress,
    LibraryScanStarted,
    MediaAdded,
)
from app.library.episode_matcher import candidate_from_file
from app.library.file_indexer import FileIndexer
from app.library.media_detector import (
    classify_extension,
    local_artwork_kind,
    season_poster_filename,
)
from app.library.movie_matcher import candidates_from_files, group_movies, primary_file
from app.library.music_matcher import candidate_from_file as track_candidate_from_file
from app.library.probe import ProbeTools
from app.library.series_matcher import canonical_title, group_by_show

logger = logging.getLogger(__name__)


class ScanCancelled(Exception):
    pass


@dataclass
class ScanOptions:
    probe_files: bool = True
    checksum_min_mb: int = 50
    include_hidden: bool = False
    follow_symlinks: bool = False


@dataclass
class ScanCounts:
    files_seen: int = 0
    files_added: int = 0
    files_updated: int = 0
    files_missing: int = 0
    movies_added: int = 0
    shows_added: int = 0
    episodes_added: int = 0
    artists_added: int = 0
    albums_added: int = 0
    tracks_added: int = 0
    errors: int = 0
    artwork_attached: int = 0


class LibraryScanner:
    CHECK_INTERVAL = 25  # files between pause/cancel checks
    PROGRESS_INTERVAL = 0.5  # seconds between scan_progress events
    PROGRESS_EVERY_FILES = 10  # …or every N files, whichever comes first

    def __init__(
        self,
        db: Database,
        repos: Repositories,
        events: EventBus,
        probe_tools: ProbeTools,
        options: ScanOptions | None = None,
    ) -> None:
        self.db = db
        self.repos = repos
        self.events = events
        self.probe_tools = probe_tools
        self.options = options or ScanOptions()
        self._pause_event = threading.Event()
        self._cancel_flag = threading.Event()
        self._lock = threading.Lock()

    # -- control ----------------------------------------------------------
    def pause(self) -> None:
        self._pause_event.set()

    def resume(self) -> None:
        self._pause_event.clear()

    def cancel(self) -> None:
        self._cancel_flag.set()
        self._pause_event.clear()

    @property
    def is_paused(self) -> bool:
        return self._pause_event.is_set()

    def _check_control(self, location_id: int | None, counts: ScanCounts) -> None:
        if self._pause_event.is_set():
            self.events.publish(
                LibraryScanProgress(location_id=location_id, paused=True,
                                    files_seen=counts.files_seen,
                                    files_indexed=counts.files_added + counts.files_updated)
            )
            while self._pause_event.is_set() and not self._cancel_flag.is_set():
                time.sleep(0.2)
        if self._cancel_flag.is_set():
            raise ScanCancelled()

    # -- entry points ---------------------------------------------------------
    def scan_all(self) -> ScanCounts:
        locations = [loc for loc in self.repos.locations.list() if loc.enabled]
        return self._scan_locations(locations, location_id=None)

    def scan_location(self, location_id: int) -> ScanCounts:
        location = self.repos.locations.get(location_id)
        if location is None:
            raise ValueError(f"unknown location {location_id}")
        return self._scan_locations([location], location_id=location_id)

    def _scan_locations(self, locations, location_id: int | None) -> ScanCounts:
        self._pause_event.clear()
        self._cancel_flag.clear()
        total = ScanCounts()
        started = time.monotonic()
        self.events.publish(
            LibraryScanStarted(location_id=location_id, total_locations=len(locations))
        )
        status = "completed"
        message = ""
        try:
            for location in locations:
                counts = ScanCounts()
                try:
                    self._scan_one_location(location.id, location.path, counts)
                except ScanCancelled:
                    raise
                except Exception as exc:
                    logger.exception("scan failed for %s", location.path)
                    counts.errors += 1
                    self.repos.locations.update_scan_result(location.id, "failed", str(exc))
                    status = "failed"
                    message = str(exc)
                total.files_seen += counts.files_seen
                total.files_added += counts.files_added
                total.files_updated += counts.files_updated
                total.files_missing += counts.files_missing
                total.movies_added += counts.movies_added
                total.shows_added += counts.shows_added
                total.episodes_added += counts.episodes_added
                total.artists_added += counts.artists_added
                total.albums_added += counts.albums_added
                total.tracks_added += counts.tracks_added
                total.errors += counts.errors
                total.artwork_attached += counts.artwork_attached
        except ScanCancelled:
            status = "cancelled"
            message = "scan cancelled"
        for location in locations:
            if status != "failed":
                self.repos.locations.update_scan_result(location.id, status)
        duration = time.monotonic() - started
        self.events.publish(
            LibraryScanFinished(
                location_id=location_id,
                status=status,
                files_seen=total.files_seen,
                files_indexed=total.files_added,
                files_missing=total.files_missing,
                files_added=total.files_added,
                movies_added=total.movies_added,
                shows_added=total.shows_added,
                episodes_added=total.episodes_added,
                artists_added=total.artists_added,
                albums_added=total.albums_added,
                tracks_added=total.tracks_added,
                errors=total.errors,
                duration_seconds=duration,
                message=message,
            )
        )
        return total

    # -- one location ------------------------------------------------------------
    def _scan_one_location(self, location_id: int, root: str, counts: ScanCounts) -> None:
        from app.library.filesystem import walk_files

        logger.info("scanning %s", root)
        indexer = FileIndexer(self.db, self.repos)

        # Phase A: walk + index ------------------------------------------------
        entries: list[dict] = []
        seen: set[str] = set()
        last_progress = time.monotonic()
        self._publish_progress(location_id, counts, root, phase="indexing")

        def _maybe_progress(directory: str) -> None:
            """Emit scan_progress every N files or T seconds, whichever first.

            Time-based emission keeps live progress visible on slow network
            mounts; count-based keeps it granular on fast local disks.
            """
            nonlocal last_progress
            now = time.monotonic()
            if (
                counts.files_seen % self.PROGRESS_EVERY_FILES == 0
                or now - last_progress >= self.PROGRESS_INTERVAL
            ):
                self._publish_progress(location_id, counts, directory, phase="indexing")
                last_progress = now

        for found in walk_files(
            root,
            include_hidden=self.options.include_hidden,
            follow_symlinks=self.options.follow_symlinks,
        ):
            kind = classify_extension(found.extension)
            if kind == "other":
                continue
            entries.append(
                {
                    "path": found.path,
                    "filename": found.filename,
                    "directory": found.directory,
                    "size_bytes": found.size_bytes,
                    "mtime_ns": found.mtime_ns,
                    "extension": found.extension,
                    "kind": kind,
                }
            )
            seen.add(found.path)
            counts.files_seen += 1
            if counts.files_seen % self.CHECK_INTERVAL == 0:
                self._check_control(location_id, counts)
            _maybe_progress(found.directory)

        if self._cancel_flag.is_set():
            raise ScanCancelled()

        result = indexer.sync(location_id, entries)
        counts.files_added += result["added"]
        counts.files_updated += result["updated"]
        counts.files_missing += result["missing"]
        id_by_path: dict[str, int] = result["ids"]

        # Phase B: match videos to episodes / movies ---------------------------------
        self._publish_progress(location_id, counts, root, phase="matching")
        video_rows = self.db.query(
            "SELECT id, path, filename, directory, size_bytes FROM media_files"
            " WHERE library_location_id=? AND kind='video' AND is_missing=0",
            (location_id,),
        )
        unmatched: list[dict] = []
        episode_candidates = []
        for row in video_rows:
            try:
                pure = Path(row["directory"])
                parent = pure.name
                grandparent = pure.parent.name
                stem = row["filename"].rsplit(".", 1)[0]
                candidates = candidate_from_file(
                    stem, parent, grandparent, row["id"], row["path"],
                    row["filename"], row["size_bytes"],
                )
                if candidates:
                    episode_candidates.extend(candidates)
                else:
                    unmatched.append(dict(row))
            except Exception:
                logger.exception("episode parse failed: %s", row["filename"])
                counts.errors += 1
                unmatched.append(dict(row))

        self._match_shows(episode_candidates, counts, location_id)
        self._match_movies(unmatched, counts)

        # Phase C: music ------------------------------------------------------------
        audio_rows = self.db.query(
            "SELECT id, path, filename, directory, size_bytes FROM media_files"
            " WHERE library_location_id=? AND kind='audio' AND is_missing=0",
            (location_id,),
        )
        self._match_music(audio_rows, counts)

        # Phase D: local artwork ------------------------------------------------------
        self._publish_progress(location_id, counts, root, phase="artwork")
        image_rows = self.db.query(
            "SELECT id, path, filename, directory FROM media_files"
            " WHERE library_location_id=? AND kind='image' AND is_missing=0",
            (location_id,),
        )
        self._attach_local_artwork(image_rows, counts)

        # Phase E: probe ---------------------------------------------------------------
        if self.options.probe_files and self.probe_tools.available:
            self._probe_items(location_id, counts)

        self._check_control(location_id, counts)

    # -- matching helpers ------------------------------------------------------------
    def _publish_progress(
        self,
        location_id: int | None,
        counts: ScanCounts,
        current_path: str = "",
        phase: str = "indexing",
    ) -> None:
        """Fan out one scan_progress event (throttled by the callers)."""
        self.events.publish(
            LibraryScanProgress(
                location_id=location_id,
                current_path=current_path,
                files_seen=counts.files_seen,
                files_indexed=counts.files_added + counts.files_updated,
                phase=phase,
            )
        )

    def _match_shows(self, episode_candidates, counts: ScanCounts, location_id) -> None:
        from app.domain.models import TvShow

        for key, group in group_by_show(episode_candidates).items():
            self._check_control(location_id, counts)
            try:
                display_title = canonical_title(group)
                show = self.repos.tv.find_show_by_title(display_title)
                if show is None:
                    show_id = self.repos.tv.create_show(TvShow(title=display_title))
                    counts.shows_added += 1
                else:
                    show_id = show.id
                for candidate in group:
                    season_id = self.repos.tv.get_or_create_season(show_id, candidate.season)
                    episode_id, created = self.repos.tv.get_or_create_episode(
                        show_id, season_id, candidate.season, candidate.episode
                    )
                    if created:
                        counts.episodes_added += 1
                    self.repos.files.link("episode", episode_id, candidate.file_id,
                                          primary=candidate.file_id in self._primary_ids(group))
                if counts.shows_added or counts.episodes_added:
                    self.events.publish(MediaAdded(media_type="tv_show", media_id=show_id))
            except Exception:
                logger.exception("show matching failed for %s", key)
                counts.errors += 1

    @staticmethod
    def _primary_ids(group) -> set[int]:
        """Largest file per episode number."""
        by_episode: dict[int, tuple[int, int]] = {}
        for candidate in group:
            best = by_episode.get(candidate.episode)
            if best is None or candidate.size_bytes > best[1]:
                by_episode[candidate.episode] = (candidate.file_id, candidate.size_bytes)
        return {fid for fid, _ in by_episode.values()}

    def _match_movies(self, unmatched_rows, counts: ScanCounts) -> None:
        try:
            candidates = candidates_from_files(unmatched_rows)
        except Exception:
            logger.exception("movie parsing failed")
            counts.errors += 1
            return
        for (norm_title, year), group in group_movies(candidates).items():
            try:
                existing = self.repos.movies.find_by_title_year(group[0].title, year)
                if existing is not None:
                    movie_id = existing.id
                else:
                    from app.domain.models import Movie

                    movie_id = self.repos.movies.create(
                        Movie(title=group[0].title, year=year)
                    )
                    counts.movies_added += 1
                primary = primary_file(group)
                for candidate in group:
                    self.repos.files.link(
                        "movie", movie_id, candidate.file_id,
                        primary=candidate.file_id == primary.file_id,
                    )
                self.events.publish(MediaAdded(media_type="movie", media_id=movie_id))
            except Exception:
                logger.exception("movie matching failed for %s (%s)", norm_title, year)
                counts.errors += 1

    def _match_music(self, audio_rows, counts: ScanCounts) -> None:
        candidates = []
        for row in audio_rows:
            try:
                candidate = track_candidate_from_file(dict(row))
                if candidate is not None:
                    candidates.append(candidate)
            except Exception:
                logger.exception("music parsing failed: %s", row["filename"])
                counts.errors += 1
        albums: dict[tuple[str, str], list] = defaultdict(list)
        for candidate in candidates:
            albums[(candidate.artist.lower(), candidate.album.lower())].append(candidate)
        for (artist_lower, album_lower), tracks in albums.items():
            try:
                artist = self.repos.music.find_artist(tracks[0].artist)
                if artist is None:
                    from app.domain.models import MusicArtist

                    artist_id = self.repos.music.create_artist(
                        MusicArtist(name=tracks[0].artist)
                    )
                    counts.artists_added += 1
                else:
                    artist_id = artist.id
                album = self.repos.music.find_album(artist_id, tracks[0].album)
                if album is None:
                    from app.domain.models import MusicAlbum

                    years = [t.album_year for t in tracks if t.album_year]
                    album_id = self.repos.music.create_album(
                        MusicAlbum(
                            artist_id=artist_id,
                            title=tracks[0].album,
                            year=years[0] if years else None,
                            track_count=len(tracks),
                        )
                    )
                    counts.albums_added += 1
                else:
                    album_id = album.id
                for track in tracks:
                    existing = self.repos.music.find_track(album_id, track.title, track.track_number)
                    if existing is not None:
                        track_id = existing.id
                    else:
                        from app.domain.models import MusicTrack

                        track_id = self.repos.music.create_track(
                            MusicTrack(
                                album_id=album_id,
                                artist_id=artist_id,
                                title=track.title,
                                track_number=track.track_number,
                                disc_number=track.disc_number,
                                duration_seconds=track.duration_seconds,
                            )
                        )
                        counts.tracks_added += 1
                    self.repos.files.link("track", track_id, track.file_id, primary=True)
                if track.genre:
                    self.repos.music.set_album_genres(album_id, [track.genre])
                self.events.publish(MediaAdded(media_type="album", media_id=album_id))
            except Exception:
                logger.exception("music matching failed for %s/%s", artist_lower, album_lower)
                counts.errors += 1

    # -- artwork / probing ------------------------------------------------------------
    def _attach_local_artwork(self, image_rows, counts: ScanCounts) -> None:
        for row in image_rows:
            try:
                kind = local_artwork_kind(row["filename"])
                if kind is None:
                    continue
                season_number = season_poster_filename(row["filename"])
                owner = self._owner_in_directory(row["directory"])
                if owner is None:
                    continue
                owner_type, owner_id, _ = owner
                if season_number is not None and owner_type == "tv_show":
                    season_id = self.repos.tv.get_or_create_season(owner_id, season_number)
                    self.repos.artwork.upsert(
                        "season", season_id, "season_poster",
                        source_url="", local_path=row["path"],
                    )
                else:
                    self.repos.artwork.upsert(
                        owner_type, owner_id, kind, source_url="", local_path=row["path"]
                    )
                counts.artwork_attached += 1
            except Exception:
                logger.exception("local artwork attach failed: %s", row["filename"])
                counts.errors += 1

    def _owner_in_directory(self, directory: str):
        """The single media item owning video files directly inside a directory."""
        rows = self.db.query(
            "SELECT DISTINCT l.media_item_type, l.media_item_id"
            " FROM media_file_links l JOIN media_files f ON f.id=l.media_file_id"
            " WHERE f.directory=? AND f.kind='video'",
            (directory,),
        )
        if len(rows) != 1:
            return None
        return rows[0]["media_item_type"], rows[0]["media_item_id"], directory

    def _probe_items(self, location_id: int, counts: ScanCounts) -> None:
        """Probe primary video files lacking probe data; update runtimes."""
        rows = self.db.query(
            "SELECT mf.id, mf.path, l.media_item_type, l.media_item_id"
            " FROM media_files mf"
            " JOIN media_file_links l ON l.media_file_id=mf.id AND l.is_primary=1"
            " WHERE mf.library_location_id=? AND mf.kind='video' AND mf.is_missing=0"
            " AND mf.probe_json IS NULL",
            (location_id,),
        )
        for row in rows:
            self._check_control(location_id, counts)
            try:
                probe = self.probe_tools.probe(row["path"])
                if probe is None:
                    continue
                self.repos.files.set_probe(row["id"], probe.to_dict())
                runtime = int(round(probe.duration_seconds)) if probe.duration_seconds else None
                if runtime and row["media_item_type"] in ("movie", "episode"):
                    if row["media_item_type"] == "movie":
                        movie = self.repos.movies.get(row["media_item_id"])
                        if movie is not None and not movie.runtime_seconds:
                            self.repos.movies.update(row["media_item_id"], {"runtime_seconds": runtime})
                    else:
                        episode = self.repos.tv.get_episode(row["media_item_id"])
                        if episode is not None and not episode.runtime_seconds:
                            self.repos.tv.update_episode(row["media_item_id"], {"runtime_seconds": runtime})
            except Exception:
                logger.exception("probe failed: %s", row["path"])
                counts.errors += 1
