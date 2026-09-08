"""Settings screen: appearance, playback backends, providers, folders, data."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.config.settings import Settings
from app.domain.events import LIBRARY_CHANGED
from app.library.indexer import LibraryIndexer
from app.library.scanner import ScanWorker
from ui.components.common import SectionHeader
from ui.themes.loader import ACCENTS, apply_theme


def _probe_backends() -> list:
    from app.playback.backends.builtin import ExternalBackend, MPVBackend, VLCBackend
    from app.playback.backends.qt_backend import QtMultimediaBackend

    return [QtMultimediaBackend.descriptor(), MPVBackend.descriptor(),
            VLCBackend.descriptor(), ExternalBackend.descriptor()]


def _panel() -> tuple[QWidget, QVBoxLayout]:
    w = QWidget()
    w.setObjectName("Panel")
    v = QVBoxLayout(w)
    v.setContentsMargins(16, 14, 16, 14)
    v.setSpacing(10)
    return w, v


class SettingsScreen(QWidget):
    def __init__(self, container, parent=None):
        super().__init__(parent)
        self.c = container
        s = container.settings
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)
        host = QWidget()
        scroll.setWidget(host)
        root = QVBoxLayout(host)
        root.setContentsMargins(16, 8, 16, 16)
        root.setSpacing(12)
        root.addWidget(SectionHeader("Settings", "persisted instantly to data/settings.json"))

        # ── appearance ─────────────────────────────────────────
        panel, lay = _panel()
        lay.addWidget(QLabel("Appearance"))
        row = QHBoxLayout()
        row.addWidget(QLabel("Theme:"))
        self.theme_box = QComboBox()
        self.theme_box.addItems(["dark", "light"])
        self.theme_box.setCurrentText(s.get(Settings.THEME))
        self.theme_box.currentTextChanged.connect(self._apply_theme_change)
        row.addWidget(self.theme_box)
        row.addWidget(QLabel("Accent:"))
        self._accent_buttons = {}
        for key in ACCENTS:
            b = QPushButton("✓" if key == s.get(Settings.ACCENT) else "")
            b.setFixedSize(30, 30)
            b.setStyleSheet(f"background:{ACCENTS[key]['acc']};border-radius:15px")
            b.clicked.connect(lambda _=None, k=key: self._set_accent(k))
            self._accent_buttons[key] = b
            row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)
        root.addWidget(panel)

        # ── playback ───────────────────────────────────────────
        panel, lay = _panel()
        lay.addWidget(QLabel("Playback"))
        row = QHBoxLayout()
        row.addWidget(QLabel("Backend:"))
        self.backend_box = QComboBox()
        self.backend_box.addItem("auto", "auto")
        self._desc = {d.id: d for d in _probe_backends()}
        for d in self._desc.values():
            self.backend_box.addItem(f"{d.name}{'' if d.available else ' (unavailable)'}", d.id)
        current = s.get(Settings.BACKEND, "auto")
        idx = self.backend_box.findData(current)
        self.backend_box.setCurrentIndex(max(0, idx))
        self.backend_box.currentIndexChanged.connect(
            lambda _i: s.set(Settings.BACKEND, self.backend_box.currentData()))
        row.addWidget(self.backend_box)
        row.addStretch(1)
        lay.addLayout(row)
        self.backend_note = QLabel(" · ".join(
            f"{d.name}: {'ok' if d.available else (d.reason or 'unavailable')}"
            for d in self._desc.values()))
        self.backend_note.setObjectName("Muted")
        self.backend_note.setWordWrap(True)
        lay.addWidget(self.backend_note)
        self.chk_autonext = QCheckBox("Autoplay next episode")
        self.chk_autonext.setChecked(bool(s.get(Settings.AUTOPLAY_NEXT)))
        self.chk_autonext.toggled.connect(lambda v: s.set(Settings.AUTOPLAY_NEXT, v))
        self.chk_cc = QCheckBox("Subtitle support (use sidecars next to media)")
        self.chk_cc.setChecked(bool(s.get(Settings.SUBTITLES)))
        self.chk_cc.toggled.connect(lambda v: s.set(Settings.SUBTITLES, v))
        lay.addWidget(self.chk_autonext)
        lay.addWidget(self.chk_cc)
        # Default volume
        vol_row = QHBoxLayout()
        vol_row.addWidget(QLabel("Default volume:"))
        self.vol_spin = QSpinBox()
        self.vol_spin.setRange(0, 100)
        self.vol_spin.setValue(int(s.get(Settings.VOLUME, 70)))
        self.vol_spin.setSuffix("%")
        self.vol_spin.valueChanged.connect(
            lambda v: s.set(Settings.VOLUME, v))
        vol_row.addWidget(self.vol_spin)
        vol_row.addStretch(1)
        lay.addLayout(vol_row)
        root.addWidget(panel)

        # ── metadata keys ──────────────────────────────────────
        panel, lay = _panel()
        lay.addWidget(QLabel("Metadata providers (optional keys)"))
        self.tmdb_edit = QLineEdit(s.get(Settings.TMDB_API_KEY))
        self.tmdb_edit.setPlaceholderText("TMDB_API_KEY")
        self.tmdb_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.omdb_edit = QLineEdit(s.get(Settings.OMDB_API_KEY))
        self.omdb_edit.setPlaceholderText("OMDB_API_KEY")
        self.tmdb_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.omdb_edit.setEchoMode(QLineEdit.EchoMode.Password)
        for edit, key in ((self.tmdb_edit, Settings.TMDB_API_KEY),
                          (self.omdb_edit, Settings.OMDB_API_KEY)):
            edit.textChanged.connect(lambda t, k=key: s.set(k, t.strip()))
            lay.addWidget(edit)
        hint = QLabel("TVMaze works keyless for series; TMDB covers movies + people.")
        hint.setObjectName("Muted")
        lay.addWidget(hint)
        root.addWidget(panel)

        # ── library folders + scan ─────────────────────────────
        panel, lay = _panel()
        lay.addWidget(QLabel("Library folders"))
        self.folder_list = QListWidget()
        self.folder_list.setMaximumHeight(120)
        for folder in s.get(Settings.LIBRARY_FOLDERS, []):
            QListWidgetItem(folder, self.folder_list)
        lay.addWidget(self.folder_list)
        row = QHBoxLayout()
        btn_add = QPushButton("+ Add folder")
        btn_add.clicked.connect(self._add_folder)
        btn_del = QPushButton("Remove selected")
        btn_del.clicked.connect(self._remove_folder)
        self.btn_scan = QPushButton("▶ Scan now")
        self.btn_scan.setProperty("accent", True)
        self.btn_scan.clicked.connect(self._scan)
        row.addWidget(btn_add)
        row.addWidget(btn_del)
        row.addStretch(1)
        row.addWidget(self.btn_scan)
        lay.addLayout(row)
        self.chk_enrich = QCheckBox("Enrich with metadata during scan (slower, needs network)")
        self.chk_enrich.setChecked(True)
        lay.addWidget(self.chk_enrich)
        root.addWidget(panel)

        # ── data ───────────────────────────────────────────────
        panel, lay = _panel()
        lay.addWidget(QLabel("Data"))
        row = QHBoxLayout()
        btn_export = QPushButton("Export JSON")
        btn_import = QPushButton("Import JSON")
        btn_diag = QPushButton("Diagnostics")
        btn_reset = QPushButton("Reset everything")
        btn_reset.setStyleSheet("color:#ff5c6c")
        btn_export.clicked.connect(self._export)
        btn_import.clicked.connect(self._import)
        btn_diag.clicked.connect(self._diag)
        btn_reset.clicked.connect(self._reset)
        for b in (btn_export, btn_import, btn_diag, btn_reset):
            row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)

        # Cache management
        cache_row = QHBoxLayout()
        btn_clear_cache = QPushButton("Clear metadata cache")
        btn_clear_cache.clicked.connect(self._clear_cache)
        self.cache_lbl = QLabel("")
        self.cache_lbl.setObjectName("Muted")
        cache_row.addWidget(btn_clear_cache)
        cache_row.addWidget(self.cache_lbl)
        cache_row.addStretch(1)
        lay.addLayout(cache_row)

        # Re-enrich all
        reenrich_row = QHBoxLayout()
        btn_reenrich_all = QPushButton("Re-enrich all movies")
        btn_reenrich_all.clicked.connect(self._reenrich_all)
        self.reenrich_lbl = QLabel("")
        self.reenrich_lbl.setObjectName("Muted")
        reenrich_row.addWidget(btn_reenrich_all)
        reenrich_row.addWidget(self.reenrich_lbl)
        reenrich_row.addStretch(1)
        lay.addLayout(reenrich_row)

        info = QLabel(f"Database: {self.c.paths.db_path}")
        info.setObjectName("Muted")
        lay.addWidget(info)
        root.addWidget(panel)
        root.addStretch(1)

        self._scan_worker: ScanWorker | None = None
        self._update_cache_label()

    # ---------------------------------------------------------- handlers
    def _apply_theme_change(self, theme: str) -> None:
        self.c.settings.set(Settings.THEME, theme)
        from PyQt6.QtWidgets import QApplication

        apply_theme(QApplication.instance(), self.c.settings)

    def _set_accent(self, key: str) -> None:
        self.c.settings.set(Settings.ACCENT, key)
        for k, b in self._accent_buttons.items():
            b.setText("✓" if k == key else "")
        self._apply_theme_change(self.c.settings.get(Settings.THEME))

    def _folders(self) -> list[str]:
        return [self.folder_list.item(i).text() for i in range(self.folder_list.count())]

    def _sync_folders(self) -> None:
        self.c.settings.set(Settings.LIBRARY_FOLDERS, self._folders())

    def _add_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Add library folder")
        if folder:
            QListWidgetItem(folder, self.folder_list)
            self._sync_folders()

    def _remove_folder(self) -> None:
        for item in self.folder_list.selectedItems():
            self.folder_list.takeItem(self.folder_list.row(item))
        self._sync_folders()

    def _scan(self) -> None:
        folders = self._folders()
        if not folders:
            self._toast("Add at least one library folder first.")
            return
        self.progress = QProgressDialog("Scanning library…", "Cancel", 0, 0, self)
        self.progress.setWindowModality(Qt.WindowModality.WindowModal)
        indexer = LibraryIndexer(self.c.media_repo, self.c.episode_repo)
        enrich = self.chk_enrich.isChecked() and self.c.metadata.configured()
        self._scan_worker = ScanWorker(folders, indexer,
                                       metadata_manager=self.c.metadata if enrich else None,
                                       parent=self)
        self._scan_worker.progressed.connect(
            lambda i, total, path: (self.progress.setMaximum(total),
                                    self.progress.setValue(i),
                                    self.progress.setLabelText(Path(path).name)))
        self._scan_worker.finished_summary.connect(self._scan_done)
        self._scan_worker.failed.connect(lambda msg: self._toast(f"Scan failed: {msg}"))
        self.progress.canceled.connect(self._scan_worker.cancel)
        self.progress.show()
        self._scan_worker.start()

    def _scan_done(self, summary: dict) -> None:
        self.progress.close()
        self.c.bus.emit(LIBRARY_CHANGED, summary=summary)
        QMessageBox.information(
            self, "Scan complete",
            f"Movies: {summary.get('movies', 0)}\nEpisodes: {summary.get('episodes', 0)}\n"
            f"Music: {summary.get('music', 0)}\nEnriched: {summary.get('enriched', 0)}\n"
            f"Errors: {summary.get('errors', 0)}")

    def _export(self) -> None:
        target, _ = QFileDialog.getSaveFileName(self, "Export JMDB data", "jmdb-backup.json",
                                                "JSON (*.json)")
        if not target:
            return
        state = {
            "schema_version": self.c.schema_version,
            "favorites": sorted(self.c.state_repo.favorites()),
            "watchlist": sorted(self.c.state_repo.watchlist()),
            "ratings": self.c.state_repo.ratings_map(),
            "settings": self.c.settings._data,
            "history": self.c.history_repo.recent(10_000),
        }
        Path(target).write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
        self._toast(f"Exported to {target}")

    def _import(self) -> None:
        source, _ = QFileDialog.getOpenFileName(self, "Import JMDB backup", "", "JSON (*.json)")
        if not source:
            return
        try:
            data = json.loads(Path(source).read_text(encoding="utf-8"))
            for mid in data.get("favorites", []):
                if mid not in self.c.state_repo.favorites():
                    self.c.state_repo.toggle_favorite(mid)
            for mid, value in (data.get("ratings") or {}).items():
                self.c.state_repo.set_rating(int(mid), value)
            self._toast("Import applied (favorites/ratings merged).")
        except (OSError, json.JSONDecodeError, KeyError) as exc:
            self._toast(f"Import failed: {exc}")

    def _diag(self) -> None:
        script = Path(__file__).resolve().parents[2] / "scripts" / "diagnostics.py"
        try:
            out = subprocess.run([sys.executable, str(script)], capture_output=True,
                                 text=True, timeout=30)
            text = (out.stdout or "") + (("\n" + out.stderr) if out.stderr else "")
        except Exception as exc:
            text = f"diagnostics failed: {exc}"
        box = QMessageBox(self)
        box.setWindowTitle("JMDB Diagnostics")
        box.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        box.setText(text or "(no output)")
        box.exec()

    def _clear_cache(self) -> None:
        n = self.c.metadata.clear_cache()
        self._update_cache_label()
        self._toast(f"Cleared {n} metadata cache entries.")

    def _update_cache_label(self) -> None:
        stats = self.c.metadata.cache_stats()
        self.cache_lbl.setText(f"cache: {stats.get('total', 0)} entries "
                               f"(movies={stats.get('movies', 0)}, series={stats.get('series', 0)})")

    def _reenrich_all(self) -> None:
        from app.library.media_detector import detect
        movies = self.c.media_repo.list("movie")
        if not movies:
            self._toast("No movies in library.")
            return
        enriched = 0
        for m in movies:
            detected = detect(m.get("file_path", ""))
            if self.c.metadata.re_enrich(m["id"], detected, media_repo=self.c.media_repo,
                                         clear_cache=True):
                enriched += 1
        self.reenrich_lbl.setText(f"Re-enriched {enriched}/{len(movies)} movies.")
        self._toast(f"Re-enriched {enriched} of {len(movies)} movies.")
        self.c.bus.emit(LIBRARY_CHANGED, summary={"re_enriched": enriched})

    def _reset(self) -> None:
        answer = QMessageBox.question(
            self, "Reset JMDB?",
            "Delete the local database (library, history, progress, ratings)?\n"
            "Settings and .env keys are kept.")
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.c.db.close()
        self.c.paths.db_path.unlink(missing_ok=True)
        self._toast("Database removed. Restart JMDB to re-create a fresh schema.")

    def _toast(self, msg: str) -> None:
        window = self.window()
        if window and hasattr(window, "statusBar"):
            window.statusBar().showMessage(msg, 5000)
