"""Dependency graph construction: paths → config → database → services."""
from __future__ import annotations

import logging

from app.config.paths import Paths
from app.config.secrets import SecretsStore
from app.config.settings import SettingsService
from app.database.connection import Database
from app.database.migrations import apply_migrations
from app.database.repositories import Repositories
from app.domain.events import EventBus
from app.services_app.coordinator import AppServices, build_services

logger = logging.getLogger(__name__)


class Dependencies:
    """Owns the full object graph and its teardown."""

    def __init__(self) -> None:
        self.paths = Paths.create()
        self.paths.ensure_directories()
        self.events = EventBus()
        self.settings = SettingsService(self.paths.config)
        self.secrets = SecretsStore(self.paths.config)
        self.db = Database(self.paths.database_file)
        version = apply_migrations(self.db)
        logger.info("database ready at %s (schema v%s)", self.paths.database_file, version)
        self.repos = Repositories(self.db)
        self.profile = self.repos.profiles.ensure_default()
        self.services: AppServices | None = None

    def build(self) -> AppServices:
        if self.services is None:
            self.services = build_services(
                self.paths, self.settings, self.secrets, self.events,
                self.db, self.repos, self.profile,
            )
        return self.services

    def close(self) -> None:
        try:
            if self.db.is_open:
                self.db.close()
        except Exception:
            logger.exception("error closing database")
