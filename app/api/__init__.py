"""EpisodeRepo accessor for API module."""
from __future__ import annotations
from app.database.repositories import EpisodeRepository


def _episode_repo():
    from app.bootstrap.dependencies import _get_container
    return EpisodeRepository(_get_container().db)
