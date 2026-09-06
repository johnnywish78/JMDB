"""FastAPI application factory and server entry point."""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api.auth import auth_middleware, generate_token
from app.api.context import APIContext
from app.api.events import EventBridge

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_UI_DIR = REPO_ROOT / "electron" / "src"


def create_app(
    context: APIContext | None = None,
    token: str | None = None,
    ui_dir: Path | None = None,
) -> FastAPI:
    """Build the JMDB API app.

    ``context`` may be omitted for tests that want to construct services
    differently; a default Dependencies graph is built then.
    """
    from app.bootstrap.dependencies import Dependencies

    owns_context = context is None
    if context is None:
        context = APIContext(Dependencies(), token or generate_token())

    app = FastAPI(
        title="JMDB API",
        version=__version__,
        docs_url=None,   # no public swagger on a local token-guarded API
        redoc_url=None,
        openapi_url=None,
    )
    app.state.context = context
    app.state.token = context.token
    app.state.owns_context = owns_context

    app.middleware("http")(auth_middleware)

    bridge = EventBridge(context.services.events)
    app.state.bridge = bridge

    @app.on_event("startup")
    async def _startup() -> None:
        await bridge.start()

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        await bridge.stop()
        if owns_context:
            context.close()

    # -- routers ---------------------------------------------------------------
    from app.api.routes import (
        artwork,
        bookmarks,
        home,
        library,
        lists,
        media,
        playback,
        recommendations,
        scan,
        search,
        services,
        settings,
        statistics,
        system,
    )

    for router in (
        system.router,
        settings.router,
        library.router,
        media.router,
        search.router,
        home.router,
        lists.router,
        recommendations.router,
        statistics.router,
        scan.router,
        bookmarks.router,
        services.router,
        artwork.router,
        playback.router,
    ):
        app.include_router(router, prefix="/api")

    # -- websocket ---------------------------------------------------------------
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        from app.api.auth import request_authorized

        token = getattr(websocket.app.state, "token", "")
        if not request_authorized(websocket, token):
            await websocket.close(code=4401)
            return
        await bridge.connect(websocket)

    # -- bundled Electron UI (same-origin: cookie auth, no CORS) ------------------
    ui_root = Path(ui_dir) if ui_dir is not None else DEFAULT_UI_DIR
    if (ui_root / "index.html").exists():
        app.mount(
            "/app",
            StaticFiles(directory=str(ui_root), html=True),
            name="app",
        )

        @app.get("/app/boot")
        async def app_boot(request: Request):
            """Token → HttpOnly session cookie, then into the UI."""
            from app.api.auth import request_authorized

            token = getattr(request.app.state, "token", "")
            if not request_authorized(request, token):
                return JSONResponse({"detail": "unauthorized"}, status_code=401)
            response = RedirectResponse(url="/app/")
            response.set_cookie(
                "jmdb_token", token, httponly=True, samesite="strict",
            )
            return response

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        logger.exception("api error on %s %s", request.method, request.url.path)
        return JSONResponse({"detail": f"internal error: {exc}"}, status_code=500)

    return app


def run_server(
    host: str = "127.0.0.1",
    port: int = 8737,
    token: str | None = None,
    ui_dir: Path | None = None,
    log_level: str = "info",
) -> None:
    """Run the API with uvicorn (blocking). Used by run.py and __main__."""
    import uvicorn

    token = token or generate_token()
    app = create_app(token=token, ui_dir=ui_dir)
    uvicorn.run(app, host=host, port=port, log_level=log_level, access_log=False)
