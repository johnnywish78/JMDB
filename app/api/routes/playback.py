"""Playback endpoints: session lifecycle, streaming, subtitles, external handoff.

The backend (PlaybackService) owns resume/watched/history/next-episode
decisions; the Electron player only reports what happened.
"""
from __future__ import annotations

import logging
import mimetypes
import os
import re
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response, StreamingResponse

from app.domain.events import PlaybackProgress

logger = logging.getLogger(__name__)

router = APIRouter()

CHUNK = 256 * 1024

MIME_OVERRIDES = {
    ".mkv": "video/x-matroska",
    ".m4v": "video/mp4",
    ".ts": "video/mp2t",
    ".flac": "audio/flac",
    ".m4a": "audio/mp4",
    ".oga": "audio/ogg",
}


def _catalog_for(services, media_type: str):
    return {
        "movie": services.movies,
        "episode": services.tv,
        "track": services.music,
    }.get(media_type)


def _queue_for(services, media_type: str, media_id: int, context: dict | None):
    """Backend-built play queue: season episodes / album tracks / single item."""
    repos = services.repos
    entries: list[dict] = []

    def entry(media_type_: str, media_id_: int, title: str, subtitle: str = "") -> dict:
        return {
            "media_type": media_type_,
            "media_id": media_id_,
            "title": title,
            "subtitle": subtitle,
        }

    context = context or {}
    if media_type == "episode":
        detail = repos.tv.episode_details(media_id, services.profile.id)
        season_id = (context.get("type") == "season" and context.get("id")) or (
            detail and detail.get("season_id")
        )
        if season_id:
            for episode in repos.tv.episodes_for_season(season_id, services.profile.id):
                if episode.get("file_path"):
                    entries.append(entry(
                        "episode", episode["id"], episode["title"],
                        f"S{episode.get('season_number', 0):02d}"
                        f"E{episode.get('episode_number', 0):02d} · "
                        f"{episode.get('show_title', '')}",
                    ))
    elif media_type == "track":
        album_id = context.get("type") == "album" and context.get("id")
        if album_id:
            for track in repos.music.tracks_for_album(int(album_id)):
                if track.get("file_path"):
                    entries.append(entry(
                        "track", track["id"], track["title"],
                        f"Track {track.get('track_number', 0)}",
                    ))
    if not entries:
        playable = _catalog_for(services, media_type)
        item = playable.playable(media_id) if playable else None
        if item is None:
            return []
        entries.append(entry(media_type, media_id, item.title, item.subtitle))
    return entries


def _subtitle_list(services, media_file_id: int) -> list[dict]:
    """Subtitle tracks the HTML player can actually render (.srt/.vtt).

    Embedded/ASS tracks need mpv/VLC; those are offered via the external
    player instead of being faked here.
    """
    out = []
    for option in services.subtitles.options_for(media_file_id):
        path = option.file_path or ""
        if not path:
            continue  # embedded track: not renderable by <track>
        lowered = path.lower()
        if lowered.endswith(".vtt"):
            url_kind = "vtt"
        elif lowered.endswith(".srt"):
            url_kind = "srt"
        else:
            continue
        out.append({
            "label": option.label,
            "language": option.language,
            "kind": url_kind,
            "url": f"/api/subtitles?path={path}",
        })
    return out


@router.post("/playback/start")
def playback_start(request: Request, body: dict) -> dict:
    services = request.app.state.context.services
    profile = services.profile.id
    media_type = body.get("media_type")
    media_id = body.get("media_id")
    if media_type not in ("movie", "episode", "track") or not media_id:
        raise HTTPException(status_code=400, detail="media_type/media_id invalid")

    catalog = _catalog_for(services, media_type)
    playable = catalog.playable(int(media_id))
    if playable is None:
        raise HTTPException(status_code=404, detail="no playable file for this item")

    media_file = services.repos.files.get(playable.media_file_id)
    queue = _queue_for(services, media_type, int(media_id), body.get("context"))
    if not queue:
        raise HTTPException(status_code=404, detail="could not build a play queue")

    session_id = services.playback.history.start(
        profile, media_type, int(media_id), playable.media_file_id
    )
    position = services.playback.resume.resume_position(profile, media_type, int(media_id)) or 0.0
    watched = services.repos.playback.is_watched(profile, media_type, int(media_id))

    path = Path(playable.path)
    suffix = path.suffix.lower()
    mime = MIME_OVERRIDES.get(suffix) or mimetypes.guess_type(str(path))[0] or "application/octet-stream"

    return {
        "session_id": session_id,
        "media": {
            "type": media_type,
            "id": int(media_id),
            "title": playable.title,
            "subtitle": playable.subtitle,
            "file": {
                "id": playable.media_file_id,
                "name": path.name,
                "size": (media_file.size_bytes if media_file else 0),
                "mime": mime,
                "exists": path.exists(),
            },
            "artwork_path": playable.artwork_path,
        },
        "stream_url": f"/api/stream/{playable.media_file_id}",
        "position": position,
        "duration_hint": playable.duration_seconds or 0.0,
        "watched": watched,
        "autoplay_next": bool(services.settings.get("autoplay_next")),
        "subtitles": _subtitle_list(services, playable.media_file_id),
        "queue": [
            dict(entry, current=(entry["media_type"] == media_type
                                 and entry["media_id"] == int(media_id)))
            for entry in queue
        ],
    }


@router.post("/playback/progress")
def playback_progress(request: Request, body: dict) -> dict:
    services = request.app.state.context.services
    profile = services.profile.id
    media_type = body.get("media_type")
    media_id = body.get("media_id")
    position = float(body.get("position") or 0.0)
    duration = float(body.get("duration") or 0.0)
    if media_type not in ("movie", "episode", "track") or not media_id:
        raise HTTPException(status_code=400, detail="media_type/media_id invalid")
    services.playback.resume.save(
        profile, media_type, int(media_id), position, duration
    )
    services.events.publish(PlaybackProgress(
        media_type=media_type, media_id=int(media_id),
        position_seconds=position, duration_seconds=duration,
    ))
    return {"ok": True}


@router.post("/playback/stop")
def playback_stop(request: Request, body: dict) -> dict:
    services = request.app.state.context.services
    session_id = body.get("session_id")
    position = float(body.get("position") or 0.0)
    duration = float(body.get("duration") or 0.0)
    if session_id:
        services.playback.history.finish(session_id, position, duration, False)
    return {"ok": True}


@router.post("/playback/finish")
def playback_finish(request: Request, body: dict) -> dict:
    """Playback completed. Backend decides watched state + next episode."""
    services = request.app.state.context.services
    profile = services.profile.id
    session_id = body.get("session_id")
    media_type = body.get("media_type")
    media_id = body.get("media_id")
    position = float(body.get("position") or 0.0)
    duration = float(body.get("duration") or 0.0)
    if media_type not in ("movie", "episode", "track") or not media_id:
        raise HTTPException(status_code=400, detail="media_type/media_id invalid")
    media_id = int(media_id)

    if session_id:
        services.playback.history.finish(session_id, position, duration, True)

    # watched when completed, or far enough along (backend rule)
    completed = bool(body.get("completed", True))
    enough = duration > 0 and position / duration >= (
        float(services.settings.get("mark_watched_pct")) / 100.0
    )
    if completed or enough:
        services.playback.mark_watched(profile, media_type, media_id)
        services.playback.resume.clear(profile, media_type, media_id)

    next_item = None
    if media_type == "episode":
        episode = services.tv.next_episode_after(media_id, profile)
        if episode:
            next_item = {
                "media_type": "episode",
                "media_id": episode["id"],
                "title": episode["title"],
                "subtitle": f"S{episode.get('season_number', 0):02d}"
                            f"E{episode.get('episode_number', 0):02d} · "
                            f"{episode.get('show_title', '')}",
                "still_path": episode.get("still_path", ""),
                "overview": episode.get("overview", ""),
            }
    return {"ok": True, "watched": completed or enough, "next": next_item,
            "autoplay_next": bool(services.settings.get("autoplay_next"))}


@router.get("/playback/state/{media_id}")
def playback_state(request: Request, media_id: int, media_type: str = Query(...)) -> dict:
    services = request.app.state.context.services
    profile = services.profile.id
    state = services.repos.playback.get_position(profile, media_type, media_id)
    return {
        "position": state.position_seconds if state else 0.0,
        "duration": state.duration_seconds if state else 0.0,
        "watched": services.repos.playback.is_watched(profile, media_type, media_id),
        "resume_seconds": services.playback.resume.resume_position(
            profile, media_type, media_id
        ) or 0.0,
    }


@router.post("/playback/external")
def playback_external(request: Request, body: dict) -> dict:
    """Hand off to the configured external player (mpv/VLC/vlc binary)."""
    services = request.app.state.context.services
    media_type = body.get("media_type")
    media_id = body.get("media_id")
    if media_type not in ("movie", "episode", "track") or not media_id:
        raise HTTPException(status_code=400, detail="media_type/media_id invalid")
    catalog = _catalog_for(services, media_type)
    playable = catalog.playable(int(media_id))
    if playable is None:
        raise HTTPException(status_code=404, detail="no playable file for this item")
    launched = services.playback.play_external(playable, services.profile.id)
    if not launched:
        raise HTTPException(
            status_code=503,
            detail="no external player found (configure one in Settings → Playback)",
        )
    return {"ok": True, "launched": True}


# -- file streaming ---------------------------------------------------------------

def _media_file_or_404(services, file_id: int) -> Path:
    media_file = services.repos.files.get(file_id)
    if media_file is None:
        raise HTTPException(status_code=404, detail="file not found")
    path = Path(media_file.path)
    if not path.exists() or media_file.is_missing:
        raise HTTPException(status_code=404, detail="file missing on disk")
    return path


def _range_stream(path: Path, start: int, end: int):
    with open(path, "rb") as handle:
        handle.seek(start)
        remaining = end - start + 1
        while remaining > 0:
            chunk = handle.read(min(CHUNK, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


@router.get("/stream/{file_id}")
def stream(
    request: Request,
    file_id: int,
    range_header: str | None = Header(default=None, alias="Range"),
):
    services = request.app.state.context.services
    path = _media_file_or_404(services, file_id)
    size = path.stat().st_size
    suffix = path.suffix.lower()
    mime = MIME_OVERRIDES.get(suffix) or mimetypes.guess_type(str(path))[0] or "application/octet-stream"

    if range_header:
        match = re.match(r"bytes=(\d*)-(\d*)", range_header.strip())
        if match:
            start = int(match.group(1) or 0)
            end = int(match.group(2) or size - 1)
            end = min(end, size - 1)
            if start > end or start >= size:
                return Response(status_code=416, headers={
                    "Content-Range": f"bytes */{size}"})
            return StreamingResponse(
                _range_stream(path, start, end),
                status_code=206,
                headers={
                    "Content-Range": f"bytes {start}-{end}/{size}",
                    "Accept-Ranges": "bytes",
                    "Content-Length": str(end - start + 1),
                    "Cache-Control": "no-store",
                },
                media_type=mime,
            )

    return StreamingResponse(
        _range_stream(path, 0, size - 1),
        headers={
            "Accept-Ranges": "bytes",
            "Content-Length": str(size),
            "Cache-Control": "no-store",
        },
        media_type=mime,
    )


# -- subtitles (SRT → WebVTT so the HTML player can render them) ------------------

def _srt_to_vtt(content: str) -> str:
    def fix_timestamp(match: re.Match) -> str:
        return match.group(0).replace(",", ".")

    body = re.sub(
        r"\d{2}:\d{2}:\d{2}[,.]\d{3}",
        fix_timestamp,
        content,
    )
    body = re.sub(r"^\d+\s*$", "", body, flags=re.MULTILINE)  # drop indexes
    body = body.replace("\r\n", "\n").strip()
    return f"WEBVTT\n\n{body}\n"


@router.get("/subtitles")
def subtitles(request: Request, path: str = Query(...)) -> Response:
    services = request.app.state.context.services
    from app.api.routes.artwork import path_is_allowed

    target = Path(path)
    if not path_is_allowed(services, target) or not target.is_file():
        raise HTTPException(status_code=404, detail="subtitle not found")
    lowered = str(target).lower()
    if lowered.endswith(".vtt"):
        return FileResponse(str(target), media_type="text/vtt")
    if lowered.endswith(".srt"):
        try:
            text = target.read_text("utf-8", errors="replace")
        except OSError:
            raise HTTPException(status_code=404, detail="subtitle not readable")
        return Response(
            _srt_to_vtt(text), media_type="text/vtt",
            headers={"Cache-Control": "private, max-age=3600"},
        )
    raise HTTPException(status_code=415, detail="unsupported subtitle format")
