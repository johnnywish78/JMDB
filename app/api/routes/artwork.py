"""Artwork serving with a strict allowlist.

Only files under the JMDB home (cache/config/artwork) or one of the
registered library roots are served — no arbitrary filesystem reads.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse

router = APIRouter()


def allowed_roots(services) -> list[Path]:
    roots = [
        services.paths.home,
    ]
    try:
        roots.extend(Path(loc.path) for loc in services.library.locations())
    except Exception:  # pragma: no cover
        pass
    return [root.resolve() for root in roots if root]


def path_is_allowed(services, path: Path) -> bool:
    try:
        resolved = Path(path).resolve()
    except (OSError, RuntimeError):
        return False
    for root in allowed_roots(services):
        if resolved == root or root in resolved.parents:
            return True
    return False


@router.get("/artwork")
def artwork(request: Request, path: str = Query(...)) -> FileResponse:
    services = request.app.state.context.services
    target = Path(path)
    if not path_is_allowed(services, target) or not target.is_file():
        raise HTTPException(status_code=404, detail="artwork not found")
    return FileResponse(
        str(target),
        headers={"Cache-Control": "private, max-age=86400"},
    )
