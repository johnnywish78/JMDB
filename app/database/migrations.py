"""PRAGMA user_version driven migrations. Append, never edit old ones."""
from __future__ import annotations

import logging

from app.database.connection import Database
from app.database.schema import SCHEMA_V1, SCHEMA_V2, SCHEMA_V3

log = logging.getLogger("jmdb.db")

MIGRATIONS: list[tuple[int, str]] = [
    (1, SCHEMA_V1),
    (2, SCHEMA_V2),
    (3, SCHEMA_V3),
]


def migrate(db: Database) -> int:
    row = db.query_one("PRAGMA user_version")
    current = int(row["user_version"]) if row else 0
    target = MIGRATIONS[-1][0] if MIGRATIONS else 0
    for version, script in MIGRATIONS:
        if version > current:
            db.executescript(script)
            db.execute(f"PRAGMA user_version={version}")
            log.info("applied migration v%s", version)
            current = version
    return target
