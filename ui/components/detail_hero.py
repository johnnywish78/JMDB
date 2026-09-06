"""DetailHero: backdrop banner with poster, title, and action buttons."""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.app.context import icon


class DetailHero(QWidget):
    play_clicked = pyqtSignal()
    refresh_clicked = pyqtSignal()
    favorite_toggled = pyqtSignal(bool)
    watchlist_toggled = pyqtSignal(bool)
    watched_toggled = pyqtSignal(bool)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("DetailPanel")
        self.setMinimumHeight(330)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.backdrop = QLabel()
        self.backdrop.setMinimumHeight(330)
        self.backdrop.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.backdrop.setStyleSheet("border-radius: 12px; background: #20242f;")
        outer.addWidget(self.backdrop)

        overlay = QWidget(self.backdrop)
        overlay.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        layout = QHBoxLayout(overlay)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setAlignment(Qt.AlignmentFlag.AlignBottom)

        self.poster = QLabel()
        self.poster.setFixedSize(170, 255)
        self.poster.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.poster.setStyleSheet("border-radius: 8px; background: #2a3040;")
        layout.addWidget(self.poster)

        info = QVBoxLayout()
        info.setSpacing(6)
        self.title_label = QLabel("")
        self.title_label.setObjectName("HeroTitle")
        self.title_label.setWordWrap(True)
        info.addWidget(self.title_label)
        self.tagline = QLabel("")
        self.tagline.setObjectName("HeroTagline")
        self.tagline.setWordWrap(True)
        info.addWidget(self.tagline)
        self.badges = QLabel("")
        self.badges.setObjectName("HeroTagline")
        info.addWidget(self.badges)
        info.addSpacing(6)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.play_button = QPushButton("  ▶  Play")
        self.play_button.setObjectName("PlayButton")
        self.play_button.clicked.connect(self.play_clicked.emit)
        self.favorite_button = QPushButton("♥ Favorite")
        self.favorite_button.setCheckable(True)
        self.favorite_button.toggled.connect(self.favorite_toggled.emit)
        self.watchlist_button = QPushButton("+ Watchlist")
        self.watchlist_button.setCheckable(True)
        self.watchlist_button.toggled.connect(self.watchlist_toggled.emit)
        self.watched_button = QPushButton("✓ Watched")
        self.watched_button.setCheckable(True)
        self.watched_button.toggled.connect(self.watched_toggled.emit)
        self.refresh_button = QPushButton()
        self.refresh_button.setIcon(icon("refresh"))
        self.refresh_button.setToolTip("Refresh metadata from providers")
        self.refresh_button.clicked.connect(self.refresh_clicked.emit)
        for button in (
            self.play_button, self.favorite_button, self.watchlist_button,
            self.watched_button, self.refresh_button,
        ):
            buttons.addWidget(button)
        buttons.addStretch(1)
        info.addLayout(buttons)
        layout.addLayout(info, 1)
        self.overlay = overlay

    # -- content ---------------------------------------------------------------
    def set_movie(self, detail: dict) -> None:
        self.title_label.setText(detail.get("title", ""))
        bits = []
        if detail.get("year"):
            bits.append(str(detail["year"]))
        if detail.get("runtime_seconds"):
            minutes = detail["runtime_seconds"] // 60
            bits.append(f"{minutes} min")
        if detail.get("certification"):
            bits.append(detail["certification"])
        if detail.get("rating") is not None:
            bits.append(f"★ {detail['rating']:.1f}")
        self.badges.setText("  ·  ".join(bits))
        self.tagline.setText(detail.get("tagline", ""))
        self.favorite_button.setChecked(bool(detail.get("is_favorite")))
        self.watchlist_button.setChecked(bool(detail.get("in_watchlist")))
        self.watched_button.setChecked(bool(detail.get("watched")))
        self.play_button.setEnabled(bool(detail.get("files")))
        if detail.get("resume"):
            position = detail["resume"]["position_seconds"]
            self.play_button.setText(f"  ▶  Resume {int(position // 60)}:{int(position % 60):02d}")

    def set_show(self, detail: dict) -> None:
        self.set_movie(detail)
        self.play_button.setText("  ▶  Play next episode")
        if detail.get("next_episode"):
            nxt = detail["next_episode"]
            self.play_button.setText(
                f"  ▶  S{nxt['season_number']:02d}E{nxt['episode_number']:02d}"
            )
        else:
            self.play_button.setText("  ▶  Play")

    def set_generic(self, title: str, subtitle: str = "") -> None:
        self.title_label.setText(title)
        self.tagline.setText(subtitle)
        self.badges.setText("")
        self.play_button.hide()
        self.watched_button.hide()

    def apply_backdrop(self, paths: tuple) -> None:
        backdrop_path, poster_path = paths
        context = getattr(self.window(), "context", None)
        if backdrop_path and context is not None:
            def on_backdrop(key, pixmap):
                self.backdrop.setPixmap(
                    pixmap.scaled(
                        self.backdrop.size(),
                        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )

            context.images.ready.connect(on_backdrop)
            context.images.request(f"detail-backdrop-{id(self)}", backdrop_path, 1000)
        if poster_path and context is not None:
            def on_poster(key, pixmap):
                self.poster.setPixmap(
                    pixmap.scaled(
                        self.poster.size(),
                        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )

            context.images.ready.connect(on_poster)
            context.images.request(f"detail-poster-{id(self)}", poster_path, 400)
