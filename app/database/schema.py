"""Schema helpers: introspection + validation used by diagnostics/tests."""
from __future__ import annotations

from app.database.connection import Database
from app.database.migrations import MIGRATIONS, current_version


def schema_version(db: Database) -> int:
    return current_version(db)


def latest_schema_version() -> int:
    return MIGRATIONS[-1].version


def describe_schema(db: Database) -> dict[str, list[str]]:
    """Table → column names, for docs/diagnostics."""
    return {table: db.column_names(table) for table in sorted(db.table_names())}


def validate_foreign_keys(db: Database) -> list[str]:
    """Run SQLite's foreign-key check; returns list of violations."""
    return [f"{r[0]} rowid={r[1]} fk={r[2]}" for r in db.query("PRAGMA foreign_key_check")]
