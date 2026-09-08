"""Qt worker that scans folders off the UI thread.

Pipeline: filesystem walk → detector → indexer → (optional) metadata enrich.
Emits plain dicts so screens never touch domain objects across threads.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from app.domain.models import DetectedMedia
from app.library.filesystem import iter_media_files
from app.library.indexer import LibraryIndexer
from app.library.media_detector import detect

log = logging.getLogger("jmdb.scan")


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
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:  # worker thread — never touch widgets here
        summary: dict = {"movies": 0, "episodes": 0, "music": 0, "errors": 0, "enriched": 0}
        try:
            files: list[Path] = []
            for folder in self.folders:
                files.extend(iter_media_files(Path(folder)))
            total = len(files)
            log.info("scan start: %s folders, %s files", len(self.folders), total)

            for i, path in enumerate(files, 1):
                if self._cancel:
                    break
                self.progressed.emit(i, total, str(path))
                try:
                    detected = detect(path)
                    media_id = self.indexer.index(detected)
                    summary[self._bucket(detected)] += 1
                    self.indexed.emit({"id": media_id, "title": detected.title,
                                       "kind": detected.kind.value, "path": str(path)})
                    if self.enrich:
                        if self.metadata.enrich(media_id, detected,
                                                media_repo=self.indexer.media_repo):
                            summary["enriched"] += 1
                        time.sleep(0.15)  # be polite to providers
                except Exception as exc:  # one bad file must not kill the scan
                    summary["errors"] += 1
                    log.warning("index failed for %s: %s", path, exc)
            self.finished_summary.emit(summary)
        except Exception as exc:  # pragma: no cover - defensive
            log.exception("scan crashed")
            self.failed.emit(str(exc))

    @staticmethod
    def _bucket(d: DetectedMedia) -> str:
        return {"episode": "episodes", "movie": "movies", "music": "music"}.get(d.kind.value, "movies")
