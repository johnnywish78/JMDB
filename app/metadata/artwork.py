"""Artwork storage + deterministic placeholder poster/backdrop renderer.
Every title gets a designed offline fallback; real art is downloaded lazily
and cached with stable filenames keyed by (media-id, type, url)."""
from __future__ import annotations

import hashlib
from pathlib import Path

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None  # type: ignore

PALETTES = [
    ("#0f2027", "#2c5364"), ("#42275a", "#734b6d"), ("#ff512f", "#dd2476"),
    ("#16222a", "#3a6073"), ("#e65c00", "#f9d423"), ("#141e30", "#243b55"),
    ("#360033", "#0b8793"), ("#000428", "#004e92"), ("#870000", "#190a05"),
    ("#134e5e", "#71b280"), ("#24243e", "#302b63"), ("#cb356b", "#bd3f32"),
]

ARTWORK_SUBDIRS = {"poster": "posters", "backdrop": "backdrops"}


class ArtworkStore:
    def __init__(self, paths):
        self.paths = paths

    # --------------------------------------------------------- remote → local
    def local_for(self, url: str | None, key: str,
                  kind: str = "poster") -> str | None:
        """Download url once into artwork dir; return local path or None."""
        if not url or requests is None:
            return None
        subdir = ARTWORK_SUBDIRS.get(kind, "posters")
        folder = self.paths.artwork_dir / subdir
        folder.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha1(f"{key}|{url}".encode()).hexdigest()[:16]
        suffix = ".jpg" if url.lower().endswith((".jpg", ".jpeg")) else ".png"
        target = folder / f"{digest}{suffix}"
        if target.exists():
            return str(target)
        try:
            r = requests.get(url, timeout=10, headers={"User-Agent": "JMDB/1.0"})
            r.raise_for_status()
            target.write_bytes(r.content)
            return str(target)
        except Exception:
            return None

    # ------------------------------------------------------ offline poster
    @staticmethod
    def placeholder_pixmap(title: str, year: int | None, width: int, height: int,
                           kind: str = "poster"):
        """Deterministic designed poster (gradient + monogram + title band)."""
        from PyQt6.QtCore import QRect, Qt
        from PyQt6.QtGui import QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QPixmap

        digest = int(hashlib.sha1(title.encode()).hexdigest(), 16)
        c1, c2 = PALETTES[digest % len(PALETTES)]
        pix = QPixmap(width, height)
        pix.fill(QColor(c1))
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        grad = QLinearGradient(0, 0, width * 0.4, height)
        grad.setColorAt(0, QColor(c1))
        grad.setColorAt(1, QColor(c2))
        painter.fillRect(0, 0, width, height, grad)
        # diagonal beams motif
        painter.setOpacity(0.07)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("white"))
        step = max(18, width // 8)
        for x in range(-height, width, step * 3):
            painter.drawRect(x, -10, 2, height + 20)
        painter.setOpacity(1)
        # monogram
        letter = (title.replace("The ", "").replace("A ", "").replace("An ", "")[:1] or "?").upper()
        font = QFont("Sans Serif", int(width * 0.30), QFont.Weight.Bold)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255, 235))
        painter.drawText(QRect(0, int(height * 0.12), width, int(height * 0.55)),
                         Qt.AlignmentFlag.AlignCenter, letter)
        # year chip
        if year:
            painter.setFont(QFont("Sans Serif", max(9, width // 16)))
            painter.setPen(QColor(255, 255, 255, 170))
            painter.drawText(width - 14, 0, 12, 28, Qt.AlignmentFlag.AlignCenter, str(year))
        # title band
        band_h = max(34, height // 7)
        painter.fillRect(QRect(0, height - band_h, width, band_h), QColor(0, 0, 0, 150))
        small = QFont("Sans Serif", max(8, width // 15), QFont.Weight.DemiBold)
        painter.setFont(small)
        painter.setPen(QColor("white"))
        metrics = QFontMetrics(small)
        elided = metrics.elidedText(title, Qt.TextElideMode.ElideRight, width - 14)
        painter.drawText(QRect(7, height - band_h, width - 14, band_h),
                         Qt.AlignmentFlag.AlignVCenter, elided)
        painter.end()
        return pix

    def poster_pixmap(self, item: dict, width: int, height: int) -> object:
        """Resolve poster: local file if already cached, download URL, else placeholder."""
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QPixmap

        raw = item.get("poster_path") or item.get("poster_url")
        if raw:
            local = self._resolve_local(raw, item.get("id"), "poster")
            if local:
                pix = QPixmap(local)
                if not pix.isNull():
                    return pix.scaled(width, height, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                      Qt.TransformationMode.SmoothTransformation)
        return self.placeholder_pixmap(item.get("title", "?"), item.get("year"), width, height)

    def backdrop_pixmap(self, item: dict, width: int, height: int) -> object:
        """Resolve backdrop: local file if already cached, download URL, else placeholder."""
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QPixmap

        raw = item.get("backdrop_path") or item.get("backdrop_url")
        if raw:
            local = self._resolve_local(raw, item.get("id"), "backdrop")
            if local:
                pix = QPixmap(local)
                if not pix.isNull():
                    return pix.scaled(width, height, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                      Qt.TransformationMode.SmoothTransformation)
        return self.placeholder_pixmap(item.get("title", "?"), item.get("year"), width, height,
                                       kind="backdrop")

    def _resolve_local(self, url_or_path: str, media_id, kind: str) -> str | None:
        """Return a local path if the URL has been downloaded; otherwise download now."""
        if url_or_path.startswith("http"):
            key = f"m{media_id or 0}"
            return self.local_for(url_or_path, key, kind)
        # Already a local path
        p = Path(url_or_path)
        if p.is_file():
            return str(p)
        return None
