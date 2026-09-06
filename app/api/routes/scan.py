"""Library scanning endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

router = APIRouter()


@router.get("/scan/status")
def scan_status(request: Request) -> dict:
    return request.app.state.context.scan.snapshot()


@router.post("/scan")
def start_scan(request: Request, body: dict = None) -> dict:
    scan = request.app.state.context.scan
    location_id = (body or {}).get("location_id")
    if location_id is not None:
        location_id = int(location_id)
    if not scan.start(location_id):
        raise HTTPException(status_code=409, detail="a scan is already running")
    return {"started": True, "location_id": location_id}
