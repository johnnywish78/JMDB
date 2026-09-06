"""Headless smoke test: build the full app, seed a real library, visit every
route twice (populated paths), and open the player window.

Run:  QT_QPA_PLATFORM=offscreen python3 scripts/smoke_ui.py [--keep-home]
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import traceback

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
os.environ.setdefault(
    "QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox --disable-gpu --disable-dev-shm-usage"
)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication

from app.bootstrap.dependencies import Dependencies
from app.bootstrap.logging_setup import configure_logging
from app.bootstrap.startup import prepare_environment
from app.config.paths import Paths


def seed_media_tree(root) -> None:
    def touch(path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x" * 16)

    touch(root / "Movies" / "Night Runner (2024)" / "Night.Runner.2024.1080p.BluRay.x264.mkv")
    touch(root / "Movies" / "Night Runner (2024)" / "poster.jpg")
    touch(root / "Movies" / "Cosmic Drift" / "Cosmic.Drift.2019.720p.WEBRip.mp4")
    touch(root / "TV" / "Solar Winds" / "Season 01" / "Solar.Winds.S01E01.720p.mkv")
    touch(root / "TV" / "Solar Winds" / "Season 01" / "Solar.Winds.S01E02-E03.720p.mkv")
    touch(root / "TV" / "Desert Show" / "Season 2" / "Desert Show - 2x05.mkv")
    touch(root / "Music" / "Aurora B" / "Midnight Sessions" / "01 - First Light.mp3")
    touch(root / "Music" / "Aurora B" / "Midnight Sessions" / "02 - Dust and Echoes.mp3")


def seed_library(services, home) -> dict:
    """Scan the fake tree, add people/lists/playback state. Returns route ids."""
    from app.library.probe import ProbeTools
    from app.library.scanner import LibraryScanner, ScanOptions

    media_root = home / "media"
    seed_media_tree(media_root)

    repos = services.repos
    profile = services.profile
    for sub in ("Movies", "TV", "Music"):
        repos.locations.add(str(media_root / sub))
    scanner = LibraryScanner(
        services.db, repos, services.events, ProbeTools(),
        ScanOptions(probe_files=False, checksum_min_mb=0),
    )
    counts = scanner.scan_all()
    print(f"seed scan: {counts.files_seen} files, {counts.errors} errors")

    # enrich: people + credits + rating so detail screens have content
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
    repos.lists.set_rating(profile.id, "movie", night.id, 8.5)
    repos.playback.mark_watched(profile.id, "movie", cosmic.id)
    repos.playback.save_position(profile.id, "episode", episodes[0]["id"], 300, 1500)
    repos.playback.save_position(profile.id, "movie", night.id, 240, 6400)
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
        "show_id": solar.id,
        "season_id": season_id,
        "episode_id": episodes[0]["id"],
        "person_id": person_id,
        "album_id": album.id,
    }


def main() -> int:
    keep_home = "--keep-home" in sys.argv
    home = PathLike = None
    tmp = None
    if keep_home:
        from pathlib import Path

        home = Path(tempfile.mkdtemp(prefix="jmdb-smoke-"))
    else:
        tmp = tempfile.mkdtemp(prefix="jmdb-smoke-")
        from pathlib import Path

        home = Path(tmp)
    os.environ["JMDB_HOME"] = str(home)

    prepare_environment()
    paths = Paths.create()
    paths.ensure_directories()
    configure_logging(paths.logs)

    failures: list[str] = []

    deps = Dependencies()
    try:
        services = deps.build()
        ids = seed_library(services, home)
        print(f"seeded ids: {ids}")

        app = QApplication(sys.argv)
        app.setApplicationName("JMDB-smoke")
        from ui.themes.system import ThemeManager

        theme = ThemeManager(app, services.settings, services.events)
        theme.apply()
        from ui.app.main_window import MainWindow

        window = MainWindow(services, theme)
        print(f"routes registered: {len(window.router.routes())}")

        routes = [
            ("home", {}),
            ("movies", {}),
            ("movie_detail", {"movie_id": ids["movie_id"]}),
            ("tv", {}),
            ("show_detail", {"show_id": ids["show_id"]}),
            ("season_detail", {"season_id": ids["season_id"]}),
            ("episode_detail", {"episode_id": ids["episode_id"]}),
            ("people", {}),
            ("person_detail", {"person_id": ids["person_id"]}),
            ("music", {}),
            ("music_detail", {"album_id": ids["album_id"]}),
            ("collections", {}),
            ("favorites", {}),
            ("watchlist", {}),
            ("history", {}),
            ("search", {"query": "solar"}),
            ("recommendations", {}),
            ("statistics", {}),
            ("browser", {}),
            ("services", {}),
            ("settings", {}),
        ]

        # two passes: second pass re-visits (refresh paths, art handler cleanup)
        for pass_no in (1, 2):
            for route, params in routes:
                try:
                    window.router.navigate(route, **params)
                    for _ in range(20):
                        app.processEvents()
                    if pass_no == 1:
                        print(f"  OK  {route}")
                except Exception:
                    label = route if pass_no == 1 else f"{route} (pass 2)"
                    failures.append(label)
                    print(f"  FAIL {label}")
                    traceback.print_exc()

        # player window opens for a real playable
        try:
            playable = services.movies.playable(ids["movie_id"])
            window.context.open_player(playable)
            for _ in range(10):
                app.processEvents()
            print("  OK  player window opened")
            if window._player_window is not None:
                window._player_window.close()
                window._player_window = None
        except Exception:
            failures.append("player")
            print("  FAIL player")
            traceback.print_exc()

        window.close()
        for _ in range(10):
            app.processEvents()
    finally:
        deps.close()
        if tmp and not keep_home:
            shutil.rmtree(tmp, ignore_errors=True)

    if failures:
        print(f"\nSMOKE FAILED: {len(failures)} item(s): {failures}")
        return 1
    print("\nSMOKE PASSED: all routes (populated, 2 passes) + player window")
    return 0


if __name__ == "__main__":
    sys.exit(main())
