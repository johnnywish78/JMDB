"""MediaCard — poster + meta + hover actions, fed by repository row dicts."""
from __future__ import annotations

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

CARD_W, POSTER_H = 172, 258


class MediaCard(QWidget):
    openRequested = pyqtSignal(dict)
    playRequested = pyqtSignal(dict)
    favoriteToggled = pyqtSignal(dict, bool)
    watchlistToggled = pyqtSignal(dict, bool)

    def __init__(self, container, item: dict, subtitle: str = "", parent=None):
        super().__init__(parent)
        self.container = container
        self.item = item
        self.setObjectName("MediaCard")
        self.setFixedSize(CARD_W, POSTER_H + 64)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(item.get("title", ""))

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.poster = QLabel()
        self.poster.setFixedSize(CARD_W, POSTER_H)
        self.poster.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.poster.setPixmap(
            container.artwork.poster_pixmap(item, CARD_W * 2, POSTER_H * 2)
            .scaled(CARD_W, POSTER_H, Qt.AspectRatioMode.IgnoreAspectRatio,
                    Qt.TransformationMode.SmoothTransformation))
        root.addWidget(self.poster, 0, Qt.AlignmentFlag.AlignHCenter)

        rating = item.get("rating") or 0
        self.badge = QLabel(f"★ {rating:.1f}", self.poster)
        if rating <= 0:
            self.badge.hide()
        else:
            self.badge.setObjectName("RatingBadge")
            self.badge.adjustSize()
            self.badge.move(6, 6)

        meta = QVBoxLayout()
        meta.setContentsMargins(8, 6, 8, 6)
        meta.setSpacing(1)
        title = QLabel(item.get("title", "?"))
        title.setObjectName("CardTitle")
        title.setWordWrap(False)
        year = item.get("year") or ""
        kind = item.get("kind", "")
        line = subtitle or (" · ".join(str(p) for p in (year, kind) if p))
        sub = QLabel(line if line else " ")
        sub.setObjectName("CardMeta")
        meta.addWidget(title)
        meta.addWidget(sub)
        root.addLayout(meta)

        # hover actions
        self.actions = QWidget(self.poster)
        self.actions.setObjectName("CardActions")
        hb = QHBoxLayout(self.actions)
        hb.setContentsMargins(8, 0, 8, 10)
        self.btn_play = QPushButton("▶")
        self.btn_fav = QPushButton("♥")
        self.btn_wl = QPushButton("✚")
        for b, tip in ((self.btn_play, "Play"), (self.btn_fav, "Favorite"), (self.btn_wl, "Watchlist")):
            b.setFixedSize(36, 30)
            b.setToolTip(tip)
            hb.addWidget(b)
        self.actions.setFixedSize(CARD_W, 40)
        self.actions.move(0, POSTER_H - 42)
        self.actions.setStyleSheet(
            "QWidget#CardActions { background: rgba(8,9,13,170); border-bottom-left-radius: 12px;"
            " border-bottom-right-radius: 12px; }"
            "QPushButton { background: rgba(20,22,30,200); color: white; border: none; border-radius: 8px; }"
            "QPushButton:hover { background: #f5b942; color: black; }")
        self.actions.hide()

        self.btn_play.clicked.connect(lambda _=None: self.playRequested.emit(self.item))
        self.btn_fav.clicked.connect(self._fav)
        self.btn_wl.clicked.connect(self._wl)
        self._fav_state = item["id"] in container.state_repo.favorites() if item.get("id") else False
        self._wl_state = item["id"] in container.state_repo.watchlist() if item.get("id") else False
        self._paint_flags()

    def _fav(self) -> None:
        self._fav_state = self.container.state_repo.toggle_favorite(self.item["id"])
        self.favoriteToggled.emit(self.item, self._fav_state)
        self._paint_flags()
        self.container.bus.emit("media.state_changed", id=self.item["id"])

    def _wl(self) -> None:
        self._wl_state = self.container.state_repo.toggle_watchlist(self.item["id"])
        self.watchlistToggled.emit(self.item, self._wl_state)
        self._paint_flags()
        self.container.bus.emit("media.state_changed", id=self.item["id"])

    def _paint_flags(self) -> None:
        self.btn_fav.setText("♥" if self._fav_state else "♡")
        self.btn_wl.setText("✓" if self._wl_state else "✚")

    def enterEvent(self, event) -> None:
        self.actions.show()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.actions.hide()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.openRequested.emit(self.item)
        super().mousePressEvent(event)

    def refresh_poster(self, item: dict) -> None:
        self.item = item
        self.poster.setPixmap(
            self.container.artwork.poster_pixmap(item, CARD_W, POSTER_H))

    def sizeHint(self) -> QSize:
        return QSize(CARD_W, POSTER_H + 64)
