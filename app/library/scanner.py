"""Qt worker that scans folders off the UI thread.

Thin adapter over the Qt-free :mod:`app.library.scan_core` so the legacy
PyQt6 UI keeps its signal-based API while the FastAPI backend and tests reuse
the same pipeline without Qt.
"""
from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from app.library.indexer import LibraryIndexer  # noqa: F401  (re-export for callers)
from app.library.scan_core import run_scan


class ScanWorker(QThread):
    progressed = pyqtSignal(int, int, str)   # current, total, current path
    indexed = pyqtSignal(dict)               # {"id":..,"title":..,"kind":..}
    finished_summary = pyqtSignal(dict)      # counts per kind + errors
    failed = pyqtSignal(str)

    def __init__(self, folders: list[str], indexer: LibraryIndexer,
                 metadata_manager=None, enrich: bool = True, parent=None):
        super().__init__(parent)
        self.folders = folders
        self.indexer = indexer
        self.metadata = metadata_manager
        self.enrich = enrich and metadata_manager is not None
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:  # worker thread — never touch widgets here
        run_scan(
            self.folders,
            self.indexer,
            metadata_manager=self.metadata,
            enrich=self.enrich,
            on_progress=lambda c, t, p: self.progressed.emit(c, t, p),
            on_indexed=lambda d: self.indexed.emit(d),
            on_finished=lambda s: self.finished_summary.emit(s),
            on_failed=lambda msg: self.failed.emit(msg),
            cancel=lambda: self._cancelled,
        )
