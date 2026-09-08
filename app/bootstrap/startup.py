"""Startup sequence: logging → Qt → container → theme → main window → exec."""
from __future__ import annotations

import logging
import sys
import traceback


def _install_logging(paths) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(paths.log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stderr),
        ],
    )


def run(theme_override: str | None = None, argv: list[str] | None = None) -> int:
    from app.bootstrap.application import create_qapp
    from app.bootstrap.dependencies import Container

    argv = list(sys.argv if argv is None else argv)
    container: Container | None = None
    try:
        from app.config.paths import AppPaths

        paths = AppPaths().ensure()
        _install_logging(paths)
        logging.getLogger("jmdb").info("startup")

        app = create_qapp(argv)
        container = Container()
        if theme_override:
            container.settings.set("theme", theme_override)

        # theme + accent (font metrics stay native)
        from ui.themes.loader import apply_theme

        apply_theme(app, container.settings)

        from ui.app.main import create_main_window

        window = create_main_window(container)
        window.show()

        def _flush() -> None:
            container.close()
            logging.getLogger("jmdb").info("shutdown")

        app.aboutToQuit.connect(_flush)
        return app.exec()
    except SystemExit as exc:  # friendly CLI errors (missing PyQt6 etc.)
        print(exc, file=sys.stderr)
        return 2
    except Exception:  # pragma: no cover - last line of defense
        traceback.print_exc()
        if container is not None:
            container.close()
        return 1
