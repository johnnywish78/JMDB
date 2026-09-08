"""Player screen: hosts a playback backend widget + transport controls.
Drives the backend, delegates all persistence decisions to PlaybackService."""
from __future__ import annotations

import logging
import os

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from app.config.settings import Settings
from app.domain.models import PlaybackPayload
from app.domain.value_objects import clock
from app.playback.backends.base import AbstractPlaybackBackend
from app.playback.backends.builtin import ExternalBackend, MPVBackend, VLCBackend
from app.playback.backends.qt_backend import QtMultimediaBackend

log = logging.getLogger("jmdb.player")

BACKEND_CLASSES = {
    "mpv": MPVBackend,
    "vlc": VLCBackend,
    "qt": QtMultimediaBackend,
    "external": ExternalBackend,
}
# MPV is preferred on Linux where VLC hits VAAPI/VDPAU issues
AUTO_ORDER = ("mpv", "vlc", "qt", "external")
SPEEDS = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0]
DEFAULT_VOLUME = 70
RESUME_THRESHOLD_MIN = 5  # only save resume if >5 min watched


class PlayerScreen(QWidget):
    """Created per session by MainWindow (not router-cached)."""

    def __init__(self, container, payload: PlaybackPayload, on_closed=None, parent=None):
        super().__init__(parent)
        self.c = container
        self.service = container.playback
        self.payload = payload
        self.on_closed = on_closed
        self.backend: AbstractPlaybackBackend | None = None
        self._duration = payload.duration_s or 0
        self._up_next_payload: PlaybackPayload | None = None
        self._is_fullscreen = False
        self.setObjectName("PlayerScreen")
        self.setStyleSheet("QWidget#PlayerScreen{background:#000}")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── top strip ────────────────────────────────────────────────────────
        top = QHBoxLayout()
        top.setContentsMargins(12, 8, 12, 4)
        btn_back = QPushButton("◀ Back")
        btn_back.clicked.connect(self._close)
        btn_back.setFixedHeight(30)
        title = QLabel(f"<b>{payload.title}</b>"
                       f" <span style='color:#aaa'>{payload.subtitle}</span>")
        title.setStyleSheet("color:#eee")
        self.backend_tag = QLabel("")
        self.backend_tag.setStyleSheet("color:#555;font-size:11px;letter-spacing:2px")
        top.addWidget(btn_back)
        top.addWidget(title, 1)
        top.addWidget(self.backend_tag)
        root.addLayout(top)

        # ── video host ───────────────────────────────────────────────────────
        self.video_host = QFrame()
        self.video_host.setStyleSheet("background:#000")
        self.video_host.setFrameShape(QFrame.Shape.NoFrame)
        vh_layout = QVBoxLayout(self.video_host)
        vh_layout.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self.video_host, 1)

        # ── up-next overlay ──────────────────────────────────────────────────
        self.up_next = QFrame(self.video_host)
        self.up_next.setStyleSheet(
            "background:rgba(15,17,24,235);border:1px solid #2c3446;border-radius:12px")
        self.up_next.setFixedWidth(360)
        un_layout = QHBoxLayout(self.up_next)
        un_layout.setContentsMargins(14, 10, 14, 10)
        self.up_next_lbl = QLabel("")
        self.up_next_lbl.setStyleSheet("color:#eee")
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self._cancel_next)
        un_layout.addWidget(self.up_next_lbl, 1)
        un_layout.addWidget(btn_cancel)
        self.up_next.hide()

        # ── controls panel ───────────────────────────────────────────────────
        ctrl = QFrame()
        ctrl.setObjectName("PlayerControls")
        ctrl.setStyleSheet("""
            #PlayerControls { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                stop:0 rgba(20,22,32,240), stop:1 rgba(10,11,18,250)); }
        """)
        cl = QVBoxLayout(ctrl)
        cl.setContentsMargins(16, 8, 16, 12)
        cl.setSpacing(6)

        # Seek bar
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, max(1, self._duration))
        self.slider.setFixedHeight(20)
        cl.addWidget(self.slider)

        # Transport row
        tr = QHBoxLayout()
        tr.setSpacing(8)

        self.btn_rewind = QPushButton("⏪ 10s")
        self.btn_rewind.setFixedHeight(32)
        self.btn_pp = QPushButton("⏸")
        self.btn_pp.setFixedWidth(56)
        self.btn_pp.setFixedHeight(32)
        self.btn_fwd = QPushButton("10s ⏩")
        self.btn_fwd.setFixedHeight(32)
        self.btn_prev = QPushButton("⏮ Prev")
        self.btn_prev.setFixedHeight(32)
        self.btn_next = QPushButton("⏭ Next")
        self.btn_next.setFixedHeight(32)
        self.time_lbl = QLabel("0:00 / 0:00")
        self.time_lbl.setStyleSheet("color:#aaa;font-size:12px")
        self.speed_box = QComboBox()
        self.speed_box.addItems([f"{s}x" for s in SPEEDS])
        self.speed_box.setFixedWidth(56)
        self.btn_mute = QPushButton("🔊")
        self.btn_mute.setFixedWidth(36)
        self.btn_mute.setFixedHeight(32)
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(DEFAULT_VOLUME)
        self.volume_slider.setFixedWidth(90)
        self.btn_fs = QPushButton("⛶")
        self.btn_fs.setFixedWidth(36)
        self.btn_fs.setFixedHeight(32)
        self.btn_fs.setToolTip("Fullscreen (F)")

        for b in (self.btn_rewind, self.btn_fwd, self.btn_prev, self.btn_next,
                  self.btn_mute, self.btn_fs):
            b.setFixedHeight(32)

        tr.addWidget(self.btn_prev)
        tr.addWidget(self.btn_rewind)
        tr.addWidget(self.btn_pp)
        tr.addWidget(self.btn_fwd)
        tr.addWidget(self.btn_next)
        tr.addWidget(self.time_lbl, 1)
        tr.addWidget(QLabel("Speed"))
        tr.addWidget(self.speed_box)
        tr.addWidget(self.btn_mute)
        tr.addWidget(self.volume_slider)
        tr.addWidget(self.btn_fs)
        cl.addLayout(tr)
        root.addWidget(ctrl)

        # ── wiring ───────────────────────────────────────────────────────────
        self.btn_pp.clicked.connect(self._toggle)
        self.btn_rewind.clicked.connect(lambda: self._skip(-10))
        self.btn_fwd.clicked.connect(lambda: self._skip(10))
        self.btn_prev.clicked.connect(self._prev)
        self.btn_next.clicked.connect(self._next)
        self.slider.sliderReleased.connect(
            lambda: self.backend and self.backend.seek_s(self.slider.value()))
        self.speed_box.currentIndexChanged.connect(
            lambda i: self.backend and self.backend.set_speed(SPEEDS[i]))
        self.volume_slider.valueChanged.connect(
            lambda v: self.backend and self.backend.set_volume(v))
        self.btn_mute.clicked.connect(self._mute_toggle)
        self.btn_fs.clicked.connect(self._toggle_fullscreen)

        self._next_timer = QTimer(self)
        self._next_timer.setSingleShot(True)
        self._next_timer.timeout.connect(self._start_next)

        # Remember default volume from settings
        saved_vol = int(self.c.settings.get(Settings.VOLUME, DEFAULT_VOLUME))
        self.volume_slider.setValue(saved_vol)

        QTimer.singleShot(0, self._start)

    # --------------------------------------------------------------- start
    def _start(self) -> None:
        path = self.payload.file_path
        if not path or not os.path.exists(path):
            from ui.components.common import EmptyState
            self.video_host.layout().addWidget(EmptyState(
                "Media file not found",
                f"'{self.payload.title}' has no readable file_path — rescan its folder.\n\n"
                f"path: {path or '—'}"))
            return
        self.backend = self._create_backend()
        if self.backend is None:
            return
        self.backend_tag.setText(self.backend.backend_name.upper())
        widget = self.backend.video_widget()
        self.video_host.layout().addWidget(widget)
        self.backend.positionChanged.connect(self._on_position)
        self.backend.durationChanged.connect(self._on_duration)
        self.backend.finished.connect(self._on_finished)
        self.backend.errorOccurred.connect(self._on_error)
        self.service.session_started(self.payload)
        resume = self.service.resume_seconds(self.payload)
        self.backend.open_media(path, start_seconds=resume)
        self.backend.play()

    def _create_backend(self):
        pref = self.c.settings.get(Settings.BACKEND, "auto")
        order = ([pref] + [b for b in AUTO_ORDER if b != pref]
                 if pref != "auto" else list(AUTO_ORDER))
        last_err = ""
        for backend_id in order:
            cls = BACKEND_CLASSES[backend_id]
            desc = cls.descriptor()
            if not desc.available:
                last_err = desc.reason or f"{desc.name} unavailable"
                continue
            try:
                return cls(self)
            except Exception as exc:
                last_err = f"{cls.backend_name} init failed: {exc}"
                log.warning("backend %s failed, trying next: %s", cls.backend_id, exc)
                continue
        log.error("all backends failed: %s", last_err)
        from ui.components.common import EmptyState
        self.video_host.layout().addWidget(EmptyState(
            "No working playback backend",
            f"Last error: {last_err}\n\n"
            "Install mpv (recommended) or VLC, or PyQt6 multimedia codecs."))
        return None

    # ------------------------------------------------------------- signals
    def _on_position(self, pos: int) -> None:
        if not self.slider.isSliderDown():
            self.slider.setValue(pos)
        dur = self._duration or (self.backend.duration_s() if self.backend else 0)
        self.time_lbl.setText(f"{clock(pos)} / {clock(dur)}")
        if self.backend and dur:
            self.service.tick(pos, dur)

    def _on_duration(self, dur: int) -> None:
        self._duration = dur
        self.slider.setRange(0, max(1, dur))

    def _on_error(self, msg: str) -> None:
        window = self.window()
        if window and hasattr(window, "statusBar"):
            window.statusBar().showMessage(f"Playback error: {msg}", 8000)
        log.warning("player error: %s", msg)

    def _on_finished(self) -> None:
        nxt = self.service.session_finished()
        if nxt:
            self._up_next_payload = nxt
            self.up_next_lbl.setText(
                f"<b>Up next</b><br>{nxt.subtitle}<br><i>starting in 5s …</i>")
            self.up_next.adjustSize()
            self.up_next.move(
                max(8, self.video_host.width() - self.up_next.width() - 16),
                max(8, self.video_host.height() - self.up_next.height() - 16))
            self.up_next.show()
            self._next_timer.start(5000)
        else:
            self._close()

    # -------------------------------------------------------- up next flow
    def _cancel_next(self) -> None:
        self._next_timer.stop()
        self.up_next.hide()
        self._up_next_payload = None
        self._close()

    def _start_next(self) -> None:
        nxt, self._up_next_payload = self._up_next_payload, None
        self.up_next.hide()
        if nxt is None or self.backend is None:
            self._close()
            return
        self.payload = nxt
        self.service.session_started(nxt)
        self._duration = nxt.duration_s or 0
        self.slider.setRange(0, max(1, self._duration))
        self.backend.open_media(nxt.file_path or "", start_seconds=0)
        self.backend.play()

    # ------------------------------------------------------------ controls
    def _toggle(self) -> None:
        if not self.backend:
            return
        if self.backend.is_playing():
            self.backend.pause()
            self.btn_pp.setText("▶")
        else:
            self.backend.play()
            self.btn_pp.setText("⏸")

    def _skip(self, seconds: int) -> None:
        if self.backend:
            self.backend.seek_s(max(0, self.backend.position_s() + seconds))

    def _prev(self) -> None:
        """Play previous item (if available via playlist logic)."""
        self._toast("Previous not implemented yet")

    def _next(self) -> None:
        """Play next item (triggers autoplay-next if configured)."""
        if self.backend:
            self.backend.stop()
            self._on_finished()

    def _mute_toggle(self) -> None:
        if not self.backend:
            return
        current = self.volume_slider.value()
        if current > 0:
            self._last_vol = current
            self.volume_slider.setValue(0)
            self.btn_mute.setText("🔇")
        else:
            vol = getattr(self, "_last_vol", DEFAULT_VOLUME)
            self.volume_slider.setValue(vol)
            self.btn_mute.setText("🔊")

    def _toggle_fullscreen(self) -> None:
        self._is_fullscreen = not self._is_fullscreen
        if self._is_fullscreen:
            self.setWindowState(self.windowState() | Qt.WindowState.WindowFullScreen)
            self.btn_fs.setText("⛶")
        else:
            self.setWindowState(self.windowState() & ~Qt.WindowState.WindowFullScreen)
            self.btn_fs.setText("⛶")

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if key == Qt.Key.Key_Space:
            self._toggle()
        elif key == Qt.Key.Key_Escape:
            if self._is_fullscreen:
                self._toggle_fullscreen()
            else:
                self._close()
        elif key == Qt.Key.Key_Right:
            self._skip(10)
        elif key == Qt.Key.Key_Left:
            self._skip(-10)
        elif key == Qt.Key.Key_Up:
            if self.backend:
                self.volume_slider.setValue(min(100, self.volume_slider.value() + 5))
        elif key == Qt.Key.Key_Down:
            if self.backend:
                self.volume_slider.setValue(max(0, self.volume_slider.value() - 5))
        elif key == Qt.Key.Key_M:
            self._mute_toggle()
        elif key == Qt.Key.Key_F:
            self._toggle_fullscreen()
        elif key == Qt.Key.Key_N:
            self._next()
        elif key == Qt.Key.Key_P:
            self._prev()
        else:
            super().keyPressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        self._toggle_fullscreen()

    # -------------------------------------------------------------- closing
    def _close(self) -> None:
        pos = self.backend.position_s() if self.backend else 0
        dur = self._duration or (self.backend.duration_s() if self.backend else 0)
        self.shutdown(keep_position=(pos, dur))
        if self.on_closed:
            self.on_closed()

    def shutdown(self, keep_position: tuple[int, int] | None = None) -> None:
        """Stop hardware & persist a resume point; idempotent."""
        if self.backend is not None:
            try:
                self.backend.stop()
            except Exception:
                pass
        pos, dur = keep_position or (0, 0)
        self.service.session_stopped(pos, dur)

    def _toast(self, msg: str) -> None:
        window = self.window()
        if window and hasattr(window, "statusBar"):
            window.statusBar().showMessage(msg, 3000)
