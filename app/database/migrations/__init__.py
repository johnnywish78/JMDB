"""Versioned database migrations.

Each migration is ``(version, name, [sql statements])``. Versions are
monotonic; the applied version is stored in ``schema_migrations``.
Migrations run inside a transaction; a failed migration rolls back and
aborts startup with a clear error.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import NamedTuple

from app.database.connection import Database

from .initial import INITIAL_SQL

logger = logging.getLogger(__name__)


class Migration(NamedTuple):
    version: int
    name: str
    statements: list[str]


MIGRATIONS: list[Migration] = [
    Migration(1, "initial schema", INITIAL_SQL),
]


def current_version(db: Database) -> int:
    tables = db.table_names()
    if "schema_migrations" not in tables:
        return 0
    return int(db.scalar("SELECT COALESCE(MAX(version), 0) FROM schema_migrations") or 0)


def apply_migrations(db: Database) -> int:
    """Apply pending migrations; returns the resulting schema version."""
    db.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        " version INTEGER PRIMARY KEY,"
        " name TEXT NOT NULL,"
        " applied_at TEXT NOT NULL)"
    )
    version = current_version(db)
    for migration in MIGRATIONS:
        if migration.version <= version:
            continue
        logger.info("applying migration %s: %s", migration.version, migration.name)
        with db.transaction() as conn:
            for statement in migration.statements:
                conn.execute(statement)
            conn.execute(
                "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?,?,?)",
                (migration.version, migration.name, datetime.utcnow().isoformat()),
            )
        version = migration.version
    return version
