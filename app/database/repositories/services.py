"""Service accounts (per-service configuration) + application settings KV."""
from __future__ import annotations

import json

from app.domain.models import ServiceAccount
from app.database.repositories import BaseRepository, row_to_dataclass


class ServiceAccountsRepository(BaseRepository):
    def set_config(self, service_id: str, config: dict) -> None:
        self.db.execute(
            "INSERT INTO service_accounts (service_id, config_json, updated_at)"
            " VALUES (?,?,datetime('now'))"
            " ON CONFLICT(service_id) DO UPDATE SET config_json=excluded.config_json,"
            " updated_at=excluded.updated_at",
            (service_id, json.dumps(config)),
        )

    def get_config(self, service_id: str) -> dict:
        row = self.db.query_one(
            "SELECT config_json FROM service_accounts WHERE service_id=?", (service_id,)
        )
        if row is None:
            return {}
        try:
            value = json.loads(row["config_json"])
            return value if isinstance(value, dict) else {}
        except (ValueError, TypeError):
            return {}

    def all(self) -> list[ServiceAccount]:
        rows = self.db.query("SELECT * FROM service_accounts ORDER BY service_id")
        out = []
        for r in rows:
            try:
                config = json.loads(r["config_json"])
            except (ValueError, TypeError):
                config = {}
            out.append(
                ServiceAccount(id=r["id"], service_id=r["service_id"], config=config)
            )
        return out

    def delete(self, service_id: str) -> None:
        self.db.execute("DELETE FROM service_accounts WHERE service_id=?", (service_id,))


class AppSettingsRepository(BaseRepository):
    """DB-side key/value settings (internal app state, not user preferences)."""

    def get(self, key: str, default=None):
        row = self.db.query_one("SELECT value_json FROM application_settings WHERE key=?", (key,))
        if row is None:
            return default
        try:
            return json.loads(row["value_json"])
        except (ValueError, TypeError):
            return default

    def set(self, key: str, value) -> None:
        self.db.execute(
            "INSERT INTO application_settings (key, value_json, updated_at)"
            " VALUES (?,?,datetime('now'))"
            " ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json,"
            " updated_at=excluded.updated_at",
            (key, json.dumps(value)),
        )

    def all(self) -> dict:
        rows = self.db.query("SELECT key, value_json FROM application_settings")
        out = {}
        for r in rows:
            try:
                out[r["key"]] = json.loads(r["value_json"])
            except (ValueError, TypeError):
                out[r["key"]] = r["value_json"]
        return out
