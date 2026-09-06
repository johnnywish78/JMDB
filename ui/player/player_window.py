"""The player window: video surface + controls + playlist + shortcuts."""
from __future__ import annotations

import logging

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QVBoxLayout,
    QWidget,
)

from app.playback.controller import PlaybackController
from app.playback.backends.external import ExternalBackend
from ui.player.audio_dialog import AudioDialog
from ui.player.controls import PlayerControls
from ui.player.playlist import PlaylistPanel
from ui.player.subtitle_dialog import SubtitleDialog

logger = logging.getLogger(__name__)


class PlayerWindow(QMainWindow):
    def __init__(self, context, main_window, parent=None) -> None:
        super().__init__(parent)
        self.context = context
        self.main_window = main_window
        self.setWindowTitle("JMDB Player")
        self.setObjectName("PlayerWindow")
        self.resize(1020, 620)
        self._current_item = None
        self._queue: list = []
        self._fullscreen = False
        self._controls_hidden = False
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._auto_hide_controls)

        central = QWidget()
        self.setCentralWidget(central)
        self.layout = QVBoxLayout(central)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # video surface area
        self.video_area = QWidget()
        self.video_layout = QHBoxLayout(self.video_area)
        self.video_layout.setContentsMargins(0, 0, 0, 0)
        self.layout.addWidget(self.video_area, 1)

        self.placeholder = QLabel("No media playing")
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_layout.addWidget(self.placeholder)

        # playlist side panel
        self.playlist_panel = PlaylistPanel()
        self.playlist_panel.item_activated.connect(self._play_queue_index)
        self.playlist_panel.hide()

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.addWidget(self.video_area, 1)
        body.addWidget(self.playlist_panel)
        self.layout.addLayout(body, 1)

        self.controls = PlayerControls()
        self.layout.addWidget(self.controls)

        self._connect_controls()
        self._install_shortcuts()

    # -- setup -----------------------------------------------------------------
    def _controller(self) -> PlaybackController | None:
        return self.context.playback_controller

    def _connect_controls(self) -> None:
        c = self.controls
        c.play_toggled.connect(self._toggle_pause)
        c.stop_requested.connect(self.close)
        c.seek_requested.connect(self._seek_slider)
        c.volume_changed.connect(self._set_volume)
        c.mute_toggled.connect(lambda _on: self._toggle_mute())
        c.fullscreen_toggled.connect(self.toggle_fullscreen)
        c.speed_selected.connect(self._set_speed)
        c.subtitles_requested.connect(self._open_subtitles)
        c.audio_requested.connect(self._open_audio)
        c.playlist_toggled.connect(self.toggle_playlist)
        c.next_requested.connect(self._next)
        c.previous_requested.connect(self._previous)
        c.subtitle_delay_changed.connect(self._adjust_subtitle_delay)
        c.audio_delay_changed.connect(self._adjust_audio_delay)
        c.aspect_selected.connect(self._set_aspect)

        controller = self._controller()
        if controller is not None:
            controller.position_changed.connect(self._on_position)
            controller.duration_changed.connect(self._on_duration)
            controller.state_changed.connect(self._on_state)
            controller.error_occurred.connect(self._on_error)
            controller.session_started.connect(self._on_session_started)
            controller.finished.connect(lambda _item: None)
            controller.queue_advanced.connect(self._on_queue_advanced)

    def _install_shortcuts(self) -> None:
        bindings = [
            ("Space", self._toggle_pause),
            ("K", self._toggle_pause),
            ("Left", lambda: self._seek_relative(-int(self.context.services.settings.get("seek_step_seconds")))),
            ("Right", lambda: self._seek_relative(int(self.context.services.settings.get("seek_step_seconds")))),
            ("J", lambda: self._seek_relative(-30)),
            ("L", lambda: self._seek_relative(30)),
            ("Up", lambda: self._volume_step(int(self.context.services.settings.get("volume_step")))),
            ("Down", lambda: self._volume_step(-int(self.context.services.settings.get("volume_step")))),
            ("F", self.toggle_fullscreen),
            ("M", self._toggle_mute),
            ("Esc", self._on_escape),
            ("N", self._next),
            ("P", self._previous),
            ("S", self._open_subtitles),
            ("A", self._open_audio),
        ]
        for key, handler in bindings:
            QShortcut(QKeySequence(key), self, activated=handler)

    # -- playback entry -------------------------------------------------------------
    def play(self, playable, queue=None) -> None:
        self._queue = list(queue) if queue else [playable]
        self._start(playable)

    def _start(self, playable) -> None:
        controller = self._controller()
        if controller is None:
            self._show_error("Playback system not ready")
            return
        self._current_item = playable
        self.controls.set_title(playable.display_title())
        self._set_video_widget()
        controller.play_item(playable, self.context.profile_id, queue=self._queue)
        if self._queue:
            index = next(
                (i for i, item in enumerate(self._queue) if item.path == playable.path), 0
            )
            self.playlist_panel.set_items(self._queue, index)

    def _set_video_widget(self) -> None:
        controller = self._controller()
        backend = controller.backend if controller else None
        if backend is not None and backend.capabilities.embed:
            widget = backend.video_widget()
            if widget is not None:
                self.placeholder.hide()
                if widget.parentWidget() is not self.video_area:
                    self.video_layout.takeAt(0)
                    self.video_layout.addWidget(widget)
                return
        # no embedded surface (external player or non-embeddable backend)
        self.video_layout.takeAt(0)
        self.video_layout.addWidget(self.placeholder)
        self.placeholder.show()
        if isinstance(backend, ExternalBackend):
            self.placeholder.setText(
                "Opened in external player\n"
                f"({backend.player_kind})\n\n"
                "Position tracking and in-app controls are not available for\n"
                "external players. Use the player's own controls."
            )
        else:
            self.placeholder.setText("No media playing")

    # -- control handlers ---------------------------------------------------------------
    def _toggle_pause(self) -> None:
        controller = self._controller()
        if controller is not None:
            controller.toggle_pause()

    def _seek_slider(self, value: int) -> None:
        controller = self._controller()
        if controller is not None and controller.backend is not None:
            duration = controller.backend.duration
            if duration > 0:
                controller.seek(duration * value / 1000.0)

    def _seek_relative(self, seconds: int) -> None:
        controller = self._controller()
        if controller is not None:
            controller.seek_relative(seconds)

    def _set_volume(self, percent: int) -> None:
        controller = self._controller()
        if controller is not None:
            controller.set_volume(percent)

    def _volume_step(self, step: int) -> None:
        slider = self.controls.volume_slider
        slider.setValue(slider.value() + step)

    def _toggle_mute(self) -> None:
        controller = self._controller()
        self.controls.toggle_mute_state()
        if controller is not None:
            controller.set_muted(self.controls._muted)

    def _set_speed(self, rate: float) -> None:
        controller = self._controller()
        if controller is not None:
            controller.set_speed(rate)
            self.context.toast(f"Speed {rate:g}×")

    def _set_aspect(self, ratio: str) -> None:
        controller = self._controller()
        if controller is not None and controller.backend is not None:
            controller.set_aspect_ratio(ratio)

    def _adjust_subtitle_delay(self, delta: float) -> None:
        controller = self._controller()
        if controller is not None:
            controller.set_subtitle_delay(delta)  # relative handled below
            self.context.toast(f"Subtitle delay {delta:+.1f}s")

    def _adjust_audio_delay(self, delta: float) -> None:
        controller = self._controller()
        if controller is not None:
            controller.set_audio_delay(delta)
            self.context.toast(f"Audio delay {delta:+.1f}s")

    def _next(self) -> None:
        controller = self._controller()
        if controller is not None:
            controller.next()

    def _previous(self) -> None:
        controller = self._controller()
        if controller is not None:
            controller.previous()

    def _play_queue_index(self, index: int) -> None:
        if 0 <= index < len(self._queue):
            self._start(self._queue[index])

    # -- dialogs ---------------------------------------------------------------------------
    def _open_subtitles(self) -> None:
        controller = self._controller()
        if controller is None or controller.backend is None:
            return
        session = self.context.services.playback.session
        media_file_id = session.current.media_file_id if session else None
        options = []
        if media_file_id:
            options = self.context.services.subtitles.options_for(media_file_id)
        dialog = SubtitleDialog(options, self)
        if dialog.exec():
            selected = dialog.selected()
            try:
                controller.backend.set_subtitle_track(
                    selected.track if selected else None
                )
            except Exception as exc:
                self._show_error(str(exc))

    def _open_audio(self) -> None:
        controller = self._controller()
        if controller is None or controller.backend is None:
            return
        tracks = controller.backend.audio_tracks()
        dialog = AudioDialog(tracks, self)
        if dialog.exec():
            selected = dialog.selected()
            try:
                controller.backend.set_audio_track(selected)
            except Exception as exc:
                self._show_error(str(exc))

    # -- view modes ---------------------------------------------------------------------------
    def toggle_fullscreen(self) -> None:
        self._fullscreen = not self._fullscreen
        if self._fullscreen:
            self.showFullScreen()
        else:
            self.showNormal()

    def toggle_playlist(self) -> None:
        self.playlist_panel.setVisible(not self.playlist_panel.isVisible())

    def _on_escape(self) -> None:
        if self._fullscreen:
            self.toggle_fullscreen()
        else:
            self.close()

    def _auto_hide_controls(self) -> None:
        self.controls.hide()

    def mouseMoveEvent(self, event) -> None:
        self.controls.show()
        self._hide_timer.start(2600)
        super().mouseMoveEvent(event)

    # -- controller events ----------------------------------------------------------------------
    def _on_position(self, position: float) -> None:
        controller = self._controller()
        duration = controller.backend.duration if controller and controller.backend else 0
        self.controls.set_times(position, duration)

    def _on_duration(self, duration: float) -> None:
        self.controls.set_times(0, duration)

    def _on_state(self, state: str) -> None:
        self.controls.set_playing(state == "playing")

    def _on_session_started(self, item) -> None:
        controller = self._controller()
        if controller and controller.backend is not None:
            self.controls.set_capabilities(controller.backend.capabilities)
            self.controls.set_playing(True)
        else:
            # external mode: disable all controls
            from app.playback.backends.base import Capabilities

            self.controls.set_capabilities(Capabilities())

    def _on_queue_advanced(self, item) -> None:
        self._current_item = item
        self.controls.set_title(item.display_title())
        index = next((i for i, queued in enumerate(self._queue) if queued.path == item.path), 0)
        self.playlist_panel.set_current(index)

    def _on_error(self, message: str) -> None:
        self._show_error(message)

    def _show_error(self, message: str) -> None:
        self.video_layout.takeAt(0)
        self.video_layout.addWidget(self.placeholder)
        self.placeholder.show()
        self.placeholder.setText(f"Playback problem\n\n{message}")
        logger.error("player: %s", message)

    # -- teardown -----------------------------------------------------------------------------------
    def closeEvent(self, event) -> None:
        controller = self._controller()
        if controller is not None:
            controller.stop()
        self.main_window.state.player_open = False
        super().closeEvent(event)
