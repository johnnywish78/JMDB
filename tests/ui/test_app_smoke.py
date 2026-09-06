"""Full-app UI smoke as a pytest: seeded library, every route, player window.

Mirrors scripts/smoke_ui.py but inside the hermetic test environment
(JMDB_HOME → tmp dir, offscreen Qt, no network).
"""
from __future__ import annotations

import pytest

from app.bootstrap.dependencies import Dependencies
from app.bootstrap.startup import prepare_environment


def _seed_media_tree(root) -> None:
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


def _seed(services, home) -> dict:
    from app.library.probe import ProbeTools
    from app.library.scanner import LibraryScanner, ScanOptions

    media_root = home / "media"
    _seed_media_tree(media_root)

    repos = services.repos
    profile = services.profile
    for sub in ("Movies", "TV", "Music"):
        repos.locations.add(str(media_root / sub))
    scanner = LibraryScanner(
        services.db, repos, services.events, ProbeTools(),
        ScanOptions(probe_files=False, checksum_min_mb=0),
    )
    counts = scanner.scan_all()
    assert counts.errors == 0
    assert counts.files_seen == 8

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
        "show_id": solar.id,
        "season_id": season_id,
        "episode_id": episodes[0]["id"],
        "person_id": person_id,
        "album_id": album.id,
    }


def _pump(app, times=20):
    for _ in range(times):
        app.processEvents()


def _drain(qtbot, app):
    """Let async workers and debounce timers settle before teardown."""
    from PyQt6.QtCore import QThreadPool

    QThreadPool.globalInstance().waitForDone(3000)
    _pump(app)
    qtbot.wait(300)  # search debounce interval
    _pump(app)


@pytest.mark.parametrize("pass_no", [1, 2])
def test_all_routes_populated(qtbot, jmdb_home, pass_no):
    prepare_environment()
    deps = Dependencies()
    try:
        services = deps.build()
        ids = _seed(services, jmdb_home)

        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        from ui.themes.system import ThemeManager

        theme = ThemeManager(app, services.settings, services.events)
        theme.apply()
        from ui.app.main_window import MainWindow

        window = MainWindow(services, theme)
        assert len(window.router.routes()) == 21

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
        for route, params in routes:
            window.router.navigate(route, **params)
            _pump(app)
            assert window.router.current_route() == route

        if pass_no == 2:
            # player window lifecycle on the second pass
            playable = services.movies.playable(ids["movie_id"])
            assert playable is not None
            window.context.open_player(playable)
            _pump(app, 8)
            assert window._player_window is not None
            window._player_window.close()
            window._player_window = None

        window.close()
        _drain(qtbot, app)
    finally:
        deps.close()


def test_missing_detail_routes_show_friendly_state(qtbot, jmdb_home):
    """Navigating to a nonexistent id must not crash."""
    prepare_environment()
    deps = Dependencies()
    try:
        services = deps.build()

        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        from ui.themes.system import ThemeManager

        theme = ThemeManager(app, services.settings, services.events)
        theme.apply()
        from ui.app.main_window import MainWindow

        window = MainWindow(services, theme)
        for route, params in [
            ("movie_detail", {"movie_id": 999999}),
            ("show_detail", {"show_id": 999999}),
            ("season_detail", {"season_id": 999999}),
            ("episode_detail", {"episode_id": 999999}),
            ("person_detail", {"person_id": 999999}),
            ("music_detail", {"album_id": 999999}),
        ]:
            window.router.navigate(route, **params)
            _pump(app)
            assert window.router.current_route() == route
        window.close()
        _drain(qtbot, app)
    finally:
        deps.close()
