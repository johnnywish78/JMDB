"""Qt application assembly and lifecycle."""
from __future__ import annotations

import logging
import sys

from PyQt6.QtWidgets import QApplication

from app.bootstrap.startup import prepare_environment
from app.bootstrap.logging_setup import configure_logging
from ui.app.main_window import MainWindow
from ui.themes.system import ThemeManager

logger = logging.getLogger(__name__)


def create_qt_app() -> QApplication:
    prepare_environment()
    app = QApplication(sys.argv)
    app.setApplicationName("JMDB")
    app.setOrganizationName("JMDB")
    return app


def run() -> int:
    """Full application lifecycle. Returns an exit code."""
    prepare_environment()

    # logging first (before Qt) so everything is captured
    from app.config.paths import Paths

    paths = Paths.create()
    paths.ensure_directories()
    redactor = configure_logging(paths.logs)
    logger.info("JMDB starting")

    deps = None
    app = None
    try:
        from app.bootstrap.dependencies import Dependencies
        from app.bootstrap.logging_setup import install_redactor

        deps = Dependencies()
        install_redactor(redactor, deps.secrets.active_secrets())
        services = deps.build()

        app = create_qt_app()
        theme_manager = ThemeManager(app, services.settings, services.events)
        theme_manager.apply()

        window = MainWindow(services, theme_manager)
        window.show()

        from app import __version__

        logger.info("JMDB %s window shown", __version__)
        exit_code = app.exec()
        logger.info("JMDB exiting with code %s", exit_code)
        return exit_code
    except Exception:
        logger.exception("fatal startup error")
        # last-resort visible error for the user
        try:
            from PyQt6.QtWidgets import QMessageBox, QApplication

            if QApplication.instance() is None:
                QApplication(sys.argv)
            QMessageBox.critical(
                None,
                "JMDB failed to start",
                "JMDB hit a fatal error during startup.\n\n"
                "See the log file for details:\n"
                f"{paths.logs / 'jmdb.log'}",
            )
        except Exception:
            pass
        return 1
    finally:
        if deps is not None:
            deps.close()
