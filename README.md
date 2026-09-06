# JMDB — Johnny Media Database

A personal media center for your own movies, TV, music and people — an **Electron desktop app** with a **Python (FastAPI) backend**, talking over localhost HTTP + WebSocket only.

```
python run.py
```

That one command starts the local backend (127.0.0.1, per-launch token) and the full desktop app — library, player, browser hub, settings. No second terminal.

---

## What it does

- **Library** — movies, TV shows (seasons/episodes), music (artists/albums/tracks), people (cast/crew with filmography); posters, backdrops and stills when artwork has been fetched; favorites, watchlist, watch history, collections, continue-watching, recommendations, statistics.
- **Player** — real HTML5 player: seek bar with buffer indicator, volume/mute, speed, subtitles (external `.srt`/`.vtt`, converted to WebVTT), picture-in-picture, prev/next in queue, restart, resume prompt, autoplay-next, full keyboard control (Space/M/F/arrows/N/P/I/C/R/dblclick), auto-hiding chrome. Progress, watched-marking and next-episode decisions are **owned by the Python backend**.
- **Browser Hub** — a real multi-tab browser inside the app (Electron `WebContentsView`, persistent `persist:jmdb` session partition so your service logins survive restarts): address bar with search-engine fallback, back/forward/reload, bookmarks, downloads manager with pause/resume/cancel, per-site permissions (persisted), find-in-page, zoom, history, popups → tabs, context menus, external-Chrome handoff, DRM sites → system browser (honest: DRM doesn't run inside Chromium).
- **Services** — exactly four: **YouTube, Telegram, Spotify, TV Time**, opened inside the Browser Hub. TV Time has **no public API** — it opens their website; tracking happens there.
- **Metadata** — TMDB / OMDb / TVmaze / MusicBrainz etc. via the existing enricher, with your own API keys; honest provider-limited behavior without keys (local file metadata only). Nothing is faked.
- **Scanner** — add media locations, scan, watch progress live (WebSocket events) — multi-episode files (`S01E02-E03`) expand correctly.
- **Themes** — dark / light / system, actually applied and persisted.

## One command, three modes

```
python run.py                 # the app (Electron + backend)
python run.py --backend-only  # just the local API server (dev)
python run.py --legacy-qt     # the previous PyQt6 UI (legacy)
python run.py --theme light   # set the theme, then launch
python run.py --reset-db      # guarded, backup-first reset (asks for typed confirmation)
```

First Electron run installs it:

```
cd electron && npm install
```

## Architecture

```
run.py                    launcher: owns the backend, spawns Electron
app/                      Python backend (unchanged core: database, repos, services)
  api/                    FastAPI layer: token auth, REST + WS, media streaming
electron/
  main.js + main/         Electron main process (window, backend, hub, downloads,
                         permissions, context menus, external browser)
  preload.js              the only bridge (contextIsolation on, nodeIntegration off)
  src/                    the UI — plain HTML/CSS/vanilla-JS modules, 21 routes
tests/                    pytest suites (API 32, UI 16, integration 5) + seeds
electron/test/            node unit tests
electron/smoke.js         in-Electron smoke test
scripts/test_renderer.py  real-Chromium integration test of the whole renderer
```

- The backend binds **127.0.0.1 only**, with a **per-launch token** (`Bearer`/`?token=`/HttpOnly cookie). The renderer is served same-origin by the backend itself (`/app`), so it needs no token and no CORS.
- The renderer has **no Node access** (`contextIsolation: true`, `nodeIntegration: false`, sandboxed preload with a minimal `jmdb` bridge).
- The DB schema is untouched; `--reset-db` always backs up first and requires a typed `RESET`.

## Tests (real results, this environment)

| suite | command | result |
| --- | --- | --- |
| Python API | `python3 -m pytest tests/api/ -q` | **32/32 pass** |
| full pytest | `python3 -m pytest tests/ -q` | **53/53 pass** |
| node units | `node --test electron/test/url-utils.test.js` | **7/7 pass** |
| renderer (real Chromium) | `QT_QPA_PLATFORM=offscreen python3 scripts/test_renderer.py` | **40/40 pass** |
| launcher | `python3 run.py --help`, `--backend-only`, `--theme`, guarded `--reset-db` | all verified |
| in-Electron smoke | `cd electron && ./node_modules/.bin/electron smoke.js` | **blocked here** — see below |

Renderer coverage includes: real navigation/filters/search/detail pages, theme persist+apply, **real video playback** (VP8 clip via the real streaming API), real controls round-trip (pause/seek/keyboard), subtitles (SRT→WebVTT, track `showing`), progress + finish reported to and decided by the backend, autoplay-to-finished, and real PDF page artifacts (`screenshots/renderer-*.pdf`).

## Honest limitations (this sandbox)

- **The Electron binary can't be downloaded here** — `objects.githubusercontent.com` (GitHub release assets) is blocked, so `npm install electron` leaves no `dist/`. Consequence: `electron/smoke.js` (boot/bridge/theme/hub round-trips) is shipped but **not runnable in this sandbox**. The renderer it drives is fully tested via real Chromium (QtWebEngine) instead. On a normal network, `cd electron && npm install` fetches the binary and the smoke runs.
- **PyInstaller**: blocked — `libpython3.11.so.1.0` is not present (Debian's `libpython3.11` package; `apt` unreachable). `electron-builder`: blocked by the same Electron-binary issue.
- This sandbox's headless Chromium has no proprietary codecs (H.264/AAC), so the renderer test uses a VP8 clip; real Electron plays both.
- TV Time / EMDB have no public API — never fabricated; they open as web apps.
- DRM sites (Netflix etc.) open in the system browser — DRM doesn't run inside Chromium.

## Legacy

The previous PyQt6 UI is kept, working (`--legacy-qt`) and tested (16/16), but it is no longer the production UI.

## Data safety

Your database lives outside the repo (`~/.jmdb` by default). Nothing here ever touches your media files. Destructive operations don't exist in code paths; `--reset-db` is guarded (typed confirmation + timestamped backup first) and is never automatic.
