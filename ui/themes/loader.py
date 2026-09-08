"""Theme loader: QSS files live next to this module; {{TOKENS}} get replaced
with the palette of the active settings (theme + accent)."""
from __future__ import annotations

from pathlib import Path

from app.config.settings import Settings

THEMES_DIR = Path(__file__).resolve().parent

ACCENTS = {
    "amber": {"acc": "#f5b942", "acc2": "#ff8a3d", "ink": "#1a1000"},
    "blue": {"acc": "#5ea8ff", "acc2": "#7c5cff", "ink": "#0a1020"},
    "green": {"acc": "#43d19e", "acc2": "#1ea672", "ink": "#04150d"},
    "rose": {"acc": "#ff5c7a", "acc2": "#b04df0", "ink": "#20050c"},
}


_FALLBACK = """
QWidget { background: #0b0d12; color: #e9ebf2; }
QPushButton { background: #161a24; border: 1px solid #232a38; border-radius: 8px; padding: 6px 12px; }
QLineEdit, QComboBox { background: #161a24; border: 1px solid #232a38; border-radius: 8px; padding: 6px 10px; }
"""


def load_qss(theme: str) -> str:
    file = THEMES_DIR / ("dark.qss" if theme == "dark" else "light.qss")
    if file.exists():
        return file.read_text(encoding="utf-8")
    return _FALLBACK


def apply_theme(app, settings: Settings) -> None:
    theme = settings.get(Settings.THEME) or "dark"
    accent_key = settings.get(Settings.ACCENT) or "amber"
    accent = ACCENTS.get(accent_key, ACCENTS["amber"])
    qss = load_qss(theme)
    for token, value in accent.items():
        qss = qss.replace("{{" + token.upper() + "}}", value)
    app.setStyleSheet(qss)
