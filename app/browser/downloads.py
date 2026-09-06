"""Downloads handling for the embedded browser."""
from __future__ import annotations

import logging
import os
import re
from pathlib import Path

from app.config.paths import Paths
from app.database.repositories import Repositories
from app.domain.events import DownloadUpdated, EventBus

logger = logging.getLogger(__name__)


def _safe_filename(name: str) -> str:
    name = os.path.basename(name or "")
    name = re.sub(r"[^\w\s.\-()]", "_", name)
    return name[:180] or "download"


class DownloadsManager:
    """Records browser downloads into ~/.jmdb/downloads and the database."""

    def __init__(self, paths: Paths, repos: Repositories, events: EventBus) -> None:
        self.paths = paths
        self.repos = repos
        self.events = events
        self._active: dict[int, object] = {}

    def handle_download(self, download) -> None:  # QWebEngineDownloadItem
        try:
            self._handle(download)
        except Exception:
            logger.exception("download handling failed")

    def _handle(self, download) -> None:
        url = download.url().toString()
        suggested = download.downloadFileName() if hasattr(download, "downloadFileName") else ""
        filename = _safe_filename(suggested or url.split("/")[-1] or "download")
        # avoid overwriting existing files
        target = self.paths.downloads / filename
        counter = 1
        while target.exists():
            stem = Path(filename).stem
            suffix = Path(filename).suffix
            target = self.paths.downloads / f"{stem} ({counter}){suffix}"
            counter += 1
        try:
            download.setDownloadDirectory(str(self.paths.downloads))
            download.setDownloadFileName(target.name)
        except AttributeError:
            download.setPath(str(target))
        download_id = self.repos.browser.add_download(
            url, str(target), download.mimeType(), download.totalBytes() or 0
        )
        self._active[download_id] = download

        def on_progress(received: int, total: int) -> None:
            self.repos.browser.update_download(
                download_id, bytes_received=received, bytes_total=total
            )
            self.events.publish(
                DownloadUpdated(download_id=download_id, state="running", received=received, total=total)
            )

        def on_state() -> None:
            state = download.state()
            from PyQt6.QtWebEngineCore import QWebEngineDownloadItem

            if state == QWebEngineDownloadItem.DownloadState.DownloadRequested:
                return
            mapping = {
                QWebEngineDownloadItem.DownloadState.DownloadCompleted: "completed",
                QWebEngineDownloadItem.DownloadState.DownloadCancelled: "cancelled",
                QWebEngineDownloadItem.DownloadState.DownloadInterrupted: "failed",
            }
            db_state = mapping.get(state, "failed")
            self.repos.browser.update_download(
                download_id,
                state=db_state,
                bytes_received=download.receivedBytes(),
                bytes_total=download.totalBytes(),
            )
            self.events.publish(
                DownloadUpdated(
                    download_id=download_id,
                    state=db_state,
                    received=download.receivedBytes(),
                    total=download.totalBytes(),
                )
            )
            self._active.pop(download_id, None)

        download.downloadProgress.connect(on_progress)
        download.stateChanged.connect(on_state)
        download.accept()

    def recent(self, limit: int = 50) -> list[dict]:
        return [
            {
                "id": d.id,
                "url": d.url,
                "path": d.path,
                "state": d.state,
                "bytes_total": d.bytes_total,
                "bytes_received": d.bytes_received,
            }
            for d in self.repos.browser.downloads(limit)
        ]
