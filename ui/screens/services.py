"""Services center: registry-driven tiles with real availability."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QGridLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ui.components.detail_body import _section_title
from ui.screens.base import Screen


class ServiceTile(QWidget):
    def __init__(self, status, screen: "ServicesScreen", parent=None) -> None:
        super().__init__(parent)
        self.status = status
        self.setObjectName("CardPanel")
        self.setFixedWidth(300)
        self.setMinimumHeight(170)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(6)

        head = QLabel(f"{status.definition.icon_emoji}  {status.definition.name}")
        head.setObjectName("SectionHeader")
        layout.addWidget(head)
        description = QLabel(status.definition.description)
        description.setObjectName("MutedLabel")
        description.setWordWrap(True)
        layout.addWidget(description)

        if status.definition.requires_drm:
            drm = QLabel("DRM → system browser")
            drm.setObjectName("PosterYear")
            layout.addWidget(drm)
        if status.notes:
            notes = QLabel(status.notes)
            notes.setWordWrap(True)
            notes.setStyleSheet("font-size: 11px;")
            layout.addWidget(notes)

        layout.addStretch(1)
        buttons = QVBoxLayout()
        buttons.setSpacing(4)
        open_embedded = QPushButton("Open in JMDB browser")
        open_embedded.setEnabled(status.embedded_available)
        open_embedded.clicked.connect(lambda: screen.open_embedded(status))
        buttons.addWidget(open_embedded)
        open_external = QPushButton("Open in system browser")
        open_external.setEnabled(status.external_available)
        open_external.clicked.connect(lambda: screen.open_external(status))
        buttons.addWidget(open_external)
        if status.definition.configurable_url:
            configure = QPushButton("Configure URL…")
            configure.clicked.connect(lambda: screen.configure_url(status))
            buttons.addWidget(configure)
        layout.addLayout(buttons)


class ServicesScreen(Screen):
    title = "Services"

    def __init__(self, context, parent=None) -> None:
        super().__init__(context, parent)
        self.header = QLabel("Services")
        self.header.setObjectName("ScreenTitle")
        self.root.addWidget(self.header)
        note = QLabel(
            "DRM-protected services (Netflix, Prime Video, Disney+) open in your "
            "system browser — the embedded engine cannot play DRM content."
        )
        note.setObjectName("MutedLabel")
        note.setWordWrap(True)
        self.root.addWidget(note)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.root.addWidget(self.scroll, 1)
        self.container = QWidget()
        self.grid = QGridLayout(self.container)
        self.grid.setSpacing(14)
        self.scroll.setWidget(self.container)

    def refresh(self) -> None:
        statuses = self.context.services.service_manager.statuses()
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        categories: dict[str, list] = {}
        for status in statuses:
            categories.setdefault(status.definition.category, []).append(status)
        row = 0
        label_map = {
            "media": "Media", "messaging": "Messaging", "music": "Music",
            "streaming": "Streaming (DRM)", "selfhosted": "Self-hosted",
        }
        for category in ("media", "streaming", "music", "messaging", "selfhosted"):
            entries = categories.get(category)
            if not entries:
                continue
            self.grid.addWidget(_section_title(label_map.get(category, category)), row, 0, 1, 3)
            row += 1
            for index, status in enumerate(entries):
                self.grid.addWidget(ServiceTile(status, self), row, index % 3)
                if index % 3 == 2:
                    row += 1
            row += 1
        self.grid.setRowStretch(row, 1)

    def open_embedded(self, status) -> None:
        opened, url = self.context.services.service_manager.open_url(status.definition)
        if opened:
            self.context.router.navigate("browser", url=url)
        else:
            ok, info = self.context.services.service_manager.open_external(status.definition)
            if not ok:
                self.context.toast("No browser available", "error")

    def open_external(self, status) -> None:
        ok, info = self.context.services.service_manager.open_external(status.definition)
        if ok:
            self.context.toast(f"Opened in {info}", "success")
        else:
            self.context.toast(info or "Could not open browser", "error")

    def configure_url(self, status) -> None:
        from ui.components.dialogs import text_input

        current = self.context.services.service_manager.configured_url(status.definition)
        url, ok = text_input(
            self, f"Configure {status.definition.name}", "Server URL:", current
        )
        if ok:
            self.context.services.service_manager.set_configured_url(
                status.definition.id, url.strip()
            )
            self.context.toast("URL saved", "success")
