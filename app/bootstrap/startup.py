"""Startup sequence for the JMDB application."""
from __future__ import annotations

import logging
import os
import sys

from app.bootstrap.dependencies import Dependencies
from app.bootstrap.logging_setup import configure_logging, install_redactor
from app.config.secrets import PROVIDER_LABELS

logger = logging.getLogger(__name__)


def prepare_environment() -> None:
    """Environment tweaks that must happen before Qt starts."""
    # WebEngine sandbox cannot work in containers / as root
    running_as_root = hasattr(os, "geteuid") and os.geteuid() == 0
    if running_as_root or os.environ.get("JMDB_CONTAINER"):
        os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
    os.environ.setdefault(
        "QTWEBENGINE_CHROMIUM_FLAGS",
        "--no-sandbox --disable-gpu --disable-dev-shm-usage",
    )
    # software rendering fallback for systems without GPU acceleration
    os.environ.setdefault("QT_QUICK_BACKEND", "software")


def startup() -> Dependencies:
    """Configure logging, paths, database, and services. Returns dependencies."""
    from app.config.paths import Paths

    paths = Paths.create()
    paths.ensure_directories()
    redactor = configure_logging(paths.logs)
    logger.info("JMDB starting; data home: %s", paths.home)

    deps = Dependencies()
    install_redactor(redactor, deps.secrets.active_secrets())
    configured = [
        PROVIDER_LABELS[p]
        for p, key in deps.secrets.all_providers().items()
        if key
    ]
    logger.info("metadata providers configured: %s", ", ".join(configured) or "none")
    deps.build()
    return deps


def verify_imports() -> list[str]:
    """Sanity check that every top-level module imports; returns problems."""
    problems = []
    import importlib

    modules = [
        "app.config.paths",
        "app.config.settings",
        "app.config.secrets",
        "app.database.connection",
        "app.database.migrations",
        "app.database.repositories",
        "app.domain.events",
        "app.domain.models",
        "app.library.scanner",
        "app.library.probe",
        "app.metadata.manager",
        "app.metadata.artwork",
        "app.playback.service",
        "app.playback.controller",
        "app.browser.engine",
        "app.services.service_manager",
        "app.search.engine",
        "app.statistics.service",
        "app.recommendations.engine",
        "app.services_app.coordinator",
    ]
    for module in modules:
        try:
            importlib.import_module(module)
        except Exception as exc:
            problems.append(f"{module}: {exc}")
    return problems
