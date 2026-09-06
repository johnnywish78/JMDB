"""SQLite connection management.

A single serialized connection (WAL mode, foreign keys enforced) shared
across threads behind a re-entrant lock. For this application's workload
(one desktop process, bursty short queries) this is simpler and safer than
a connection pool and keeps transaction semantics explicit.
"""
from __future__ import annotations

import logging
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

logger = logging.getLogger(__name__)

PRAGMAS = (
    "PRAGMA journal_mode=WAL",
    "PRAGMA foreign_keys=ON",
    "PRAGMA synchronous=NORMAL",
    "PRAGMA busy_timeout=10000",
)


class Database:
    """Wrapper around a sqlite3 connection with helpers and migrations."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(
            str(self.path), check_same_thread=False, timeout=15.0
        )
        self._conn.row_factory = sqlite3.Row
        for pragma in PRAGMAS:
            self._conn.execute(pragma)

    # -- lifecycle -------------------------------------------------------
    def close(self) -> None:
        with self._lock:
            try:
                self._conn.commit()
            except sqlite3.Error:  # pragma: no cover
                pass
            self._conn.close()

    @property
    def is_open(self) -> bool:
        try:
            self._conn.execute("SELECT 1")
            return True
        except sqlite3.ProgrammingError:
            return False

    # -- execution -------------------------------------------------------
    def execute(self, sql: str, params: tuple | list = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur

    def executemany(self, sql: str, seq: list[tuple]) -> None:
        with self._lock:
            self._conn.executemany(sql, seq)
            self._conn.commit()

    def query(self, sql: str, params: tuple | list = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    def query_one(self, sql: str, params: tuple | list = ()) -> sqlite3.Row | None:
        with self._lock:
            return self._conn.execute(sql, params).fetchone()

    def scalar(self, sql: str, params: tuple | list = ()) -> Any:
        row = self.query_one(sql, params)
        return row[0] if row is not None else None

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Group statements into one transaction; roll back on error."""
        with self._lock:
            try:
                yield self._conn
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    # -- introspection ------------------------------------------------------
    def table_names(self) -> set[str]:
        rows = self.query(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        return {r["name"] for r in rows}

    def column_names(self, table: str) -> list[str]:
        rows = self.query(f"PRAGMA table_info({table})")
        return [r["name"] for r in rows]

    def fts5_available(self) -> bool:
        try:
            self.query("CREATE VIRTUAL TABLE IF NOT EXISTS tmp_fts_probe USING fts5(x)")
            self.query("DROP TABLE IF EXISTS tmp_fts_probe")
            return True
        except sqlite3.Error:
            return False
