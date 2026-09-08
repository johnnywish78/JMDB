"""Shared seed helpers for API/UI tests: realistic media tree + library data."""
from __future__ import annotations


def seed_media_tree(root) -> None:
    def touch(path, content: bytes = b"x" * 16):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def real_png(color):
        """A tiny valid PNG so renderer tests can assert images truly decode."""
        from io import BytesIO

        from PIL import Image

        buf = BytesIO()
        Image.new("RGB", (24, 36), color).save(buf, format="PNG")
        return buf.getvalue()

    touch(root / "Movies" / "Night Runner (2024)" / "Night.Runner.2024.1080p.BluRay.x264.mkv")
    touch(root / "Movies" / "Night Runner (2024)" / "poster.jpg", real_png((120, 40, 200)))
    touch(root / "Movies" / "Cosmic Drift" / "Cosmic.Drift.2019.720p.WEBRip.mp4")
    touch(root / "TV" / "Solar Winds" / "poster.jpg", real_png((30, 90, 160)))
    touch(root / "TV" / "Solar Winds" / "Season 01" / "season01.jpg", real_png((200, 120, 30)))
    touch(root / "TV" / "Solar Winds" / "Season 01" / "Solar.Winds.S01E01.720p.mkv")
    touch(
        root / "TV" / "Solar Winds" / "Season 01" / "Solar.Winds.S01E01.720p.en.srt",
        b"1\n00:00:01,000 --> 00:00:03,000\nHello solar winds\n\n"
        b"2\n00:00:04,000 --> 00:00:06,000\nSecond line\n\n",
    )
    touch(root / "TV" / "Solar Winds" / "Season 01" / "Solar.Winds.S01E02-E03.720p.mkv")
    touch(root / "TV" / "Desert Show" / "Season 2" / "Desert Show - 2x05.mkv")
    touch(root / "Music" / "Aurora B" / "Midnight Sessions" / "01 - First Light.mp3")
    touch(root / "Music" / "Aurora B" / "Midnight Sessions" / "02 - Dust and Echoes.mp3")


def scan_tree(services, root) -> None:
    from app.library.probe import ProbeTools
    from app.library.scanner import LibraryScanner, ScanOptions

    for sub in ("Movies", "TV", "Music"):
        services.repos.locations.add(str(root / sub))
    scanner = LibraryScanner(
        services.db, services.repos, services.events, ProbeTools(),
        ScanOptions(probe_files=False, checksum_min_mb=0),
    )
    counts = scanner.scan_all()
    assert counts.errors == 0, f"seed scan errors: {counts.errors}"
    return counts


def seed_library(services, home) -> dict:
    """Scan + people/lists/playback state. Returns route ids."""
    media_root = home / "media"
    seed_media_tree(media_root)
    scan_tree(services, media_root)

    repos = services.repos
    profile = services.profile
    night = repos.movies.find_by_title_year("Night Runner", 2024)
    cosmic = repos.movies.find_by_title_year("Cosmic Drift", 2019)
    solar = repos.tv.find_show_by_title("Solar Winds")
    season_id = repos.tv.get_or_create_season(solar.id, 1)
    episodes = repos.tv.episodes_for_season(season_id, profile.id)
    artist = repos.music.find_artist("Aurora B")
    album = repos.music.find_album(artist.id, "Midnight Sessions")

    person_id = repos.people.get_or_create(
        "Dana Starfield", biography="A fearless explorer of inner space.",
        place_of_birth="Tucson, Arizona",
    )
    repos.people.replace_credits("movie", night.id, [
        {"name": "Dana Starfield", "role": "actor", "character": "Runner", "sort_order": 0},
        {"name": "Iris Vega", "role": "director", "job": "Director", "sort_order": 0},
    ])
    repos.people.replace_credits("tv_show", solar.id, [
        {"name": "Dana Starfield", "role": "actor", "character": "Captain", "sort_order": 0},
    ])
    repos.lists.set_favorite(profile.id, "movie", night.id, True)
    repos.lists.set_watchlist(profile.id, "movie", cosmic.id, True)
    repos.playback.mark_watched(profile.id, "movie", cosmic.id)
    repos.playback.save_position(profile.id, "episode", episodes[0]["id"], 300, 1500)
    session_id = repos.playback.start_session(
        profile.id, "movie", cosmic.id,
        repos.files.files_for("movie", cosmic.id)[0].id,
    )
    repos.playback.finish_session(session_id, 6400, 6400, True)
    collection = repos.collections.create("Weekend picks", "For rainy Sundays")
    repos.collections.add_item(collection.id, "movie", night.id)
    repos.collections.add_item(collection.id, "tv_show", solar.id)

    return {
        "movie_id": night.id,
        "movie2_id": cosmic.id,
        "show_id": solar.id,
        "season_id": season_id,
        "episode_id": episodes[0]["id"],
        "episode2_id": episodes[1]["id"],
        "person_id": person_id,
        "album_id": album.id,
        "collection_id": collection.id,
    }
