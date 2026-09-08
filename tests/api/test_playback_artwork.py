"""TV episode artwork chain regression tests.

The reported bug: TV episodes had no artwork in the player. The fix has two
halves — (a) local artwork attachment understands the real TV layouts
(poster.jpg in the show root, seasonNN.jpg in the season folder) and
(b) episode artwork falls back generally: episode still -> season poster ->
show poster, in both playable() and the play queue.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.auth import generate_token
from app.api.context import APIContext
from app.api.server import create_app
from app.bootstrap.dependencies import Dependencies
from tests.seedlib import scan_tree, seed_library, seed_media_tree


@pytest.fixture()
def seeded(tmp_path, monkeypatch):
    # underscore in the path is deliberate: it reproduces the escaping bug
    # where the directory-equality probe was fed a LIKE-escaped string
    home = tmp_path / "media_root_100pct"
    home.mkdir()
    monkeypatch.setenv("JMDB_HOME", str(home))
    seed_media_tree(home)
    # real playable bytes so /api/stream can serve
    for pattern in ("Movies/**/*.mkv", "Movies/**/*.mp4", "TV/**/*.mkv", "Music/**/*.mp3"):
        for media in tmp_path.glob(pattern):
            shutil.copy2("/tmp/jmdb-rt/test-vp8.mkv", media)
    ctx = APIContext(Dependencies(), generate_token())
    scan_tree(ctx.services, home)
    keys = seed_library(ctx.services, home)
    app = create_app(context=ctx, token=ctx.token, ui_dir=home / "no-ui")
    client = TestClient(app)
    client.headers.update({"Authorization": f"Bearer {ctx.token}"})
    return ctx, keys, client


def test_local_tv_layout_artwork_attaches(seeded):
    """poster.jpg in the show root and season01.jpg in the season folder must
    attach to the show and season (the standard real-world layouts)."""
    ctx, _keys, _client = seeded
    rows = {
        (r["owner_type"], r["kind"]): r["local_path"]
        for r in ctx.services.repos.db.query(
            "SELECT owner_type, kind, local_path FROM artwork WHERE local_path <> ''"
        )
    }
    assert any(t == ("tv_show", "poster") and "poster.jpg" in p for t, p in rows.items()), rows
    assert any(t == ("season", "season_poster") and "season01.jpg" in p for t, p in rows.items()), rows


def test_episode_playable_artwork_falls_back_to_season_poster(seeded):
    """The seeded episodes have NO stills, so playable() must resolve the
    season poster (then show poster) — the exact reported failure."""
    ctx, keys, _client = seeded
    from app.media.tv import TvCatalog

    item = TvCatalog(ctx.services.repos).playable(keys["episode_id"])
    assert item is not None
    assert item.artwork_path, "episode artwork must not be empty without stills"
    assert "season01.jpg" in item.artwork_path or "poster.jpg" in item.artwork_path


def test_playback_start_carries_episode_artwork_and_queue_art(seeded):
    """/api/playback/start returns media.artwork_path for the episode and
    artwork_path on every queue entry (season episodes, album tracks, or the
    single-item fallback)."""
    ctx, keys, client = seeded
    response = client.post(
        "/api/playback/start",
        json={"media_type": "episode", "media_id": keys["episode_id"]},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["media"]["artwork_path"], data["media"]
    queue = data["queue"]
    assert queue, "season episodes must form a queue"
    for entry in queue:
        assert entry.get("artwork_path"), f"queue entry without artwork: {entry}"


def test_movie_queue_entry_has_artwork(seeded):
    """Single-item queues (movies) carry the playable's artwork too."""
    ctx, keys, client = seeded
    response = client.post(
        "/api/playback/start",
        json={"media_type": "movie", "media_id": keys["movie_id"]},
    )
    assert response.status_code == 200
    entry = response.json()["queue"][0]
    assert entry.get("artwork_path"), entry


def test_playback_start_surfaces_probe_codec_facts(seeded):
    """/api/playback/start must tell the player the REAL codec facts (from
    ffprobe) so it can decide honestly whether the embedded Chromium can
    decode the file (e.g. HEVC without hardware decode) instead of showing
    a silent black screen."""
    import shutil as _shutil

    from app.library.probe import ProbeTools

    ctx, keys, client = seeded
    tools = ProbeTools()
    if not tools.available:
        pytest.skip("no ffprobe/ffmpeg available for probing")

    movie = ctx.services.movies.playable(keys["movie_id"])
    assert movie is not None

    # swap in a REAL 10-bit HEVC file (the user-reported codec class) and
    # probe it for real — no fabricated metadata
    hevc = Path("/tmp/jmdb-rt/test-hevc10.mkv")
    if not hevc.exists():
        pytest.skip("HEVC sample not generated in this environment")
    _shutil.copy2(hevc, movie.path)
    result = tools.probe(movie.path)
    assert result is not None and result.video_codec.lower().startswith("hevc"), (
        f"probe result: {result.to_dict() if result else None}")
    ctx.services.repos.files.set_probe(movie.media_file_id, result.to_dict())

    response = client.post(
        "/api/playback/start",
        json={"media_type": "movie", "media_id": keys["movie_id"]},
    )
    assert response.status_code == 200, response.text
    info = response.json()["media"]["file"]
    assert info["video_codec"].lower().startswith("hevc"), info
    assert info["width"] > 0 and info["height"] > 0, info
    assert isinstance(info["audio_tracks"], list), info


def test_playback_external_launches_configured_player(seeded, monkeypatch):
    """The external-player handoff must really launch a process with the
    media path (tested with /bin/true as the configured player — a real
    subprocess spawn, no fake success)."""
    import shutil as _shutil
    import stat as _stat

    ctx, keys, client = seeded
    true_bin = _shutil.which("true")
    if not true_bin:
        pytest.skip("no /bin/true on this platform")

    ctx.services.settings.set("external_player_path", true_bin)
    try:
        response = client.post(
            "/api/playback/external",
            json={"media_type": "movie", "media_id": keys["movie_id"]},
        )
        assert response.status_code == 200, response.text
        assert response.json().get("launched") is True
    finally:
        ctx.services.settings.set("external_player_path", "")
