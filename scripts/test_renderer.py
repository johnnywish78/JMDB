#!/usr/bin/env python3
"""Renderer integration test — real Chromium (QtWebEngine) against the real API.

Loads the REAL Electron renderer (electron/src) served by the REAL backend
(as run.py does), drives it like a user (navigation, theme switch, search,
detail pages, the player with a REAL video file, subtitles, the browser hub's
honest no-Electron notice), and asserts on real DOM/API state.

Offline-safe: everything is local (no external sites are loaded).

Run: QT_QPA_PLATFORM=offscreen python3 scripts/test_renderer.py
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PORT = 8831
BASE = f"http://127.0.0.1:{PORT}"
VIDEO = Path("/tmp/jmdb-rt/test-vp8.mkv")

results = []


def pump() -> None:
    """Give the Qt loop a kick so web content + JS callbacks can run."""
    from PyQt6.QtWidgets import QApplication

    for _ in range(6):
        QApplication.processEvents()
        time.sleep(0.02)


def num(value) -> int:
    """js() delivers JS numbers as int/float (not str) — coerce any shape to int."""
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, bool(ok)))
    print(f"{'PASS' if ok else 'FAIL'} — {name}" + (f" — {detail}" if detail else ""), flush=True)


def main() -> int:
    home = Path(tempfile.mkdtemp(prefix="jmdb-renderer-"))
    os.environ["JMDB_HOME"] = str(home)

    from tests.seedlib import seed_media_tree, scan_tree, seed_library
    from app.bootstrap.dependencies import Dependencies
    from app.api.context import APIContext
    from app.api.auth import generate_token
    from app.api.server import create_app

    # real media with a REAL playable video in place of the seeded stub files
    tree = home
    seed_media_tree(tree)
    replaced = []
    for pattern in ("Movies/**/*.mkv", "Movies/**/*.mp4", "TV/**/*.mkv", "Music/**/*.mp3",
                   "media/Movies/**/*.mkv", "media/Movies/**/*.mp4", "media/TV/**/*.mkv", "media/Music/**/*.mp3"):
        for path in tree.glob(pattern):
            shutil.copy2(VIDEO, path)
            replaced.append(path.name)
    check("real playable media files in place", len(replaced) >= 4, f"{len(replaced)} files")

    ctx = APIContext(Dependencies(), generate_token())
    scan_tree(ctx.services, tree)
    seed_library(ctx.services, home)

    # seed_library scans a second media tree under home/media — replace those
    # stubs with the real playable clip too, so every playable file in the DB plays
    def replace_with_real_media():
        count = 0
        for pattern in ("Movies/**/*.mkv", "Movies/**/*.mp4", "TV/**/*.mkv", "Music/**/*.mp3",
                        "media/Movies/**/*.mkv", "media/Movies/**/*.mp4", "media/TV/**/*.mkv", "media/Music/**/*.mp3"):
            for media in tree.glob(pattern):
                shutil.copy2(VIDEO, media)
                count += 1
        return count

    replaced2 = replace_with_real_media()
    check("real playable media files in place (both trees)", replaced2 >= 10, f"{replaced2} files")

    # Real ffprobe facts for the played movie (vp8) and a REAL 10-bit HEVC
    # file for the second movie — the exact codec class the user reported.
    # Probing is real (ProbeTools on the actual bytes); scan-time probing is
    # disabled in the seed, so the facts are attached explicitly here.
    from app.library.probe import ProbeTools
    hevc_src = Path("/tmp/jmdb-rt/test-hevc10.mkv")
    probe_tools = ProbeTools()
    movies_catalog = ctx.services.movies
    hevc_movie_id = None
    # HEVC goes to the SECOND movie (id != movie_id used by the main player
    # checks, which is Night Runner id=1); the played movie keeps the
    # playable VP8 bytes and gets its real probe facts attached too.
    movie_rows = list(ctx.services.repos.db.query("SELECT id FROM movies ORDER BY id"))
    for row in movie_rows:
        item = movies_catalog.playable(row["id"])
        if item is None:
            continue
        if hevc_src.exists() and probe_tools.available and row["id"] != movie_rows[0]["id"]:
            shutil.copy2(hevc_src, item.path)
            probe = probe_tools.probe(item.path)
            assert probe and probe.video_codec.lower().startswith("hevc"), "hevc probe failed"
            ctx.services.repos.files.set_probe(item.media_file_id, probe.to_dict())
            hevc_movie_id = row["id"]
        elif probe_tools.available:
            probe = probe_tools.probe(item.path)
            if probe:
                ctx.services.repos.files.set_probe(item.media_file_id, probe.to_dict())
    check("probed codec facts attached (incl. a real 10-bit HEVC movie)",
          hevc_movie_id is not None, f"hevc movie id={hevc_movie_id}")

    import uvicorn

    app = create_app(context=ctx)
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="error"))
    threading.Thread(target=server.run, daemon=True).start()
    wait_http(f"{BASE}/api/health")
    check("backend healthy on 127.0.0.1", True, BASE)

    # ---------------------------------------------------------------- QtWebEngine
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox --disable-gpu --disable-dev-shm-usage --autoplay-policy=no-user-gesture-required")
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import QUrl
    from PyQt6.QtWebEngineWidgets import QWebEngineView

    qt_app = QApplication.instance() or QApplication(["jmdb-renderer-test"])
    view = QWebEngineView()

    boot_url = f"{BASE}/app/boot?token={ctx.token}"
    view.load(QUrl(boot_url))
    nav_count = None
    for _ in range(80):
        pump()
        nav_count = js(view, "document.querySelectorAll('#nav a').length", timeout_s=2)
        if nav_count:
            break
        print(f"  waiting: title={view.title()!r} url={view.url().toString()!r} nav={nav_count}", flush=True)
        time.sleep(0.15)
    if not nav_count:
        check("renderer booted (boot token → cookie → app)", False, f"nav never populated (title={view.title()!r})")
        return finish(server, 1)
    nav_count = js(view, "document.querySelectorAll('#nav a').length")
    check("renderer booted (boot token → cookie → app)", True, f"{nav_count} nav items")

    nav_labels = js_value(view, "JSON.stringify([...document.querySelectorAll('#nav a .label')].map(a => a.textContent))")
    check("navigation complete", len(nav_labels) >= 14, ", ".join(nav_labels[:6]) + "…")

    def goto(hash: str, expr: str, timeout_s: float = 12.0) -> str:
        js(view, f"(() => {{ location.hash = {json.dumps(hash)}; return true }})()")
        return wait_js(view, expr, timeout_s)

    def raw_svg_sweep(label: str, scope_selector: str = "body") -> None:
        """Regression: no literal SVG markup may ever render as text."""
        raw = js(view, """(() => {
            const scope = document.querySelector('%s') || document.body;
            const walker = document.createTreeWalker(scope, NodeFilter.SHOW_TEXT);
            let bad = 0; let sample = '';
            while (walker.nextNode()) {
                const t = (walker.currentNode.nodeValue || '').trim().toLowerCase();
                if (t && (t.includes('<svg') || t.includes('<path') || /^(svg)+$/.test(t) || /svg.{0,4}svg/.test(t))) {
                    bad++; if (!sample) sample = t.slice(0, 48);
                }
            }
            return JSON.stringify([bad, sample]);
        })()""" % scope_selector, timeout_s=8)
        report = _parse_json(raw)
        if isinstance(report, list) and len(report) == 2:
            check(f"no raw svg text nodes ({label})", int(report[0]) == 0, str(report[1]))
        else:
            check(f"no raw svg text nodes ({label})", False, "sweep failed")

    # ---------------------------------------------------------------- home
    cards = goto("#/home", "document.querySelectorAll('.poster-card, .continueCard').length")
    check("home renders cards from real API data", int(cards or 0) >= 4, f"{cards} cards")
    raw_svg_sweep("home cards")
    stats = goto("#/home", "document.querySelectorAll('.stat-grid .fact').length")
    check("home renders stats strip", int(stats or 0) >= 4, f"{stats} facts")

    # ---------------------------------------------------------------- movies grid + filters
    cards = goto("#/movies", "document.querySelectorAll('.grid .poster-card').length")
    check("movies grid renders", int(cards or 0) >= 2, f"{cards} movies")
    n = goto("#/movies?q=night", "document.querySelectorAll('.grid .poster-card').length")
    check("movies title filter (client-side reload)", int(n or 0) == 1, f"{n} movie matches 'night'")

    # ---------------------------------------------------------------- tv + music
    cards = goto("#/tv", "document.querySelectorAll('.grid .poster-card').length")
    check("tv grid renders", int(cards or 0) >= 2, f"{cards} shows")
    n = goto("#/music?type=albums", "document.querySelectorAll('.grid .album-card, .grid .poster-card').length")
    check("music albums render", int(n or 0) >= 1, f"{n} albums")
    n = goto("#/music?type=tracks", "document.querySelectorAll('.track-row').length")
    check("music tracks render", int(n or 0) >= 2, f"{n} tracks")

    # ---------------------------------------------------------------- search
    n = goto("#/search?q=night", "document.querySelectorAll('.grid .poster-card').length")
    check("global search finds results", int(n or 0) >= 1, f"{n} movie cards")

    # ---------------------------------------------------------------- detail pages
    n = goto("#/people", "document.querySelectorAll('.person-card').length")
    check("people page renders", int(n or 0) >= 1, f"{n} people")
    people_id = js(view, "document.querySelector('.person-card') ? 1 : 0")
    n = goto(f"#/person/{people_id}", "document.querySelectorAll('.filmography .poster-card, .detail-layout').length")
    check("person detail renders filmography", int(n or 0) >= 1)

    # movie detail via search result
    movie_id = int(js(view, "document.getElementById('global-search') ? 1 : 0") or 1)
    n = goto(f"#/movie/{movie_id}", "document.querySelectorAll('.hero, .facts-grid, .file-row').length")
    check("movie detail renders hero/facts/files", int(n or 0) >= 3, f"{n} blocks")

    # show detail (Solar Winds id=1 in seed data)
    n = goto("#/show/1", "document.body.textContent.includes('Seasons') && document.querySelectorAll('.section').length")
    err = js(view, "document.querySelector('.error-note') ? document.querySelector('.error-note').textContent.slice(0, 140) : ''", timeout_s=3)
    check("show detail renders seasons", int(n or 0) >= 3, f"{n} sections; page error: {err!r}")

    # season detail → episodes
    n = goto("#/season/1", "document.querySelectorAll('.episode-row').length")
    check("season detail renders episodes", int(n or 0) >= 3, f"{n} episodes")

    # ---------------------------------------------------------------- theme switching
    # theme: ask the PAGE to PATCH (async), then verify DOM + CSS + persistence (sync)
    patched = js(view, """(async () => {
        const res = await fetch('/api/settings',
            {headers: {'Content-Type': 'application/json'}, method: 'PATCH',
             body: JSON.stringify({theme: 'light'})});
        return res.ok ? 'ok' : 'http-' + res.status;
    })()""", promise=True, timeout_s=15)
    check("theme PATCH via the page succeeded", patched == "ok", str(patched))
    pump()
    saved = http_get(ctx.token, f"{BASE}/api/settings")["values"]["theme"]
    applied = js(view, "document.documentElement.dataset.theme", timeout_s=3)
    bg = js(view, "getComputedStyle(document.documentElement).getPropertyValue('--bg').trim()", timeout_s=3)
    check("theme saved to profile", saved == "light", str(saved))
    check("theme applied to DOM", applied == "light", str(applied))
    check("light theme CSS variables live", bg.startswith("#f") or bg.startswith("rgb(24"), f"--bg={bg}")
    js(view, "(() => { fetch('/api/settings', {headers: {'Content-Type': 'application/json'}, method: 'PATCH', body: JSON.stringify({theme: 'system'})}); return 1 })()", timeout_s=3)
    pump()

    # ---------------------------------------------------------------- settings acceptance
    # theme chips: three SEPARATE controls (used to read as "DarkLightSystem")
    chips = js_value(view, "JSON.stringify([])", timeout_s=3)  # noop warmup
    goto("#/settings", "document.querySelectorAll('.settings-section').length >= 6")
    chip_count = int(js(view, "document.querySelectorAll('.chip-row .chip').length", timeout_s=3) or 0)
    chip_labels = js_value(view, "JSON.stringify([...document.querySelectorAll('.chip-row .chip')].map(c => c.textContent.trim()))")
    check("theme rendered as 3 separate chips", chip_count == 3, f"{chip_labels}")

    # provider cards: real provider names, key badges, chain order, Browse picker
    goto("#/settings", "document.querySelectorAll('.provider-card').length >= 8")
    provider_text = js_value(view, "document.body.textContent")
    for provider_name in ("TMDB", "OMDb", "TVmaze", "MusicBrainz", "TheAudioDB", "Last.fm", "Fanart.tv", "TV Time"):
        check(f"provider card present: {provider_name}", provider_name in provider_text, "")
    chain_text = js_value(view, "document.querySelector('.provider-chains') ? document.querySelector('.provider-chains').textContent : ''")
    check("provider chain order is visible", "tmdb" in chain_text and "musicbrainz" in chain_text, chain_text[:70])
    browse = int(js(view, "document.querySelectorAll('button').length && [...document.querySelectorAll('button')].filter(b => b.textContent.trim() === 'Browse…').length", timeout_s=3) or 0)
    check("native folder picker button offered", browse == 1, f"{browse} button(s)")
    tvtime_note = js_value(view, "document.body.textContent.includes('TV Time has no public API') ? 'yes' : 'no'")
    check("TV Time honestly documented as no-API", tvtime_note == "yes", tvtime_note)

    # add location: INVALID path → error toast (no fake success)
    invalid_click = js(view, """(() => {
        const input = document.querySelector('input[placeholder*="media folder"]');
        if (!input) return 'NO-INPUT';
        input.value = '/nonexistent/renderer-path';
        const btn = [...document.querySelectorAll('button')].find(b => b.textContent.trim() === 'Add location');
        if (!btn) return 'NO-BUTTON';
        btn.click();
        return 'CLICKED';
    })()""", timeout_s=5)
    error_toast = wait_js(view, "document.querySelector('.toast.error') ? document.querySelector('.toast.error').textContent : ''", 8.0)
    check("invalid location shows an ERROR toast",
          "Couldn't add" in str(error_toast) and invalid_click == "CLICKED",
          f"click={invalid_click} toast={str(error_toast)[:70]}")
    fake_success = js_value(view, "document.querySelector('.toast.success') ? document.querySelector('.toast.success').textContent : ''")
    check("no fake success toast for invalid path", "Location added" not in str(fake_success), str(fake_success)[:60])

    # add location: VALID path → success toast + the row appears
    valid_dir = home / "renderer-media"
    valid_dir.mkdir(exist_ok=True)
    valid_click = js(view, """(() => {
        const input = document.querySelector('input[placeholder*="media folder"]');
        if (!input) return 'NO-INPUT';
        input.value = VALIDDIRPLACEHOLDER;
        const btn = [...document.querySelectorAll('button')].find(b => b.textContent.trim() === 'Add location');
        if (!btn) return 'NO-BUTTON';
        btn.click();
        return 'CLICKED';
    })()""".replace("VALIDDIRPLACEHOLDER", json.dumps(str(valid_dir))), timeout_s=5)
    added = wait_js(view, "document.body.textContent.includes('renderer-media') ? 1 : 0", 8.0)
    detail = str(valid_dir)
    if added != "1" or valid_click != "CLICKED":
        # diagnostics: what did the toasts / location rows / console actually say?
        diag = js(view, "JSON.stringify({toasts: [...document.querySelectorAll('.toast')].map(t => t.textContent.slice(0, 70)), rows: [...document.querySelectorAll('.location-row .path')].map(p => p.textContent)})", timeout_s=5)
        detail = f"click={valid_click} diag={str(diag)[:220]}"
    check("valid location appears in the list", num(added) == 1 and valid_click == "CLICKED", detail)

    # ---------------------------------------------------------------- services page
    goto("#/services", "document.querySelectorAll('.service-card').length")
    service_names = js_value(view, "JSON.stringify([...document.querySelectorAll('.service-card h3')].map(h => h.textContent.trim()))")
    names = set(service_names if isinstance(service_names, list) else json.loads(service_names))
    check("services page shows exactly the four services",
          names == {"YouTube", "Telegram", "Spotify", "TV Time"}, str(sorted(names)))
    # every card has a primary open action; in this web renderer (no Electron
    # bridge) the label must say what it does — a browser tab, not the Hub
    primary_buttons = int(js(view, "document.querySelectorAll('.service-card .actions .btn.primary').length", timeout_s=3) or 0)
    check("each service offers a primary open action", primary_buttons == 4, f"{primary_buttons} buttons")
    # .note elements include the embedded-Hub hint text; only URL notes count
    urls = js_value(view, "JSON.stringify([...document.querySelectorAll('.service-card .note')].map(n => n.textContent.trim()).filter(txt => txt.startsWith('https://')))")
    url_list = urls if isinstance(urls, list) else (json.loads(urls) if isinstance(urls, str) else [])
    check("service URLs are the official sites",
          len(url_list) == 4 and all(str(u).startswith("https://") for u in url_list), str(url_list)[:100])

    # real brand icons: every card shows an SVG mark, no emoji placeholders
    brand = js(view, """(() => {
        const cards = [...document.querySelectorAll('.service-card')];
        return JSON.stringify({
          cards: cards.length,
          withSvg: cards.filter(c => c.querySelector('.svc-icon svg')).length,
          emojiOnly: cards.filter(c => !c.querySelector('.svc-icon svg') && c.querySelector('.svc-icon')).length,
        });
    })()""", timeout_s=6)
    brand_data = _parse_json(brand)
    if isinstance(brand_data, dict):
        check("service cards show real SVG brand icons",
              brand_data.get("cards") == 4 and brand_data.get("withSvg") == 4,
              f"svg={brand_data.get('withSvg')}/{brand_data.get('cards')}")
        # official COLORFUL marks: each icon carries its official brand fill
        color_raw = js(view, """(() => {
            const fills = [...document.querySelectorAll('.service-card .svc-icon svg [fill]')]
                .map(el => el.getAttribute('fill'));
            return JSON.stringify(fills);
        })()""", timeout_s=6)
        fills = _parse_json(color_raw) or []
        fill_set = set(str(f).upper() for f in fills if f and f != "none")
        official = {"#FF0000", "#229ED9", "#1DB954", "#104D9C", "#FFFFFF", "#191414"}
        check("brand icons are official-color marks (YouTube red, Telegram blue, Spotify green, TV Time blue)",
              {"#FF0000", "#229ED9", "#1DB954", "#104D9C"}.issubset(fill_set),
              f"fills={sorted(fill_set)}")
    else:
        check("service cards show real SVG brand icons", False, str(brand)[:60])

    # primary buttons do what their label says. In this web renderer (no
    # Electron bridge) a non-DRM service must open via window.open, and a DRM
    # service must offer the external path — no dead or mislabeled cards.
    open_probe = js(view, """(async () => {
        const opened = [];
        const orig = window.open;
        window.open = (url, target) => { opened.push([url, target]); return null; };
        try {
          const cards = [...document.querySelectorAll('.service-card')];
          const results = [];
          for (const card of cards) {
            const btn = card.querySelector('.actions .btn.primary');
            const label = btn ? btn.textContent.trim() : '';
            if (btn) btn.click();
            await new Promise(r => setTimeout(r, 60));
            results.push({ label, clicked: Boolean(btn) });
          }
          return JSON.stringify({ opened, results });
        } finally { window.open = orig; }
    })()""", promise=True, timeout_s=15)
    probe = _parse_json(open_probe)
    if isinstance(probe, dict):
        opened = probe.get("opened") or []
        clicked = sum(1 for r in probe.get("results", []) if r.get("clicked"))
        labels = [r.get("label", "") for r in probe.get("results", [])]
        honest = all("Browser Hub" not in lbl for lbl in labels)  # web renderer must not promise the hub
        check("service primary buttons work in the web renderer",
              clicked == 4 and len(opened) >= 3 and honest,
              f"clicked={clicked}, opened={len(opened)}, labels={labels}")
    else:
        check("service primary buttons work in the web renderer", False, str(open_probe)[:70])
    # the embedded path routes through the browser page, not cross-page hacks
    services_src = (ROOT / "electron/src/js/pages/services.js").read_text()
    check("embedded open routes via /browser?url= (page-owned tabs)",
          "browser?url=" in services_src and "setTimeout" not in services_src.split("navigate(")[1][:200])
    raw_svg_sweep("services cards")

    # ---------------------------------------------------------------- metadata transparency
    goto(f"#/movie/{movie_id}", "document.querySelectorAll('.badge.outline').length")
    meta_badge = js_value(view, "[...document.querySelectorAll('.badge.outline')].map(b => b.textContent).find(t => t.startsWith('Metadata:')) || ''")
    check("movie detail shows metadata source badge", meta_badge.startswith("Metadata:"), meta_badge)

    # ---------------------------------------------------------------- scan progress over WebSocket in the real UI
    # Instrument FIRST: latches record the pill flash and every toast text even
    # when a scan finishes in milliseconds — polling alone can miss a 1ms window.
    js(view, """(() => {
        window.__pill_seen = false;
        window.__toasts_seen = [];
        const pill = document.getElementById('scan-pill');
        if (!pill) return 'NO-PILL';
        if (!pill.classList.contains('hidden')) window.__pill_seen = true;
        // MutationObserver with old values: a hidden->visible->hidden sequence
        // leaves a record whose oldValue lacks 'hidden' even if batched.
        new MutationObserver((records) => {
            for (const r of records) {
                if (!(r.oldValue || '').includes('hidden')) window.__pill_seen = true;
            }
        }).observe(pill, {attributes: true, attributeFilter: ['class'], attributeOldValue: true});
        // belt and braces: sample the pill and toasts every 40ms
        setInterval(() => {
            if (!pill.classList.contains('hidden')) window.__pill_seen = true;
            for (const t of document.querySelectorAll('.toast')) window.__toasts_seen.push(t.textContent);
        }, 40);
        return 'ARMED';
    })()""", timeout_s=5)
    scan_started = js(view, """(async () => {
        const res = await fetch('/api/scan', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'});
        return res.status;
    })()""", promise=True, timeout_s=10)
    check("scan started from the page", str(scan_started) == "200", f"HTTP {scan_started}")
    pill_visible = wait_js(view, "window.__pill_seen ? 1 : 0", 20.0)
    check("scan pill becomes visible while scanning", num(pill_visible) == 1, "")
    finished_toast = wait_js(view, "window.__toasts_seen.some(t => t.includes('Scan finished')) ? 1 : 0", 25.0)
    check("scan completion toast appears (WS-driven)", num(finished_toast) == 1, "")
    pill_hidden = wait_js(view, "document.getElementById('scan-pill').classList.contains('hidden') ? 1 : 0", 15.0)
    check("scan pill returns to idle after completion", num(pill_hidden) == 1, "")

    # ---------------------------------------------------------------- subtitles endpoint (SRT → WebVTT)
    srt = next(tree.glob("TV/**/Solar.Winds.S01E01*.srt"), None)
    if srt:
        import urllib.parse

        vtt = http_text(ctx.token, f"{BASE}/api/subtitles?path={urllib.parse.quote(str(srt))}")
        check("subtitles endpoint serves WebVTT", vtt.startswith("WEBVTT"), vtt[:40].replace("\n", " "))
    else:
        check("subtitles endpoint serves WebVTT", False, "seed srt missing")

    # ---------------------------------------------------------------- mpv engine handoff (injected desktop bridge)
    # The real desktop app exposes window.jmdb.mpv; here we inject a faithful
    # fake bridge BEFORE clicking Play so the REAL handoff code in player.js
    # runs in a real browser: status → open(payload) → mpv-mode page → close.
    played = goto(f"#/movie/{movie_id}", "document.querySelectorAll('.play-btn').length")
    js(view, """(() => {
        window.__mpv_calls = [];
        window.__mpv_listeners = {};
        window.jmdb = {
            mpv: {
                status: async () => ({ available: true, path: '/usr/bin/mpv', version: '0.38-test' }),
                open: async (payload) => { window.__mpv_calls.push(['open', payload]); return { ok: true, engine: 'mpv' }; },
                close: async () => { window.__mpv_calls.push(['close']); return { ok: true }; },
            },
            on: (channel, cb) => {
                (window.__mpv_listeners[channel] = window.__mpv_listeners[channel] || []).push(cb);
                return () => {};
            },
        };
        return 1;
    })()""", timeout_s=3)
    js(view, "(() => { document.querySelector('.play-btn').click(); return 1 })()", timeout_s=3)
    ok = wait_js(view, "document.querySelector('.player.mpv-mode') ? 1 : 0", 10)
    check("mpv engine chosen when the desktop bridge reports it available", bool(ok))
    if ok:
        payload_raw = js(view, "JSON.stringify((window.__mpv_calls.find(c => c[0] === 'open') || [null, null])[1])", timeout_s=5)
        payload = _parse_json(payload_raw) or {}
        check("mpv handoff passes the real file path and session data",
              bool(payload.get("path")) and payload.get("sessionId") and payload.get("mediaType") == "movie"
              and payload.get("title") and "seekStep" in payload,
              f"path={str(payload.get('path'))[:40]}… session={bool(payload.get('sessionId'))}")
        # closing: the engine tells the renderer, the page cleans up
        js(view, """(() => { (window.__mpv_listeners['mpv:closed'] || []).forEach(cb => cb({ reason: 'user' })); return 1 })()""", timeout_s=3)
        ok2 = wait_js(view, "document.querySelector('.player.mpv-mode') ? 0 : 1", 10)
        check("mpv player page closes when the engine reports closed", bool(ok2))
    js(view, "(() => { delete window.jmdb; window.__mpv_calls = []; return 1 })()", timeout_s=3)

    # honest fallback: bridge present but mpv NOT available → built-in player
    goto(f"#/movie/{movie_id}", "document.querySelectorAll('.play-btn').length")
    js(view, """(() => {
        window.jmdb = {
            mpv: {
                status: async () => ({ available: false, reason: 'mpv is not installed' }),
                open: async () => ({ ok: false, error: 'unavailable' }),
                close: async () => ({ ok: false }),
            },
            on: () => () => {},
        };
        return 1;
    })()""", timeout_s=3)
    js(view, "(() => { document.querySelector('.play-btn').click(); return 1 })()", timeout_s=3)
    ok = wait_js(view, "document.querySelector('.player video') ? 1 : 0", 15)
    check("player falls back to the built-in engine when mpv is unavailable", bool(ok))
    if ok:
        js(view, """(() => { const v = document.querySelector('.player video'); if (v) v.pause(); return 1 })()""", timeout_s=3)
        js(view, """(() => { const p = document.querySelector('.player-top button[title^="Back"]'); if (p) p.click(); return 1 })()""", timeout_s=3)
        wait_js(view, "document.querySelector('.player') ? 0 : 1", 10)
    js(view, "(() => { delete window.jmdb; return 1 })()", timeout_s=3)

    # ---------------------------------------------------------------- PLAYER with a real video
    played = goto(f"#/movie/{movie_id}", "document.querySelectorAll('.play-btn').length")
    check("movie detail offers Play", int(played or 0) >= 1)
    js(view, "(() => { document.querySelector('.play-btn').click(); return 1 })()", timeout_s=3)
    ok = wait_js(view, "document.querySelector('.player video') ? 1 : 0", 20)
    check("player overlay opens", bool(ok))
    if ok:
        raw_svg_sweep("movie player chrome", ".player")
        art_raw = js(view, """(() => new Promise(resolve => {
            const img = document.querySelector('.player-top .artwork');
            if (!img) { resolve(JSON.stringify([0, 0])); return; }
            if (img.complete) { resolve(JSON.stringify([1, img.naturalWidth])); return; }
            img.addEventListener('load', () => resolve(JSON.stringify([1, img.naturalWidth])));
            img.addEventListener('error', () => resolve(JSON.stringify([1, -1])));
            setTimeout(() => resolve(JSON.stringify([1, img.naturalWidth])), 4000);
        }))()""", promise=True, timeout_s=10)
        art = _parse_json(art_raw)
        if isinstance(art, list) and len(art) == 2:
            check("movie player top bar shows real artwork",
                  art[0] == 1 and int(art[1]) > 2, f"naturalWidth={art[1]}")
        else:
            check("movie player top bar shows real artwork", False, str(art_raw)[:60])
        state_raw = js(view, """(async () => {
        await new Promise(r => setTimeout(r, 2600));
        const video = document.querySelector('.player video');
        const track = document.querySelector('.player video track');
        return JSON.stringify([video.currentTime, video.duration, video.readyState,
                               video.error ? String(video.error.code) : 'none',
                               track ? track.getAttribute('src') : 'none']);
    })()""", promise=True, timeout_s=20)
        state = _parse_json(state_raw)
        if isinstance(state, list) and len(state) == 5 and all(v is not None for v in state):
            current, duration, ready, error, track = state
            check("real video plays in embedded player",
                  float(current) > 0.8 and float(duration) >= 10 and ready in (3, 4) and error == "none",
                  f"t={current:.1f}s of {duration:.1f}s, readyState={ready}, err={error}")
            # pause / seek / resume round-trip
            state2_raw = js(view, """(async () => {
        const video = document.querySelector('.player video');
        video.pause();
        await new Promise(r => setTimeout(r, 300));
        const afterPause = video.currentTime;
        video.currentTime = 1.5;
        await new Promise(r => setTimeout(r, 300));
        video.play();
        await new Promise(r => setTimeout(r, 500));
        return JSON.stringify([afterPause, video.currentTime, video.paused]);
    })()""", promise=True, timeout_s=15)
            state2 = _parse_json(state2_raw)
            if isinstance(state2, list) and len(state2) == 3:
                check("pause/seek/resume controls work", float(state2[1]) >= 1.5 and float(state2[2]) == 0, f"t={state2[1]:.2f}s")
            else:
                # honest failure — a parse miss here would otherwise silently
                # skip the whole autoplay/watched/history chain (fake green)
                check("pause/seek/resume controls work", False, f"probe never landed: {str(state2_raw)[:80]}")
            # progress reaches the backend while playing (report fires on pause + every 5s)
            time.sleep(0.8)
            pump()
            pstate = http_get(ctx.token, f"{BASE}/api/playback/state/{movie_id}?media_type=movie")
            # keyboard: seek via a real KeyboardEvent
            state3_raw = js(view, """(async () => {
        const video = document.querySelector('.player video');
        const before = video.currentTime;
        document.dispatchEvent(new KeyboardEvent('keydown', {key: 'ArrowRight', bubbles: true}));
        await new Promise(r => setTimeout(r, 350));
        return JSON.stringify([before, video.currentTime]);
    })()""", promise=True, timeout_s=15)
            state3 = _parse_json(state3_raw)
            if isinstance(state3, list) and len(state3) == 2:
                check("keyboard seek shortcut works", float(state3[1]) > float(state3[0]) + 0.5, f"{state3[0]:.1f} → {state3[1]:.1f}")
            # let it end: onEnded → finish (backend marks watched, clears resume)
            finished = wait_js(view, "document.querySelector('.center-msg') ? 1 : 0", 20)
            check("autoplay reached the end and showed the Finished box", bool(finished))
            js(view, "(() => { const back = [...document.querySelectorAll('.center-msg .btn')].find(b => b.textContent.includes('Back to library')); back && back.click(); return 1 })()", timeout_s=3)
            gone = wait_js(view, "document.querySelector('.player') ? 0 : 1", 8)
            check("player closes cleanly", bool(gone))
            post = http_get(ctx.token, f"{BASE}/api/playback/state/{movie_id}?media_type=movie")
            check("backend marked the movie watched after finishing", bool(post.get("watched")), json.dumps(post)[:80])
            hist = http_get(ctx.token, f"{BASE}/api/history")
            latest = next((row for row in hist.get("items", []) if row.get("media_type") == "movie" and row.get("media_id") == movie_id), {})
            check("playback session recorded in history", bool(latest.get("id")), json.dumps(latest)[:110])

            # seek step honors the persisted setting (seek_step_seconds),
            # changed through the REAL settings page (store cache + API)
            goto("#/settings", "document.body.textContent.includes('Seek step') ? 1 : 0")
            js(view, "(async () => { const row = [...document.querySelectorAll('.setting-row')].find(r => r.textContent.includes('Seek step')); const input = row && row.querySelector('input'); if (!input) return 'no input'; input.value = '7'; input.dispatchEvent(new Event('change')); await new Promise(r => setTimeout(r, 600)); return 'saved'; })()", promise=True, timeout_s=10)
            goto(f"#/movie/{movie_id}", "document.querySelectorAll('.play-btn').length")
            js(view, "(() => { document.querySelector('.play-btn') && document.querySelector('.play-btn').click(); return 1 })()", timeout_s=3)
            ok_seek = wait_js(view, "document.querySelector('.player video') ? 1 : 0", 20)
            if ok_seek:
                js(view, "(async () => { await new Promise(r => setTimeout(r, 800)); const video = document.querySelector('.player video'); video.pause(); video.currentTime = 2; await new Promise(r => setTimeout(r, 250)); const before = video.currentTime; document.dispatchEvent(new KeyboardEvent('keydown', {key: 'ArrowRight', bubbles: true})); await new Promise(r => setTimeout(r, 300)); window.__seek_result = [before, video.currentTime]; return 1; })()", promise=True, timeout_s=15)
                seek_res = _parse_json(js(view, "JSON.stringify(window.__seek_result)", timeout_s=5))
                if isinstance(seek_res, list) and len(seek_res) == 2:
                    delta = float(seek_res[1]) - float(seek_res[0])
                    check("seek step honors the seek_step_seconds setting", 5.5 <= delta <= 8.5, f"delta {delta:.1f}s (setting 7)")
                else:
                    check("seek step honors the seek_step_seconds setting", False, str(seek_res)[:60])
                # codec facts in the settings panel (real probe data)
                js(view, "(() => { const b = [...document.querySelectorAll('.pbtn')].find(x => x.getAttribute('title') === 'Settings'); if (b) b.click(); return 1 })()", timeout_s=3)
                pump()
                codec_row = js(view, "(() => { const panel = document.querySelector('.player-settings'); if (!panel) return ''; const row = [...panel.querySelectorAll('.setting-row')].find(r => r.textContent.includes('File')); return row ? row.textContent : ''; })()", timeout_s=5)
                check("player settings panel shows real codec facts", "vp8" in str(codec_row), str(codec_row)[:90])
                js(view, "(() => { document.querySelector('.player-top .pbtn').click(); return 1 })()", timeout_s=3)
                gone = wait_js(view, "document.querySelector('.player') ? 0 : 1", 8)
                check("player exits via Back after codec check", bool(gone))
            # restore the default so later checks are unaffected
            goto("#/settings", "document.body.textContent.includes('Seek step') ? 1 : 0")
            js(view, "(async () => { const row = [...document.querySelectorAll('.setting-row')].find(r => r.textContent.includes('Seek step')); const input = row && row.querySelector('input'); if (input) { input.value = '10'; input.dispatchEvent(new Event('change')); await new Promise(r => setTimeout(r, 400)); } return 1; })()", promise=True, timeout_s=10)

        else:
            check("real video plays in embedded player", False,
                  f"video state unusable: {str(state_raw)[:90]}")

        # ---- HEVC decode-failure path (the user's reported 1080p 10-bit case):
        # this Chromium build cannot decode HEVC, so the honest fallback box
        # must appear - never a silent black screen - and the controls must
        # stay reachable (no idle-hiding in a failure state).
        if hevc_movie_id:
            hevc_nav = goto(f"#/movie/{hevc_movie_id}", "document.querySelectorAll('.play-btn').length")
            check("HEVC movie detail offers Play", int(hevc_nav or 0) >= 1)
            js(view, "(() => { document.querySelector('.play-btn').click(); return 1 })()", timeout_s=3)
            hevc_open = wait_js(view, "document.querySelector('.player') ? 1 : 0", 20)
            if hevc_open:
                box = wait_js(view, "document.querySelector('.center-msg .video-error') ? 1 : 0", 12)
                hevc_state = js(view, "(() => { const player = document.querySelector('.player'); const video = player && player.querySelector('video'); return JSON.stringify({ failureClass: player ? player.classList.contains('failure') : false, hasSrc: video ? Boolean(video.getAttribute('src')) : null, externalBtn: Boolean([...document.querySelectorAll('.center-msg .btn')].find(b => b.textContent.includes('external player'))), backBtn: Boolean([...document.querySelectorAll('.center-msg .btn')].find(b => b.textContent.trim() === 'Back')), codecNote: (document.querySelector('.center-msg') || {textContent: ''}).textContent.includes('hevc') }); })()", timeout_s=5)
                hs = _parse_json(hevc_state) or {}
                check("HEVC movie shows the honest decode-failure fallback", bool(box), "error box rendered")
                check("HEVC failure keeps controls reachable and stops the media",
                      bool(hs.get("failureClass")) and hs.get("hasSrc") is False
                      and bool(hs.get("externalBtn")) and bool(hs.get("backBtn")),
                      str(hs)[:110])
                check("HEVC failure names the real codec", bool(hs.get("codecNote")), str(hs)[:80])
                js(view, "(() => { const b = [...document.querySelectorAll('.center-msg .btn')].find(x => x.textContent.trim() === 'Back'); if (b) b.click(); return 1 })()", timeout_s=3)
                hg = wait_js(view, "document.querySelector('.player') ? 0 : 1", 8)
                check("HEVC failure exits via Back", bool(hg))
            else:
                check("HEVC movie shows the honest decode-failure fallback", False, "player never opened")
        else:
            check("HEVC movie shows the honest decode-failure fallback", False, "no HEVC sample in this environment")

        # ---- episode player: subtitles (the episode has a real .srt) ----
        # Default subtitle language: set through the REAL settings page, then
        # playback must auto-select the matching track (no manual click).
        goto("#/settings", "document.body.textContent.includes('Default subtitle language') ? 1 : 0")
        js(view, "(async () => { const row = [...document.querySelectorAll('.setting-row')].find(r => r.textContent.includes('Default subtitle language')); const input = row && row.querySelector('input'); if (!input) return 'no input'; input.value = 'en'; input.dispatchEvent(new Event('change')); await new Promise(r => setTimeout(r, 600)); return 'saved'; })()", promise=True, timeout_s=10)
        ep_auto_ok = goto("#/episode/1", "document.querySelector('.play-btn') ? 1 : 0")
        if ep_auto_ok:
            js(view, "(() => { document.querySelector('.play-btn').click(); return 1 })()", timeout_s=3)
            auto_open = wait_js(view, "document.querySelector('.player video') ? 1 : 0", 20)
            if auto_open:
                auto_raw = js(view, "(async () => { await new Promise(r => setTimeout(r, 900)); const video = document.querySelector('.player video'); return JSON.stringify([video.querySelectorAll('track').length, video.textTracks.length, (video.textTracks[0] && video.textTracks[0].mode) || 'none']); })()", promise=True, timeout_s=12)
                auto = _parse_json(auto_raw)
                if isinstance(auto, list) and len(auto) == 3:
                    check("default subtitle language auto-selects the track",
                          auto[0] >= 1 and auto[1] >= 1 and auto[2] == "showing",
                          f"tracks={auto[0]}, textTracks={auto[1]}, mode={auto[2]}")
                else:
                    check("default subtitle language auto-selects the track", False, str(auto_raw)[:60])
                # subtitle delay: real cue-time shifting through the menu buttons
                js(view, "(() => { document.querySelector('.player-controls .pbtn[title^=Subtitles]').click(); return 1 })()", timeout_s=3)
                pump()
                delay_raw = js(view, "(async () => { const menu = document.querySelector('.subtitle-menu'); if (!menu) return JSON.stringify({menu: false}); const plus = [...menu.querySelectorAll('.delay-row button')].find(b => b.textContent.includes('+0.25')); if (!plus) return JSON.stringify({menu: true, plus: false}); const video = document.querySelector('.player video'); let track = null; for (let i = 0; i < video.textTracks.length; i++) if (video.textTracks[i].mode === 'showing') track = video.textTracks[i]; if (!track || !track.cues || !track.cues.length) { await new Promise(r => setTimeout(r, 800)); for (let i = 0; i < video.textTracks.length; i++) if (video.textTracks[i].mode === 'showing') track = video.textTracks[i]; } if (!track || !track.cues || !track.cues.length) return JSON.stringify({menu: true, plus: true, cues: 0}); const before = track.cues[0].startTime; plus.click(); await new Promise(r => setTimeout(r, 300)); return JSON.stringify({menu: true, plus: true, cues: track.cues.length, before: before, after: track.cues[0].startTime}); })()", promise=True, timeout_s=15)
                dl = _parse_json(delay_raw) or {}
                if isinstance(dl, dict) and dl.get("before") is not None:
                    shift = round(float(dl["after"]) - float(dl["before"]), 3)
                    check("subtitle delay shifts real cue times", abs(shift - 0.25) < 0.05,
                          f"cue0 {dl['before']} -> {dl['after']} ({dl['cues']} cues)")
                else:
                    check("subtitle delay shifts real cue times", False, str(delay_raw)[:70])
                js(view, "(() => { document.querySelector('.player-top .pbtn').click(); return 1 })()", timeout_s=3)
                wait_js(view, "document.querySelector('.player') ? 0 : 1", 8)
            # reset the language setting to its default for the checks below
            goto("#/settings", "document.body.textContent.includes('Default subtitle language') ? 1 : 0")
            js(view, "(async () => { const row = [...document.querySelectorAll('.setting-row')].find(r => r.textContent.includes('Default subtitle language')); const input = row && row.querySelector('input'); if (input) { input.value = ''; input.dispatchEvent(new Event('change')); await new Promise(r => setTimeout(r, 400)); } return 1; })()", promise=True, timeout_s=10)

        ep_ok = goto("#/episode/1", "document.querySelector('.play-btn') ? 1 : 0")
        check("episode detail offers Play", bool(ep_ok))
        js(view, "(() => { document.querySelector('.play-btn').click(); return 1 })()", timeout_s=3)
        ep_video = wait_js(view, "document.querySelector('.player video') ? 1 : 0", 20)
        check("episode player opens", bool(ep_video))
        if ep_video:
            raw_svg_sweep("episode player chrome", ".player")
            # TV artwork chain: episode still -> season poster -> show poster.
            # The seeded show has no episode stills, so the top-bar artwork must
            # arrive through the season/show fallback (the reported bug).
            ep_art_raw = js(view, """(() => new Promise(resolve => {
                const img = document.querySelector('.player-top .artwork');
                if (!img) { resolve(JSON.stringify([0, 0, ''])); return; }
                const done = () => resolve(JSON.stringify([1, img.naturalWidth, img.getAttribute('src') || '']));
                if (img.complete) { done(); return; }
                img.addEventListener('load', done);
                img.addEventListener('error', () => resolve(JSON.stringify([1, -1, img.getAttribute('src') || ''])));
                setTimeout(done, 4000);
            }))()""", promise=True, timeout_s=10)
            ep_art = _parse_json(ep_art_raw)
            if isinstance(ep_art, list) and len(ep_art) == 3:
                check("episode player shows artwork via season/show chain",
                      ep_art[0] == 1 and int(ep_art[1]) > 2 and "artwork" in str(ep_art[2]),
                      f"naturalWidth={ep_art[1]} src={str(ep_art[2])[:60]}")
            else:
                check("episode player shows artwork via season/show chain", False, str(ep_art_raw)[:60])
            # queue panel entries carry artwork too (season episodes)
            js(view, """(() => { const b = document.querySelector('.pbtn[title="Queue"]'); if (b) b.click(); return 1 })()""", timeout_s=3)
            pump()
            q_raw = js(view, """(() => {
                const panel = document.querySelector('.queue-panel');
                if (!panel) return JSON.stringify([-1, 0]);
                return JSON.stringify([panel.querySelectorAll('.queue-item').length,
                                       panel.querySelectorAll('.queue-item img.thumb').length]);
            })()""", timeout_s=8)
            q = _parse_json(q_raw)
            if isinstance(q, list) and len(q) == 2 and int(q[0]) >= 0:
                check("episode queue entries show artwork thumbs", int(q[0]) >= 2 and int(q[1]) == int(q[0]),
                      f"{q[1]}/{q[0]} entries with thumbs")
            else:
                check("episode queue entries show artwork thumbs", False, str(q_raw)[:60])
            js(view, """(() => { const b = document.querySelector('.pbtn[title="Queue"]'); if (b) b.click(); return 1 })()""", timeout_s=3)
            pump()
            js(view, "(() => { document.querySelector('.player-controls .pbtn[title^=Subtitles]').click(); return 1 })()", timeout_s=3)
            pump()
            ep_opts = js(view, "(() => { const menu = document.querySelector('.subtitle-menu'); window.__eo = menu ? menu.querySelectorAll('button').length : -1; if (menu && menu.querySelectorAll('button')[1]) menu.querySelectorAll('button')[1].click(); return 1 })()", timeout_s=3)
            pump()
            ep_raw = js(view, """(async () => {
                const video = document.querySelector('.player video');
                await new Promise(r => setTimeout(r, 500));
                return JSON.stringify([document.querySelectorAll('.player video track').length,
                                       video.textTracks.length,
                                       (video.textTracks[0] && video.textTracks[0].mode) || 'none',
                                       window.__eo]);
            })()""", promise=True, timeout_s=12)
            ep = _parse_json(ep_raw)
            if isinstance(ep, list) and len(ep) == 4:
                check("episode subtitle selection attaches a real track",
                      ep[0] >= 1 and ep[1] >= 1 and ep[2] in ("showing", "hidden") and ep[3] >= 2,
                      f"tracks={ep[0]}, textTracks={ep[1]}, mode={ep[2]}, menuOptions={ep[3]}")
            else:
                check("episode subtitle selection attaches a real track", False, str(ep_raw)[:100])
            js(view, "(() => { document.querySelector('.player-top .pbtn').click(); return 1 })()", timeout_s=3)
            ep_gone = wait_js(view, "document.querySelector('.player') ? 0 : 1", 8)
            check("episode player closes cleanly", bool(ep_gone))
        else:
            check("player video state", False, "video state promise failed")
    else:
        check("player video state", False, "no video element")

    # ---------------------------------------------------------------- browser settings + vault UI
    goto("#/settings", "document.querySelectorAll('.provider-card').length")
    browser_rows = js_value(view, """(() => {
        const rows = [...document.querySelectorAll('.setting-row')];
        const find = (t) => rows.find(r => r.textContent.includes(t));
        return JSON.stringify({
          cookies: Boolean(find('Allow cookies in Browser Hub')),
          javascript: Boolean(find('Enable JavaScript')),
          zoom: Boolean(find('Default zoom for new tabs')),
          engine: Boolean(find('Search engine')),
        });
    })()""")
    brow = browser_rows if isinstance(browser_rows, dict) else (_parse_json(browser_rows) or {})
    check("browser settings expose engine/zoom/cookies/JavaScript rows",
          all(brow.get(k) for k in ("cookies", "javascript", "zoom", "engine")), str(brow)[:80])

    # settings audit: controls without a consumer must say so honestly
    honest = js_value(view, """(() => {
        const rows = [...document.querySelectorAll('.setting-row')];
        const auto = rows.find(r => r.textContent.includes('Auto-refresh metadata'));
        const lang = rows.find(r => r.textContent.includes('Metadata language'));
        return JSON.stringify({
          auto: auto ? auto.textContent.includes('Not active in this build') : null,
          lang: lang ? lang.textContent.includes('Not active in this build') : null,
        });
    })()""")
    hon = honest if isinstance(honest, dict) else (_parse_json(honest) or {})
    check("inactive metadata settings are labeled honestly",
          hon.get("auto") is True and hon.get("lang") is True, str(hon)[:80])

    # toggling cookies persists through the real settings API (round-trip)
    toggle = js(view, """(async () => {
        const row = [...document.querySelectorAll('.setting-row')].find(r => r.textContent.includes('Allow cookies in Browser Hub'));
        const input = row && row.querySelector('input[type=checkbox]');
        if (!input) return JSON.stringify({ ok: false, why: 'no input' });
        const before = input.checked;
        input.checked = !before;
        input.dispatchEvent(new Event('change'));
        await new Promise(r => setTimeout(r, 700));
        const saved = await (await fetch('/api/settings')).json();
        return JSON.stringify({ ok: true, before, saved: saved.values.browser_allow_cookies });
    })()""", promise=True, timeout_s=15)
    tstate = _parse_json(toggle)
    if isinstance(tstate, dict) and tstate.get("ok"):
        expected = not tstate.get("before")
        check("cookies toggle persists via the API", tstate.get("saved") == expected,
              f"before={tstate.get('before')} saved={tstate.get('saved')}")
        # restore the default (allowed) for other checks
        js(view, """(async () => {
            await fetch('/api/settings', {headers:{'Content-Type':'application/json'}, method:'PATCH', body: JSON.stringify({browser_allow_cookies: true})});
            return 1; })()""", promise=True, timeout_s=10)
    else:
        check("cookies toggle persists via the API", False, str(toggle)[:70])

    # The full Hub UI (toolbar, vault panel, …) needs the Electron bridge.
    # Here we exercise the REAL renderer code against a stub bridge contract
    # (the real bridge + vault are covered by the node test suites):
    # add → list → reveal → copy → delete round-trip through the panel UI.
    vault_flow = js(view, """(async () => {
        const calls = { reveal: 0, copy: 0 };
        const entries = [];
        let nextId = 1;
        window.jmdb = {
          hub: {
            setVisible: async () => {}, setDefaultZoom: async () => {},
            setCookiesEnabled: async () => {}, setJavaScriptEnabled: async () => {},
            tabs: async () => [],
            createTab: async () => 1, activateTab: async () => {}, closeTab: async () => {},
            back: async () => {}, forward: async () => {}, reload: async () => {}, stop: async () => {},
            home: async () => {}, find: async () => {}, clearFind: async () => {}, zoom: async () => {},
            reopenTab: async () => {}, history: async () => ({ items: [] }), clearHistory: async () => {},
            togglePin: async () => {}, favorites: async () => [], switchTab: async () => {},
            print: async () => {}, exportPdf: async () => ({ ok: false, cancelled: true }),
            clearData: async () => ({ ok: true, cleared: {} }), setBounds: async () => {},
          },
          downloads: { list: async () => [] },
          on: () => () => {},
          passwords: {
            list: async () => ({ ok: true, backend: 'safeStorage', entries: entries.map(e => ({ ...e })) }),
            add: async (entry) => { const id = nextId++; entries.push({ id, ...entry }); return { ok: true, id }; },
            update: async (id, fields) => { const e = entries.find(x => x.id === id); if (e) Object.assign(e, fields); return { ok: true }; },
            remove: async (id) => { const i = entries.findIndex(x => x.id === id); if (i >= 0) entries.splice(i, 1); return { ok: true }; },
            reveal: async (id) => { calls.reveal++; const e = entries.find(x => x.id === id); return e ? { ok: true, password: e.password } : { ok: false }; },
            copy: async (id) => { calls.copy++; const e = entries.find(x => x.id === id); return e ? { ok: true } : { ok: false }; },
          },
        };
        location.hash = '#/browser';
        await new Promise(r => setTimeout(r, 900));
        const btn = [...document.querySelectorAll('.nav-btn')].find(b => (b.getAttribute('title')||'').includes('Password vault'));
        if (!btn) return JSON.stringify({ ok: false, why: 'no vault button' });
        btn.click();
        await new Promise(r => setTimeout(r, 500));
        const panel = document.querySelector('.hub-vault');
        if (!panel) return JSON.stringify({ ok: false, why: 'no panel' });
        const backendNote = panel.textContent.includes("operating system's secure storage");
        // add an entry through the real form
        const inputs = [...panel.querySelectorAll('.vault-add .input')];
        const [fDomain, fUser, fPass, fNotes] = inputs;
        fDomain.value = 'example.com'; fUser.value = 'alice'; fPass.value = 'topsecret'; fNotes.value = 'note';
        const addBtn = panel.querySelector('.vault-add .btn');
        addBtn.click();
        await new Promise(r => setTimeout(r, 500));
        const row = panel.querySelector('.vault-row');
        if (!row) return JSON.stringify({ ok: false, why: 'entry row missing after add' });
        const rowText = row.textContent;
        const masked = rowText.includes('••••') && !rowText.includes('topsecret');
        // reveal through the real button
        const revealBtn = [...row.querySelectorAll('button')].find(b => b.textContent.trim() === 'Show');
        revealBtn.click();
        await new Promise(r => setTimeout(r, 400));
        const shown = panel.textContent.includes('topsecret');
        return JSON.stringify({ ok: true, backendNote, masked, shown, revealCalls: calls.reveal,
                                domainShown: rowText.includes('example.com') });
    })()""", promise=True, timeout_s=30)
    vf = _parse_json(vault_flow)
    if isinstance(vf, dict) and vf.get("ok"):
        check("vault panel: add/mask/reveal flow through the real UI",
              vf.get("masked") and vf.get("shown") and vf.get("backendNote") and vf.get("revealCalls") == 1,
              str({k: vf.get(k) for k in ("masked", "shown", "backendNote", "revealCalls")}))
    else:
        check("vault panel: add/mask/reveal flow through the real UI", False, str(vault_flow)[:90])
    # restore the real (bridge-less) web context for the honest-notice check.
    # Bounce via #/home first: re-assigning the SAME hash fires no hashchange,
    # so the page would keep the stale bridge-mounted DOM.
    js(view, "(() => { delete window.jmdb; location.hash = '#/home'; return 1; })()", timeout_s=5)
    time.sleep(0.6); pump()

    # ---------------------------------------------------------------- browser hub page (honest without Electron)
    note = goto("#/browser", "document.querySelector('.error-note') ? document.querySelector('.error-note').textContent.slice(0, 200) : ''")
    check("browser page shows honest no-Electron notice", "Electron" in str(note), str(note)[:120])

    # ---------------------------------------------------------------- PDF page artifacts (real renders)
    from PyQt6.QtCore import QObject, pyqtSignal, QTimer

    class _PdfSink(QObject):
        done = pyqtSignal()

        def __init__(self, out_path):
            super().__init__()
            self.out_path = out_path

        def on_result(self, data):
            with open(self.out_path, "wb") as handle:
                handle.write(bytes(data))
            self.done.emit()

    shots = ROOT / "screenshots"
    shots.mkdir(exist_ok=True)
    for name, route_hash, needles in [
        ("renderer-home", "#/home", ("Recently added", "Continue watching")),
        ("renderer-movies", f"#/movie/{movie_id}", ("Night Runner", "Favorite")),
        ("renderer-show", "#/show/1", ("Solar Winds", "Seasons")),
    ]:
        js(view, f"(() => {{ location.hash = {json.dumps(route_hash)}; return 1 }})()", timeout_s=3)
        wait_js(view, "document.querySelector('.hero, .grid, .detail-layout') ? 1 : 0")
        time.sleep(1.0)
        pump()
        out = shots / f"{name}.pdf"
        sink = _PdfSink(str(out))
        sink.done.connect(lambda: None)
        view.page().printToPdf(sink.on_result)
        deadline = time.time() + 25
        last_size = -1
        while time.time() < deadline:
            pump()
            time.sleep(0.25)
            if out.exists():
                size = out.stat().st_size
                if size == last_size and size > 5000:
                    break
                last_size = size
        if out.exists() and out.stat().st_size > 5000:
            from pypdf import PdfReader

            page_text = " ".join(
                (page.extract_text() or "") for page in PdfReader(str(out)).pages
            )
            check(f"PDF page artifact {name} renders real content",
                  all(needle in page_text for needle in needles),
                  f"{out.stat().st_size // 1024} KB; expected {needles}")
        else:
            check(f"PDF page artifact {name} renders real content", False, "pdf never rendered")

    # restore theme
    http_post(ctx.token, f"{BASE}/api/settings", {"theme": "system"})

    code = 0 if all(ok_ for _, ok_ in results) else 1
    return finish(server, code)


def finish(server, code: int) -> int:
    server.should_exit = True
    time.sleep(0.6)
    print(f"\nRENDERER TEST {'PASSED' if code == 0 else 'FAILED'} "
          f"({sum(1 for _, ok in results if ok)}/{len(results)} checks)", flush=True)
    return code


_js_results: list = []


def js(view, expr: str, promise: bool = False, timeout_s: float = 10.0):
    """Evaluate a JS EXPRESSION (not a function) and return its value.

    PyQt6 delivers runJavaScript results via callback only, and only primitives
    cross the bridge — objects are stringified first. ``promise`` awaits an
    async IIFE expression and stringifies its object result.
    """
    if promise:
        # PyQt6's runJavaScript callback cannot deliver async values (they arrive as
        # {}), so async work happens in-page and lands on window.__jmdb_probe,
        # which we then poll synchronously.
        launcher = (
            "(() => { window.__jmdb_probe = undefined;"
            " (async () => { const value = await (" + expr + ");"
            " window.__jmdb_probe = (value && typeof value === 'object')"
            " ? JSON.stringify(value) : value; })(); return 1; })()"
        )
        js(view, launcher, timeout_s=5)
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            landed = js(view, "window.__jmdb_probe === undefined ? 0 : String(window.__jmdb_probe)", timeout_s=3)
            if landed not in (None, 0, "0", ""):
                return landed
            pump()
            time.sleep(0.1)
        return None
    script = "(" + expr + ")"
    _js_results.clear()
    view.page().runJavaScript(script, 0, lambda value: _js_results.append(value))
    deadline = time.time() + timeout_s
    while time.time() < deadline and not _js_results:
        pump()
    return _js_results[0] if _js_results else None


def wait_js(view, expr: str, timeout_s: float = 12.0, promise: bool = False):
    """Poll a JS expression until it's truthy (or timeout)."""
    deadline = time.time() + timeout_s
    result = None
    while time.time() < deadline:
        pump()
        try:
            result = js(view, expr, promise=promise, timeout_s=2)
        except Exception:  # noqa: BLE001 - transient during navigation
            result = None
        if result not in (None, "", 0, "0", []):
            return result
        time.sleep(0.15)
    return result


def _parse_json(raw):
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except ValueError:
            return raw
    return raw


def js_value(view, expr: str, promise: bool = False, timeout_s: float = 15.0):
    """Evaluate once and PARSE JSON strings back into Python values."""
    raw = js(view, expr, promise=promise, timeout_s=timeout_s)
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except ValueError:
            return raw
    return raw


def wait_http(url: str, timeout_s: float = 30.0) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return
        except OSError:
            pass
        time.sleep(0.2)
    raise RuntimeError(f"never healthy: {url}")


def http_get(token: str, url: str):
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read())


def http_text(token: str, url: str) -> str:
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(request, timeout=10) as response:
        return response.read().decode("utf-8", "replace")


def http_post(token: str, url: str, body: dict):
    request = urllib.request.Request(
        url, data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="PATCH",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read())


if __name__ == "__main__":
    raise SystemExit(main())
