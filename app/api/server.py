"""JMDB FastAPI — local HTTP API.

Binds to 127.0.0.1 only. Serves the Electron renderer.
All routes delegate to the existing Container / repositories.
"""
from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

log = logging.getLogger("jmdb.api")

# ── module-level state ────────────────────────────────────────────────────────
_container = None
_auth_token = ""
app: FastAPI | None = None


def _get_container():
    global _container
    if _container is None:
        from app.bootstrap.dependencies import Container
        _container = Container()
    return _container


def _build_app(port: int = 18932) -> FastAPI:
    """Build and return the FastAPI app (called once at startup)."""
    global _auth_token, app
    if app is not None:
        return app
    _auth_token = uuid.uuid4().hex[:16]
    log.info("JMDB API token: %s…", _auth_token[:8])

    @asynccontextmanager
    async def lifespan(app: FastAPI):  # noqa: F811
        log.info("JMDB API starting on 127.0.0.1:%d", port)
        yield
        log.info("JMDB API shutting down")
        if _container is not None:
            _container.close()

    fa = FastAPI(title="JMDB", version="1.1.0", lifespan=lifespan)
    fa.add_middleware(
        CORSMiddleware,
        allow_origins=[f"http://127.0.0.1:{port}", "electron://JMDB"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app = fa
    return fa


def init_app(port: int = 18932) -> tuple[FastAPI, str]:
    """Called by serve.py and tests. Returns (app, token)."""
    return _build_app(port), _auth_token


# ══════════════════════════════════════════════════════════════════════════════
# ROUTES
# ══════════════════════════════════════════════════════════════════════════════

_health_app = _build_app()


@_health_app.get("/api/health")
async def health():
    return {"status": "ok", "token_hint": f"{_auth_token[:8]}…"}


@_health_app.get("/api/app/info")
async def app_info():
    c = _get_container()
    return {
        "name": "JMDB",
        "version": "1.1.0",
        "movies": c.media_repo.count("movie"),
        "shows": c.media_repo.count("show"),
        "music": c.media_repo.count("music"),
        "schema_version": c.schema_version,
    }


# ── settings ──────────────────────────────────────────────────────────────────

@_health_app.get("/api/settings")
async def get_settings():
    c = _get_container()
    s = c.settings
    data = dict(s._data)
    for k in ("tmdb_api_key", "omdb_api_key"):
        v = data.get(k, "")
        data[k] = f"{v[:4]}…{v[-4:]}" if len(v) > 8 else ("*" * min(8, len(v)) if v else "")
    return data


@_health_app.patch("/api/settings")
async def update_settings(body: dict):
    c = _get_container()
    for key, val in body.items():
        c.settings.set(key, val)
    return {"ok": True}


# ── library ───────────────────────────────────────────────────────────────────

@_health_app.get("/api/library")
async def get_library(kind: str = Query("movie")):
    c = _get_container()
    items = c.media_repo.list(kind, sort="rating")
    return {"kind": kind, "total": len(items), "items": items}


@_health_app.get("/api/library/movies")
async def get_movies(sort: str = "rating", genre: str | None = None, limit: int | None = None):
    c = _get_container()
    items = c.media_repo.list("movie", sort=sort, genre=genre, limit=limit)
    return {"total": len(items), "items": items}


@_health_app.get("/api/library/tv")
async def get_tv(sort: str = "rating", limit: int | None = None):
    c = _get_container()
    items = c.media_repo.list("show", sort=sort, limit=limit)
    return {"total": len(items), "items": items}


@_health_app.get("/api/library/music")
async def get_music(sort: str = "title", limit: int | None = None):
    c = _get_container()
    items = c.media_repo.list("music", sort=sort, limit=limit)
    return {"total": len(items), "items": items}


# ── media detail ──────────────────────────────────────────────────────────────

@_health_app.get("/api/media/{media_id}")
async def get_media(media_id: int):
    c = _get_container()
    item = c.media_repo.get(media_id)
    if not item:
        raise HTTPException(404, "Media not found")
    return item


@_health_app.get("/api/movies/{media_id}")
async def get_movie(media_id: int):
    return await get_media(media_id)


@_health_app.get("/api/shows/{media_id}")
async def get_show(media_id: int):
    c = _get_container()
    item = c.media_repo.get(media_id)
    if not item or item["kind"] != "show":
        raise HTTPException(404, "Show not found")
    episodes = c.episode_repo.for_show(media_id)
    return {**item, "episodes": episodes}


@_health_app.get("/api/episodes/{episode_id}")
async def get_episode(episode_id: int):
    c = _get_container()
    ep = c.episode_repo.get(episode_id)
    if not ep:
        raise HTTPException(404, "Episode not found")
    return ep


# ── people ────────────────────────────────────────────────────────────────────

@_health_app.get("/api/people")
async def get_people():
    c = _get_container()
    return {"people": c.people_repo.all_people()}


@_health_app.get("/api/people/{name}")
async def get_person(name: str):
    c = _get_container()
    items = c.people_repo.items_for(name)
    return {"name": name, "items": items}


# ── search ────────────────────────────────────────────────────────────────────

@_health_app.get("/api/search")
async def search(q: str = "", kind: str | None = None, limit: int = 50):
    c = _get_container()
    results = c.search.search(q, limit=limit)
    if kind:
        results = [r for r in results if r.get("kind") == kind]
    return {"query": q, "total": len(results), "results": results}


# ── home ──────────────────────────────────────────────────────────────────────

@_health_app.get("/api/home")
async def get_home():
    c = _get_container()
    trending = c.media_repo.list("movie", sort="rating", limit=10)
    recently_added = (
        c.media_repo.list("movie", sort="added", limit=6)
        + c.media_repo.list("show", sort="added", limit=4)
    )
    continue_watching = c.progress_repo.in_progress()
    favorites_ids = c.state_repo.favorites()
    favorites = c.media_repo.by_ids(sorted(favorites_ids))
    recommendations = c.reco.for_you(10)
    return {
        "trending": trending,
        "recently_added": recently_added,
        "continue_watching": continue_watching,
        "favorites": favorites,
        "recommendations": recommendations,
    }


# ── favorites ─────────────────────────────────────────────────────────────────

@_health_app.get("/api/favorites")
async def getFavorites():
    c = _get_container()
    ids = c.state_repo.favorites()
    items = c.media_repo.by_ids(sorted(ids))
    return {"ids": sorted(ids), "items": items}


@_health_app.post("/api/favorites/{media_id}")
async def add_favorite(media_id: int):
    c = _get_container()
    state = c.state_repo.toggle_favorite(media_id)
    return {"favorited": state}


@_health_app.delete("/api/favorites/{media_id}")
async def remove_favorite(media_id: int):
    c = _get_container()
    c.state_repo.toggle_favorite(media_id)
    return {"ok": True}


# ── watchlist ─────────────────────────────────────────────────────────────────

@_health_app.get("/api/watchlist")
async def get_watchlist():
    c = _get_container()
    ids = c.state_repo.watchlist()
    items = c.media_repo.by_ids(sorted(ids))
    return {"ids": sorted(ids), "items": items}


@_health_app.post("/api/watchlist/{media_id}")
async def add_watchlist(media_id: int):
    c = _get_container()
    state = c.state_repo.toggle_watchlist(media_id)
    return {"in_watchlist": state}


@_health_app.delete("/api/watchlist/{media_id}")
async def remove_watchlist(media_id: int):
    c = _get_container()
    c.state_repo.toggle_watchlist(media_id)
    return {"ok": True}


# ── history ───────────────────────────────────────────────────────────────────

@_health_app.get("/api/history")
async def get_history(limit: int = 100):
    c = _get_container()
    return {"entries": c.history_repo.recent(limit)}


# ── continue watching ─────────────────────────────────────────────────────────

@_health_app.get("/api/continue-watching")
async def continue_watching(min_seconds: int = 30):
    c = _get_container()
    rows = c.progress_repo.in_progress(min_seconds)
    return {"items": rows}


# ── recommendations ───────────────────────────────────────────────────────────

@_health_app.get("/api/recommendations")
async def recommendations(limit: int = 18):
    c = _get_container()
    items = c.reco.for_you(limit)
    return {"items": items}


# ── statistics ────────────────────────────────────────────────────────────────

@_health_app.get("/api/statistics")
async def statistics():
    c = _get_container()
    return c.stats.overview()


# ── scanner ───────────────────────────────────────────────────────────────────

_scan_status: dict = {"running": False, "summary": None, "current_file": ""}


@_health_app.get("/api/scan/status")
async def scan_status():
    return _scan_status


@_health_app.post("/api/scan")
async def start_scan(folders: list[str] | None = None, enrich: bool = True):
    if _scan_status["running"]:
        return {"ok": False, "message": "Scan already running"}
    _scan_status.update({"running": True, "summary": None, "current_file": ""})

    import threading
    from app.library.scanner import ScanWorker
    from app.library.indexer import LibraryIndexer

    c = _get_container()
    folders = folders or c.settings.get("library_folders", [])
    if not folders:
        _scan_status["running"] = False
        _scan_status["summary"] = {"error": "No library folders configured"}
        return {"ok": False, "message": "No library folders"}

    def _run():
        indexer = LibraryIndexer(c.media_repo, c.episode_repo)
        mgr = c.metadata if enrich else None
        worker = ScanWorker(folders, indexer, metadata_manager=mgr, enrich=enrich)

        def _on_progress(cur, total, path):
            _scan_status["current_file"] = Path(path).name

        def _on_finished(summary):
            _scan_status["running"] = False
            _scan_status["summary"] = summary

        worker.progressed.connect(_on_progress)
        worker.finished_summary.connect(_on_finished)
        worker.start()
        worker.wait()

    threading.Thread(target=_run, daemon=True).start()
    return {"ok": True, "message": "Scan started"}


# ── bookmarks ─────────────────────────────────────────────────────────────────

@_health_app.get("/api/bookmarks")
async def get_bookmarks():
    c = _get_container()
    return {"bookmarks": c.bookmarks.all()}


@_health_app.post("/api/bookmarks")
async def add_bookmark(name: str, url: str):
    c = _get_container()
    c.bookmarks.add(name, url)
    return {"ok": True}


@_health_app.delete("/api/bookmarks/{bm_id}")
async def remove_bookmark(bm_id: int):
    c = _get_container()
    c.bookmarks.remove(bm_id)
    return {"ok": True}


# ── services ──────────────────────────────────────────────────────────────────

@_health_app.get("/api/services")
async def get_services():
    c = _get_container()
    return {"services": [s.__dict__ for s in c.services.services()]}


# ── playback ──────────────────────────────────────────────────────────────────

@_health_app.post("/api/playback/start")
async def playback_start(payload: dict):
    c = _get_container()
    from app.domain.models import PlaybackPayload
    p = PlaybackPayload(
        media_key=payload.get("media_key", ""),
        title=payload.get("title", ""),
        subtitle=payload.get("subtitle", ""),
        file_path=payload.get("file_path"),
        duration_s=int(payload.get("duration_s") or 0),
        media_id=payload.get("media_id"),
        episode_id=payload.get("episode_id"),
        show_id=payload.get("show_id"),
        season=payload.get("season"),
        number=payload.get("number"),
    )
    c.playback.session_started(p)
    return {"ok": True}


@_health_app.post("/api/playback/progress")
async def playback_progress(position_s: int = 0, duration_s: int = 0):
    c = _get_container()
    c.playback.tick(position_s, duration_s)
    return {"ok": True}


@_health_app.post("/api/playback/stop")
async def playback_stop(position_s: int = 0, duration_s: int = 0):
    c = _get_container()
    c.playback.session_stopped(position_s, duration_s)
    return {"ok": True}


@_health_app.post("/api/playback/finish")
async def playback_finish():
    c = _get_container()
    next_payload = c.playback.session_finished()
    return {"ok": True, "next_payload": next_payload.__dict__ if next_payload else None}


@_health_app.get("/api/playback/{media_key}")
async def get_playback(media_key: str):
    c = _get_container()
    progress = c.progress_repo.get(media_key)
    return {"progress": progress}


# ── metadata ──────────────────────────────────────────────────────────────────

@_health_app.post("/api/re-enrich/{media_id}")
async def re_enrich(media_id: int, clear_cache: bool = False):
    c = _get_container()
    from app.library.media_detector import detect
    item = c.media_repo.get(media_id)
    if not item:
        raise HTTPException(404, "Media not found")
    detected = detect(item.get("file_path", ""))
    result = c.metadata.re_enrich(media_id, detected, media_repo=c.media_repo, clear_cache=clear_cache)
    updated = c.media_repo.get(media_id)
    return {"ok": True, "result": result, "updated": updated}


# ── cache ─────────────────────────────────────────────────────────────────────

@_health_app.get("/api/cache/stats")
async def cache_stats():
    c = _get_container()
    return c.metadata.cache_stats()


@_health_app.post("/api/cache/clear")
async def cache_clear(bucket: str | None = None):
    c = _get_container()
    n = c.metadata.clear_cache(bucket)
    return {"cleared": n}


# ── artwork ───────────────────────────────────────────────────────────────────

@_health_app.get("/api/artwork/{kind}/{key}")
async def get_artwork(kind: str, key: str):
    c = _get_container()
    from app.metadata.artwork import ARTWORK_SUBDIRS
    import hashlib
    subdir = ARTWORK_SUBDIRS.get(kind, "posters")
    folder = c.paths.artwork_dir / subdir
    digest = hashlib.sha1(key.encode()).hexdigest()[:16]
    for ext in (".jpg", ".png"):
        p = folder / f"{digest}{ext}"
        if p.exists():
            return {"path": str(p), "url": f"file://{p}"}
    return {"path": None}
