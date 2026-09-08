"""API runtime context: owns the dependency graph, token, and scan manager."""
from __future__ import annotations

import logging
import threading

from app.bootstrap.dependencies import Dependencies

logger = logging.getLogger(__name__)


class ScanManager:
    """Runs library scans in a worker thread and tracks status via events.

    The heavy lifting stays in LibraryService/Scanner; this only manages the
    thread and a status snapshot built from the existing EventBus events.
    """

    def __init__(self, services) -> None:
        self.services = services
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self.status: dict = {
            "running": False,
            "started_at": None,
            "finished_at": None,
            "location_id": None,
            "current_path": "",
            "phase": "",
            "files_seen": 0,
            "files_indexed": 0,
            "errors": 0,
            "last_result": None,
        }
        services.events.subscribe(object, self._on_event)

    # -- events -------------------------------------------------------------
    def _on_event(self, event) -> None:
        name = type(event).__name__
        if name == "LibraryScanProgress":
            with self._lock:
                self.status["current_path"] = getattr(event, "current_path", "")
                self.status["files_seen"] = getattr(event, "files_seen", 0)
                self.status["files_indexed"] = getattr(event, "files_indexed", 0)
                self.status["phase"] = getattr(event, "phase", "")
                self.status["location_id"] = getattr(event, "location_id", None)
        elif name == "LibraryScanStarted":
            with self._lock:
                self.status["location_id"] = getattr(event, "location_id", None)
        elif name == "LibraryScanFinished":
            with self._lock:
                self.status["errors"] = getattr(event, "errors", 0)
                self.status["last_result"] = {
                    key: getattr(event, key)
                    for key in (
                        "status", "files_seen", "files_indexed", "files_missing",
                        "files_added", "files_removed", "movies_added", "shows_added",
                        "episodes_added", "artists_added", "albums_added", "tracks_added",
                        "errors", "duration_seconds", "message",
                    )
                }

    # -- control ------------------------------------------------------------
    @property
    def running(self) -> bool:
        thread = self._thread
        return bool(thread and thread.is_alive())

    def start(self, location_id: int | None = None) -> bool:
        """Start a scan (all locations or one). Returns False if already running."""
        with self._lock:
            if self.running:
                return False
            import datetime

            self.status.update(
                running=True,
                started_at=datetime.datetime.now().isoformat(timespec="seconds"),
                finished_at=None,
                location_id=location_id,
                current_path="",
                phase="indexing",
                files_seen=0,
                files_indexed=0,
                errors=0,
            )
            self._thread = threading.Thread(
                target=self._run, args=(location_id,), daemon=True, name="jmdb-scan"
            )
            self._thread.start()
            return True

    def _run(self, location_id: int | None) -> None:
        import datetime

        library = self.services.library
        try:
            if location_id is None:
                counts = library.scan_all()
            else:
                counts = library.scan_location(location_id)
            logger.info("api-triggered scan finished: %s", counts)
        except Exception:
            logger.exception("api-triggered scan failed")
        finally:
            with self._lock:
                self.status["running"] = False
                self.status["finished_at"] = datetime.datetime.now().isoformat(
                    timespec="seconds"
                )

    def snapshot(self) -> dict:
        with self._lock:
            status = dict(self.status)
        status["running"] = self.running
        return status


class APIContext:
    """Holds the DI graph and API-scoped helpers for the route handlers."""

    def __init__(self, deps: Dependencies, token: str) -> None:
        self.deps = deps
        self.services = deps.build()
        self.token = token
        self.scan = ScanManager(self.services)

    @property
    def profile_id(self) -> int:
        return self.services.profile.id

    def close(self) -> None:
        try:
            self.deps.close()
        except Exception:
            logger.exception("error closing dependencies")
