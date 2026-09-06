"""Local API authentication: bearer token or same-origin session cookie.

The token is generated per server launch and shared with Electron via a
file (never printed). The renderer gets an HttpOnly cookie via /app/boot.
"""
from __future__ import annotations

import secrets

from fastapi import Request
from fastapi.responses import JSONResponse

OPEN_PATHS = ("/api/health",)


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def _cookie_name(request: Request) -> str:
    return "jmdb_token"


def request_authorized(request: Request, token: str) -> bool:
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer ") and secrets.compare_digest(auth[7:], token):
        return True
    query_token = request.query_params.get("token", "")
    if query_token and secrets.compare_digest(query_token, token):
        return True
    cookie = request.cookies.get(_cookie_name(request), "")
    if cookie and secrets.compare_digest(cookie, token):
        return True
    return False


def host_is_local(request: Request) -> bool:
    """Reject non-local Host headers (DNS-rebinding defense)."""
    host = (request.headers.get("host") or "").split(":")[0].lower()
    # "testserver" is FastAPI's TestClient default host
    return host in ("127.0.0.1", "localhost", "[::1]", "::1", "testserver")


async def auth_middleware(request: Request, call_next):
    if not host_is_local(request):
        return JSONResponse({"detail": "local access only"}, status_code=421)
    path = request.url.path
    if path in OPEN_PATHS or path.startswith("/app"):
        # /app/* is the bundled UI; the bootstrap route sets the session
        # cookie and everything else still requires it via /api
        return await call_next(request)
    if path.startswith("/api") or path.startswith("/ws"):
        token = getattr(request.app.state, "token", "")
        if not request_authorized(request, token):
            return JSONResponse({"detail": "unauthorized"}, status_code=401)
    return await call_next(request)
