"""Settings screen: theme, library folders, playback, external player, providers.

Provider API keys are shown as password fields; existing values are never
displayed in plaintext. They are stored locally only.
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ui.components.detail_body import _section_title
from ui.components.dialogs import confirm
from ui.screens.base import Screen


def _help(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("MutedLabel")
    label.setWordWrap(True)
    return label


class ProviderKeysDialog(QDialog):
    """Edit provider API keys. Existing keys are never displayed in plaintext."""

    def __init__(self, context, parent=None) -> None:
        super().__init__(parent)
        self.context = context
        self.setWindowTitle("Metadata providers")
        self.setMinimumWidth(520)
        layout = QVBoxLayout(self)
        layout.addWidget(_help(
            "API keys are stored in your local secrets file (never committed, "
            "never shown back in plain text) and used only to talk to the "
            "matching provider. Leave a field blank to keep an existing key "
            "(shown as ••••). Providers without a key simply stay inactive."
        ))
        form = QFormLayout()
        self._key_fields: list[tuple[str, str, QLineEdit]] = []  # (secrets key, label, entry)
        for provider_id in sorted(context.services.providers):
            provider = context.services.providers[provider_id]
            if not provider.requires_key:
                continue
            key_name = provider.key_provider_name or provider_id
            entry = QLineEdit()
            entry.setEchoMode(QLineEdit.EchoMode.Password)
            if provider.api_key or context.services.secrets.get(key_name):
                entry.setPlaceholderText("••••••••  (saved)")
            form.addRow(f"{provider.display_name} API key", entry)
            self._key_fields.append((key_name, provider.display_name, entry))
        if not self._key_fields:
            layout.addWidget(_help("No configured provider requires an API key."))
        else:
            layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self) -> None:
        secrets = self.context.services.secrets
        for key_name, _label, entry in self._key_fields:
            text = entry.text().strip()
            if not text:
                continue  # blank keeps the existing key
            secrets.set(key_name, text)
            # live providers were constructed with the old key; refresh them
            for provider in self.context.services.providers.values():
                if (provider.key_provider_name or provider.id) == key_name:
                    provider.api_key = text
        super().accept()


class SettingsScreen(Screen):
    title = "Settings"

    def __init__(self, context, parent=None) -> None:
        super().__init__(context, parent)
        self.header = QLabel("Settings")
        self.header.setObjectName("ScreenTitle")
        self.root.addWidget(self.header)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.root.addWidget(self.scroll, 1)
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setSpacing(14)
        self.scroll.setWidget(self.content)
        self._build()

    # -- construction --------------------------------------------------------
    def _build(self) -> None:
        layout = self.content_layout
        settings = self.context.services.settings

        # Appearance
        layout.addWidget(_section_title("Appearance"))
        appearance = QGridLayout()
        appearance.addWidget(QLabel("Theme"), 0, 0)
        self.theme_box = QComboBox()
        self.theme_box.addItem("System", "system")
        self.theme_box.addItem("Dark", "dark")
        self.theme_box.addItem("Light", "light")
        current_theme = str(settings.get("theme", "dark"))
        self.theme_box.setCurrentIndex(max(0, self.theme_box.findData(current_theme)))
        self.theme_box.currentIndexChanged.connect(self._save_theme)
        appearance.addWidget(self.theme_box, 0, 1)
        appearance.addWidget(QLabel("Startup screen"), 1, 0)
        self.startup_box = QComboBox()
        for route, title in self.context.router.routes_with_titles():
            self.startup_box.addItem(title, route)
        self.startup_box.setCurrentIndex(
            max(0, self.startup_box.findData(settings.get("startup_screen", "home")))
        )
        self.startup_box.currentIndexChanged.connect(self._save_startup)
        appearance.addWidget(self.startup_box, 1, 1)
        appearance.addWidget(QLabel("Poster card width"), 2, 0)
        self.width_spin = QSpinBox()
        self.width_spin.setRange(120, 400)
        self.width_spin.setValue(int(settings.get("poster_card_width", 180)))
        self.width_spin.valueChanged.connect(
            lambda v: self._set("poster_card_width", v)
        )
        appearance.addWidget(self.width_spin, 2, 1)
        appearance.addWidget(QLabel("Toast duration (ms)"), 3, 0)
        self.toast_spin = QSpinBox()
        self.toast_spin.setRange(1000, 15000)
        self.toast_spin.setSingleStep(500)
        self.toast_spin.setValue(int(settings.get("toast_duration_ms", 4000)))
        self.toast_spin.valueChanged.connect(
            lambda v: self._set("toast_duration_ms", v)
        )
        appearance.addWidget(self.toast_spin, 3, 1)
        holder = QWidget()
        holder.setLayout(appearance)
        layout.addWidget(holder)

        # Library
        layout.addWidget(_section_title("Library folders"))
        library_note = _help(
            "Media in these folders is scanned into your library. Changes here "
            "do not move or delete files."
        )
        layout.addWidget(library_note)
        self.library_layout = QVBoxLayout()
        layout.addLayout(self.library_layout)
        add_row = QHBoxLayout()
        self.add_folder_entry = QLineEdit()
        self.add_folder_entry.setPlaceholderText("/path/to/media")
        add_row.addWidget(self.add_folder_entry, 1)
        add_button = QPushButton("Add folder")
        add_button.setObjectName("PrimaryButton")
        add_button.clicked.connect(self._add_folder)
        add_row.addWidget(add_button)
        layout.addLayout(add_row)

        # Behavior
        layout.addWidget(_section_title("Behavior"))
        self.notify_check = QCheckBox("Notify when a background scan finishes")
        self.notify_check.setChecked(bool(settings.get("notify_scan", True)))
        self.notify_check.toggled.connect(lambda on: self._set("notify_scan", on))
        layout.addWidget(self.notify_check)

        # Playback
        layout.addWidget(_section_title("Playback"))
        playback = QGridLayout()
        backend_label = QLabel("Video backend")
        playback.addWidget(backend_label, 0, 0)
        self.backend_box = QComboBox()
        self.backend_box.addItem("Automatic", "auto")
        availability = self.context.services.playback.backend_availability()
        for backend_id, info in availability.items():
            name = info.get("name", backend_id)
            if not info.get("available"):
                name += f"  (unavailable)"
            self.backend_box.addItem(name, backend_id)
        current_backend = settings.get("playback_backend", "auto")
        self.backend_box.setCurrentIndex(max(0, self.backend_box.findData(current_backend)))
        self.backend_box.currentIndexChanged.connect(self._save_backend)
        playback.addWidget(self.backend_box, 0, 1)
        playback.addWidget(QLabel("External player"), 1, 0)
        self.external_entry = QLineEdit()
        self.external_entry.setPlaceholderText("e.g. mpv (blank = embedded player)")
        self.external_entry.setText(settings.get("external_player_path", ""))
        self.external_entry.editingFinished.connect(
            lambda: self._set("external_player_path", self.external_entry.text().strip())
        )
        playback.addWidget(self.external_entry, 1, 1)
        holder = QWidget()
        holder.setLayout(playback)
        layout.addWidget(holder)

        # Providers
        layout.addWidget(_section_title("Metadata providers"))
        layout.addWidget(_help(
            "JMDB talks to providers you configure. API keys stay in your local "
            "database and are never displayed back in plain text."
        ))
        self.provider_button = QPushButton("Manage provider keys…")
        self.provider_button.clicked.connect(self._open_providers)
        layout.addWidget(self.provider_button)

        # Maintenance
        layout.addWidget(_section_title("Maintenance"))
        maintenance = QHBoxLayout()
        scan_button = QPushButton("Scan library now")
        scan_button.clicked.connect(self._scan_now)
        maintenance.addWidget(scan_button)
        rebuild_button = QPushButton("Rebuild search index")
        rebuild_button.clicked.connect(self._rebuild_index)
        maintenance.addWidget(rebuild_button)
        diagnostics_button = QPushButton("View diagnostics")
        diagnostics_button.clicked.connect(
            lambda: self.context.router.navigate("services")
        )
        maintenance.addWidget(diagnostics_button)
        layout.addLayout(maintenance)
        layout.addStretch(1)

    def _populate_library(self) -> None:
        while self.library_layout.count():
            item = self.library_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                while item.layout().count():
                    sub = item.layout().takeAt(0)
                    if sub.widget():
                        sub.widget().deleteLater()
        for location in self.context.services.library.locations():
            row = QHBoxLayout()
            path_text = location.path
            if getattr(location, "label", ""):
                path_text = f"{location.label}: {location.path}"
            if getattr(location, "last_scan_status", ""):
                path_text += f"  ({location.last_scan_status})"
            path_label = QLabel(path_text)
            row.addWidget(path_label, 1)
            scan_button = QPushButton("Scan")
            scan_button.clicked.connect(
                lambda _=False, loc_id=location.id: self._scan_folder(loc_id)
            )
            row.addWidget(scan_button)
            remove_button = QPushButton("Remove")
            remove_button.setObjectName("DangerButton")
            remove_button.clicked.connect(
                lambda _=False, loc_id=location.id: self._remove_folder(loc_id)
            )
            row.addWidget(remove_button)
            holder = QWidget()
            holder.setLayout(row)
            self.library_layout.addWidget(holder)

    # -- handlers ------------------------------------------------------------
    def refresh(self) -> None:
        self._populate_library()

    def _set(self, key: str, value) -> None:
        self.context.services.settings.set(key, value)

    def _save_theme(self, index: int) -> None:
        theme = self.theme_box.itemData(index)
        if theme:
            self.context.themes.set_theme(theme)

    def _save_startup(self, index: int) -> None:
        route = self.startup_box.itemData(index)
        if route:
            self._set("startup_screen", route)

    def _save_backend(self, index: int) -> None:
        backend_id = self.backend_box.itemData(index)
        if backend_id:
            self._set("playback_backend", backend_id)

    def _add_folder(self) -> None:
        path = self.add_folder_entry.text().strip()
        if not path:
            return
        ok, message = self.context.services.library.add_location(path)
        self.context.toast(message, "success" if ok else "warning")
        if ok:
            self.add_folder_entry.clear()
            self._populate_library()

    def _remove_folder(self, location_id: int) -> None:
        if confirm(self, "Remove folder", "Remove this folder from the library? Files stay on disk."):
            self.context.services.library.remove_location(location_id)
            self._populate_library()

    def _scan_folder(self, location_id: int) -> None:
        self._run_async_scan(
            lambda: self.context.services.library.scan_location(location_id),
            "Scan started",
        )

    def _scan_now(self) -> None:
        self._run_async_scan(
            lambda: self.context.services.library.scan_all(),
            "Full library scan started",
        )

    def _run_async_scan(self, work, start_message: str) -> None:
        from ui.app.context import run_async

        self.context.toast(start_message, "success")

        def done(_counts):
            self.context.toast("Scan finished", "success")
            self.refresh()

        run_async(work, done, lambda _err: self.context.toast("Scan failed", "error"))

    def _rebuild_index(self) -> None:
        from ui.app.context import run_async

        self.context.toast("Rebuilding search index…", "success")

        def done(count):
            self.context.toast(f"Search index rebuilt ({count} items)", "success")

        run_async(
            lambda: self.context.services.search_index.rebuild(),
            done,
            lambda _err: self.context.toast("Index rebuild failed", "error"),
        )

    def _open_providers(self) -> None:
        dialog = ProviderKeysDialog(self.context, self)
        dialog.exec()
        self.context.toast("Provider settings saved", "success")
