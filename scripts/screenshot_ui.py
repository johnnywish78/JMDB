"""Offscreen screenshots of every screen (populated) for visual QA.

Run:  QT_QPA_PLATFORM=offscreen python3 scripts/screenshot_ui.py [outdir]
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
os.environ.setdefault(
    "QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox --disable-gpu --disable-dev-shm-usage"
)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtCore import QSize
from PyQt6.QtWidgets import QApplication

from app.bootstrap.dependencies import Dependencies
from app.bootstrap.logging_setup import configure_logging
from app.bootstrap.startup import prepare_environment
from app.config.paths import Paths
from scripts.smoke_ui import seed_library

OUT = sys.argv[1] if len(sys.argv) > 1 else "screenshots"


def main() -> int:
    home = tempfile.mkdtemp(prefix="jmdb-shots-")
    os.environ["JMDB_HOME"] = home
    from pathlib import Path

    home = Path(home)

    prepare_environment()
    paths = Paths.create()
    paths.ensure_directories()
    configure_logging(paths.logs)

    deps = Dependencies()
    try:
        services = deps.build()
        ids = seed_library(services, home)

        app = QApplication(sys.argv)
        app.setApplicationName("JMDB-shots")
        from ui.themes.system import ThemeManager

        theme = ThemeManager(app, services.settings, services.events)
        theme.apply()
        from ui.app.main_window import MainWindow

        window = MainWindow(services, theme)
        window.resize(1440, 900)
        window.show()
        for _ in range(30):
            app.processEvents()

        os.makedirs(OUT, exist_ok=True)
        shots = [
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
            ("history", {}),
            ("search", {"query": "solar"}),
            ("recommendations", {}),
            ("statistics", {}),
            ("browser", {}),
            ("services", {}),
            ("settings", {}),
        ]
        for route, params in shots:
            window.router.navigate(route, **params)
            for _ in range(30):
                app.processEvents()
            pix = window.grab()
            target = os.path.join(OUT, f"{route}.png")
            pix.save(target)
            print(f"saved {target}")

        # player window
        playable = services.movies.playable(ids["movie_id"])
        window.context.open_player(playable)
        for _ in range(20):
            app.processEvents()
        window._player_window.resize(QSize(1280, 720))
        for _ in range(5):
            app.processEvents()
        window._player_window.grab().save(os.path.join(OUT, "player.png"))
        print(f"saved {OUT}/player.png")
        window._player_window.close()
        window._player_window = None

        window.close()
        for _ in range(10):
            app.processEvents()
    finally:
        deps.close()
        shutil.rmtree(home, ignore_errors=True)
    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
