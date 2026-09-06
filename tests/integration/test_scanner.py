"""End-to-end library scan integration tests (real temp filesystem)."""
from __future__ import annotations

from app.library.scanner import ScanOptions


def test_scan_full_tree(database, repos, profile, events, media_tree, jmdb_home):
    from app.library.probe import ProbeTools
    from app.library.scanner import LibraryScanner

    scanner = LibraryScanner(
        database, repos, events, ProbeTools(),
        ScanOptions(probe_files=False, checksum_min_mb=0),
    )
    for sub in ("Movies", "TV", "Music"):
        repos.locations.add(str(media_tree / sub))
    counts = scanner.scan_all()

    assert counts.files_seen == 8  # 7 media files + poster.jpg
    assert counts.errors == 0

    # movies
    assert repos.movies.count() == 2
    night = repos.movies.find_by_title_year("Night Runner", 2024)
    assert night is not None
    assert repos.movies.find_by_title_year("Cosmic Drift", 2019) is not None
    files = repos.files.files_for("movie", night.id)
    assert len(files) == 1 and files[0].kind == "video"

    # local poster picked up
    poster = repos.artwork.get("movie", night.id, "poster")
    assert poster is not None and poster.local_path.endswith("poster.jpg")

    # tv hierarchy
    assert repos.tv.count_shows() == 2
    solar = repos.tv.find_show_by_title("Solar Winds")
    assert solar is not None
    season_id = repos.tv.get_or_create_season(solar.id, 1)
    episodes = repos.tv.episodes_for_season(season_id, profile.id)
    assert [e["episode_number"] for e in episodes] == [1, 2, 3]  # multi-episode file expands
    desert = repos.tv.find_show_by_title("Desert Show")
    assert desert is not None
    desert_season = repos.tv.get_or_create_season(desert.id, 2)
    desert_eps = repos.tv.episodes_for_season(desert_season, profile.id)
    assert len(desert_eps) == 1 and desert_eps[0]["episode_number"] == 5

    # every episode links back to the correct show and season
    for ep in episodes:
        detail = repos.tv.episode_details(ep["id"], profile.id)
        assert detail["show_title"] == "Solar Winds"
        assert detail["season_number"] == 1

    # movie rows never masquerade as TV: distinct tables, distinct files
    movie_rows, _total = repos.movies.list_page(profile.id)
    assert "Night Runner" in {r["title"] for r in movie_rows}

    # music
    assert repos.music.count_artists() == 1
    assert repos.music.count_albums() == 1
    assert repos.music.count_tracks() == 2
    artist = repos.music.find_artist("Aurora B")
    assert artist is not None
    album = repos.music.find_album(artist.id, "Midnight Sessions")
    tracks = repos.music.tracks_for_album(album.id)
    assert [t["track_number"] for t in tracks] == [1, 2]
    assert all(t["file_path"] for t in tracks)

    # events were published
    published = []
    events.subscribe(object, lambda e: published.append(type(e).__name__))
    scanner.scan_all()
    assert "LibraryScanFinished" in published


def test_scan_detects_removals_and_moves(database, repos, profile, events, media_tree):
    from app.library.probe import ProbeTools
    from app.library.scanner import LibraryScanner

    scanner = LibraryScanner(
        database, repos, events, ProbeTools(), ScanOptions(probe_files=False)
    )
    repos.locations.add(str(media_tree))
    scanner.scan_all()
    assert repos.files.count(missing=False) == 8

    # delete a file and move another
    (media_tree / "Movies" / "Cosmic Drift" / "Cosmic.Drift.2019.720p.WEBRip.mp4").unlink()
    moved_dir = media_tree / "Movies" / "Night Runner (2024)" / "extra"
    moved_dir.mkdir()
    src = media_tree / "Movies" / "Night Runner (2024)" / "Night.Runner.2024.1080p.BluRay.x264.mkv"
    src.rename(moved_dir / "Night.Runner.2024.1080p.BluRay.x264.mkv")

    counts = scanner.scan_all()
    assert counts.files_missing >= 2
    movie = repos.movies.find_by_title_year("Night Runner", 2024)
    assert movie is not None  # still matched via directory context
    files = repos.files.files_for("movie", movie.id)
    assert len(files) == 1  # moved file re-adopted (not duplicated)


def test_scan_cancels(database, repos, profile, events, media_tree):
    from app.domain.events import LibraryScanStarted
    from app.library.probe import ProbeTools
    from app.library.scanner import LibraryScanner

    scanner = LibraryScanner(
        database, repos, events, ProbeTools(), ScanOptions(probe_files=False)
    )
    repos.locations.add(str(media_tree))

    def cancel_on_start(event):
        scanner.cancel()

    events.subscribe(LibraryScanStarted, cancel_on_start)
    counts = scanner.scan_all()
    assert counts.files_seen == 0  # cancelled before any file was processed
    location = repos.locations.list()[0]
    assert location.last_scan_status == "cancelled"


def test_scan_pauses_and_resumes(database, repos, profile, events, media_tree):
    import threading

    from app.domain.events import LibraryScanProgress
    from app.library.probe import ProbeTools
    from app.library.scanner import LibraryScanner

    scanner = LibraryScanner(
        database, repos, events, ProbeTools(), ScanOptions(probe_files=False)
    )
    repos.locations.add(str(media_tree))
    paused_seen = []

    def pause_on_first_progress(event):
        if not isinstance(event, LibraryScanProgress) or paused_seen:
            return
        paused_seen.append(event)
        scanner.pause()
        threading.Timer(0.5, scanner.resume).start()

    events.subscribe(object, pause_on_first_progress)
    scanner.CHECK_INTERVAL = 1
    counts = scanner.scan_all()
    assert paused_seen, "scanner never paused"
    assert counts.files_seen == 8  # resumed and completed the scan


def test_scan_resilient_to_bad_files(database, repos, profile, events, tmp_path):
    """A malformed filename or unreadable entry must not stop the scan."""
    from app.library.probe import ProbeTools
    from app.library.scanner import LibraryScanner

    root = tmp_path / "messy"
    root.mkdir()
    (root / "....mkv").write_bytes(b"")           # empty title
    (root / "Movie With Year 2021.mkv").write_bytes(b"x" * 100)
    (root / "Weird.File.S01E10.mkv").write_bytes(b"x" * 100)
    (root / "song with no tags.mp3").write_bytes(b"x" * 100)  # no artist → skipped

    scanner = LibraryScanner(
        database, repos, events, ProbeTools(), ScanOptions(probe_files=False)
    )
    repos.locations.add(str(root))
    counts = scanner.scan_all()
    assert counts.errors == 0
    assert repos.movies.count() >= 1
    assert repos.tv.count_shows() >= 1
