"""QApplication construction with a friendly failure mode."""
from __future__ import annotations


def create_qapp(argv: list[str]):
    try:
        from PyQt6.QtGui import QGuiApplication
        from PyQt6.QtWidgets import QApplication
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise SystemExit(
            "JMDB: PyQt6 is not installed.\n"
            "  python3 -m venv .venv && source .venv/bin/activate\n"
            "  pip install -r requirements.txt\n"
            f"({exc})"
        )

    QApplication.setApplicationName("JMDB")
    QApplication.setOrganizationName("JohnnyMedia")
    QApplication.setApplicationDisplayName("JMDB — Johnny Media Database")
    app = QApplication(argv)
    app.setStyle("Fusion")
    if QGuiApplication.primaryScreen() and QGuiApplication.primaryScreen().size().width() >= 1600:
        pass  # room for a future scale-factor policy
    return app
