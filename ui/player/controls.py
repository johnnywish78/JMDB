"""Player control bar."""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSlider,
    QWidget,
)

from ui.app.context import icon


def format_time(seconds: float) -> str:
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


class PlayerControls(QWidget):
    play_toggled = pyqtSignal()
    stop_requested = pyqtSignal()
    seek_requested = pyqtSignal(int)
    volume_changed = pyqtSignal(int)
    mute_toggled = pyqtSignal(bool)
    fullscreen_toggled = pyqtSignal()
    speed_selected = pyqtSignal(float)
    subtitles_requested = pyqtSignal()
    audio_requested = pyqtSignal()
    playlist_toggled = pyqtSignal()
    next_requested = pyqtSignal()
    previous_requested = pyqtSignal()
    subtitle_delay_changed = pyqtSignal(float)
    audio_delay_changed = pyqtSignal(float)
    aspect_selected = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("PlayerControls")
        self.setFixedHeight(92)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(10)

        self.title_label = QLabel("")
        self.title_label.setObjectName("PlayerTitle")
        layout.addWidget(self.title_label, 1)

        # position slider + times
        self.position_slider = QSlider(Qt.Orientation.Horizontal)
        self.position_slider.setObjectName("PositionSlider")
        self.position_slider.setRange(0, 1000)
        self.position_slider.sliderMoved.connect(
            lambda value: self.seek_requested.emit(value)
        )
        self.time_label = QLabel("0:00 / 0:00")
        self.time_label.setObjectName("MutedLabel")
        layout.addWidget(self.time_label)
        layout.addWidget(self.position_slider, 2)

        self.previous_button = self._icon_button("skip_prev", "Previous (P)", self.previous_requested.emit)
        self.play_button = self._icon_button("pause", "Play/Pause (Space)", self.play_toggled.emit)
        self.next_button = self._icon_button("skip_next", "Next (N)", self.next_requested.emit)
        self.stop_button = self._icon_button("stop", "Stop", self.stop_requested.emit)
        for button in (self.previous_button, self.play_button, self.next_button, self.stop_button):
            layout.addWidget(button)

        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setObjectName("VolumeSlider")
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(100)
        self.volume_slider.setFixedWidth(110)
        self.volume_slider.valueChanged.connect(self.volume_changed.emit)
        self.mute_button = self._icon_button("volume", "Mute (M)", lambda: self.mute_toggled.emit(True))
        layout.addWidget(self.mute_button)
        layout.addWidget(self.volume_slider)

        self.speed_button = self._icon_button("speed", "Playback speed", self._show_speed_menu)
        self.subtitle_button = self._icon_button("subtitles", "Subtitles", self.subtitles_requested.emit)
        self.audio_button = self._icon_button("audio", "Audio track", self.audio_requested.emit)
        self.playlist_button = self._icon_button("list", "Playlist", self.playlist_toggled.emit)
        self.aspect_button = self._icon_button("fullscreen", "Aspect ratio", self._show_aspect_menu)
        self.fullscreen_button = self._icon_button("fullscreen", "Fullscreen (F)", self.fullscreen_toggled.emit)
        for button in (self.speed_button, self.subtitle_button, self.audio_button, self.playlist_button, self.aspect_button, self.fullscreen_button):
            layout.addWidget(button)

        self._muted = False

    def _icon_button(self, icon_name: str, tooltip: str, handler) -> QPushButton:
        button = QPushButton()
        button.setObjectName("FlatIconButton")
        button.setIcon(icon(icon_name))
        button.setToolTip(tooltip)
        button.clicked.connect(handler)
        return button

    # -- state updates ------------------------------------------------------------
    def set_playing(self, playing: bool) -> None:
        self.play_button.setIcon(icon("pause" if playing else "play"))

    def set_times(self, position: float, duration: float) -> None:
        self.time_label.setText(f"{format_time(position)} / {format_time(duration)}")
        if duration > 0 and not self.position_slider.isSliderDown():
            self.position_slider.setValue(int(position / duration * 1000))

    def set_title(self, title: str) -> None:
        self.title_label.setText(title)

    def toggle_mute_state(self) -> None:
        self._muted = not self._muted
        self.mute_button.setIcon(icon("mute" if self._muted else "volume"))

    def set_capabilities(self, capabilities) -> None:
        """Enable/disable buttons from backend capabilities."""
        self.position_slider.setEnabled(bool(capabilities.seek))
        self.volume_slider.setEnabled(bool(capabilities.volume))
        self.mute_button.setEnabled(bool(capabilities.mute))
        self.speed_button.setEnabled(bool(capabilities.speed))
        self.subtitle_button.setEnabled(bool(capabilities.subtitle_tracks))
        self.audio_button.setEnabled(bool(capabilities.audio_tracks))
        self.aspect_button.setEnabled(bool(capabilities.aspect_ratio))

    # -- menus ------------------------------------------------------------------------
    def _show_speed_menu(self) -> None:
        menu = QMenu(self)
        for rate in (0.5, 0.75, 1.0, 1.25, 1.5, 2.0):
            action = menu.addAction(f"{rate:g}×")
            action.triggered.connect(lambda _=False, r=rate: self.speed_selected.emit(r))
        menu.exec(self.mapToGlobal(self.speed_button.pos()))

    def _show_aspect_menu(self) -> None:
        menu = QMenu(self)
        for ratio in ("auto", "4:3", "16:9", "1.85:1", "2.39:1"):
            action = menu.addAction(ratio)
            action.triggered.connect(lambda _=False, r=ratio: self.aspect_selected.emit(r))
        menu.exec(self.mapToGlobal(self.aspect_button.pos()))

    def show_delay_controls(self) -> None:
        menu = QMenu(self)
        sub_menu = menu.addMenu("Subtitle delay")
        for delta in (-0.5, -0.1, 0.1, 0.5):
            sub_menu.addAction(f"{delta:+.1f}s").triggered.connect(
                lambda _=False, d=delta: self.subtitle_delay_changed.emit(d)
            )
        audio_menu = menu.addMenu("Audio delay")
        for delta in (-0.5, -0.1, 0.1, 0.5):
            audio_menu.addAction(f"{delta:+.1f}s").triggered.connect(
                lambda _=False, d=delta: self.audio_delay_changed.emit(d)
            )
        menu.exec(self.mapToGlobal(self.subtitle_button.pos()))
