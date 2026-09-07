"""Library scanning endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter()


@router.get("/scan/status")
def scan_status(request: Request) -> dict:
    return request.app.state.context.scan.snapshot()


@router.post("/scan")
def start_scan(
    request: Request,
    location_id: int | None = Query(default=None),
    body: dict = None,
) -> dict:
    """Start a scan of every location (``location_id`` omitted) or one.

    ``location_id`` may arrive as a query parameter (the settings page sends
    ``/api/scan?location_id=3``) or inside the JSON body — both are accepted.
    """
    scan = request.app.state.context.scan
    if location_id is None:
        location_id = (body or {}).get("location_id")
    if location_id is not None:
        location_id = int(location_id)
        location = request.app.state.context.services.repos.locations.get(location_id)
        if location is None:
            raise HTTPException(status_code=404, detail="unknown location")
    if not scan.start(location_id):
        raise HTTPException(status_code=409, detail="a scan is already running")
    return {"started": True, "location_id": location_id}
