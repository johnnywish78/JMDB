"""Qt-free library scan engine.

The pipeline (filesystem walk -> detector -> indexer -> optional metadata
enrich) lives here so it can run from the FastAPI backend (threading) and from
tests without any Qt dependency. The Qt ``ScanWorker`` in ``scanner.py`` is a
thin adapter over :func:`run_scan` for the legacy PyQt6 UI.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Callable

from app.library.filesystem import iter_media_files
from app.library.media_detector import detect

log = logging.getLogger("jmdb.scan")

ProgressFn = Callable[[int, int, str], None]     # current, total, current path
IndexedFn = Callable[[dict], None]               # {"id","title","kind","path"}
SummaryFn = Callable[[dict], None]               # counts + errors


def _bucket(kind: str) -> str:
    return {"episode": "episodes", "movie": "movies", "music": "music"}.get(kind, "movies")


def run_scan(
    folders: list[str],
    indexer,
    metadata_manager=None,
    enrich: bool = True,
    on_progress: ProgressFn | None = None,
    on_indexed: IndexedFn | None = None,
    on_finished: SummaryFn | None = None,
    on_failed: Callable[[str], None] | None = None,
    cancel: Callable[[], bool] | None = None,
    polite_delay: float = 0.15,
) -> dict:
    """Scan *folders*, index media, optionally enrich metadata.

    Returns the summary dict. Never raises; failures are reported via
    ``on_failed`` and counted in ``summary["errors"]``.
    """
    enrich = bool(enrich and metadata_manager is not None)
    summary: dict[str, Any] = {
        "movies": 0, "episodes": 0, "music": 0, "errors": 0, "enriched": 0,
        "total_files": 0, "scanned": 0, "cancelled": False,
    }
    try:
        files: list[Path] = []
        for folder in folders:
            files.extend(iter_media_files(Path(folder)))
        total = len(files)
        summary["total_files"] = total
        log.info("scan start: %s folders, %s files", len(folders), total)

        for i, path in enumerate(files, 1):
            if cancel and cancel():
                summary["cancelled"] = True
                break
            summary["scanned"] = i
            if on_progress:
                on_progress(i, total, str(path))
            try:
                detected = detect(path)
                media_id = indexer.index(detected)
                summary[_bucket(detected.kind.value)] += 1
                if on_indexed:
                    on_indexed({"id": media_id, "title": detected.title,
                                "kind": detected.kind.value, "path": str(path)})
                if enrich:
                    if metadata_manager.enrich(media_id, detected,
                                               media_repo=indexer.media_repo):
                        summary["enriched"] += 1
                    time.sleep(polite_delay)  # be polite to providers
            except Exception as exc:  # one bad file must not kill the scan
                summary["errors"] += 1
                log.warning("index failed for %s: %s", path, exc)
        if on_finished:
            on_finished(summary)
        return summary
    except Exception as exc:  # pragma: no cover - defensive
        log.exception("scan crashed")
        if on_failed:
            on_failed(str(exc))
        return summary
