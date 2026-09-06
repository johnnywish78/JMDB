"""System endpoints: health + app info."""
from __future__ import annotations

import platform
import sys

from fastapi import APIRouter, Request

from app import __version__

router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "version": __version__}


@router.get("/app/info")
def app_info(request: Request) -> dict:
    services = request.app.state.context.services
    backends = services.playback.backend_availability()
    return {
        "name": "JMDB",
        "version": __version__,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "database_path": str(services.paths.database_file),
        "profile": {"id": services.profile.id, "name": services.profile.name},
        "playback_backends": backends,
        "providers": {
            provider_id: provider.is_configured()
            for provider_id, provider in services.providers.items()
        },
    }
