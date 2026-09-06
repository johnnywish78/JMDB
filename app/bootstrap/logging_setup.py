"""Structured logging setup with secret redaction.

Logs go to ``~/.jmdb/logs/jmdb.log`` (rotating) and to stderr. Secrets
(API keys) are masked everywhere via a logging filter.
"""
from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path

from app.config.secrets import SecretRedactor

FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
_reductor = SecretRedactor()


def configure_logging(logs_dir: Path, level: str = "INFO") -> SecretRedactor:
    logs_dir.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    for handler in list(root.handlers):
        root.removeHandler(handler)

    formatter = logging.Formatter(FORMAT)

    file_handler = logging.handlers.RotatingFileHandler(
        logs_dir / "jmdb.log", maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    file_handler.addFilter(_reductor)
    root.addHandler(file_handler)

    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(formatter)
    console.addFilter(_reductor)
    root.addHandler(console)

    # third-party noise reduction
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("PyQt6").setLevel(logging.WARNING)
    return _reductor


def install_redactor(redactor: SecretRedactor, secrets: list[str]) -> None:
    redactor.set_secrets(secrets)
