# JMDB — Final End-to-End Acceptance, Bug-Fix and Completion Pass

Branch `fix/jmdb-complete-acceptance`, base `6ea0872`, final `e964b26`.

## What was actually broken and fixed in this pass

1. **Media probing was completely broken** (`app/library/probe.py`): ffprobe
   and ffmpeg were invoked with a `--` separator that the ffmpeg-family CLI
   does not support — it is parsed as a FILENAME, so every probe failed and
   `probe_json` stayed empty (no runtimes, no codecs, no dimensions). The
   ffmpeg fallback additionally missed width/height (they sit after the
   first comma of the stream line). Fixed with absolute paths and correct
   dimension parsing; verified against real VP8 / HEVC-8bit / HEVC-10bit
   files.
2. **HEVC black screen** (the reported 1080p 10-bit case): Chromium decodes
   HEVC only with hardware support (no software fallback in stock
   Chromium/Electron). The player now (a) knows the real codec from the
   backend's probe facts, (b) surfaces an honest fallback box on the error
   event, (c) runs a decode monitor that detects "audio playing, zero video
   frames" after three consecutive seconds of active playback, (d) fully
   stops the media in a failure (no zombie audio), keeps the chrome visible,
   and always offers Back + "Open in external player" (mpv/VLC handoff via
   `/api/playback/external`, which really spawns the process — tested).
3. **Scan updates when websockets is missing**: uvicorn without the
   `websockets` package serves HTTP only, so WS-driven scan events die
   silently (the user's "Scan All shows no progress"). `websockets>=12.0`
   was already declared in requirements.txt; run.py now prints an
   actionable warning, and the renderer's polling fallback was upgraded to
   drive the SAME deduplicated finish reporter as the WebSocket (pill while
   running, exactly one completion toast, page refresh) at a 2s interval.
4. **Player controls completed**: subtitle delay (real VTTCue time
   shifting), audio-track selection where the platform supports it (honest
   note otherwise), keyboard seek/volume steps from persisted settings
   (`seek_step_seconds`, `volume_step`), default subtitle language
   auto-select, fullscreen button state sync.
5. **Test-suite fake-green hazard fixed**: a parse miss in the pause/seek
   probe silently skipped the whole autoplay/watched/history check chain
   while still reporting PASSED. It now fails loudly.

## Verification (all real, no mocks for the app code under test)

- `python -m pytest -q` → **101 tests, 0 failures, 0 errors**
  (new: probe facts through `/api/playback/start` on a real 10-bit HEVC
  file; external-player subprocess launch).
- `cd electron && npm test` → **70/70** (includes the main-lifecycle test
  that executes the real main.js boot and protects the registerIpc fix).
- `scripts/test_renderer.py` (real Chromium/QtWebEngine + real backend +
  real files) → **85/88 checks**. The 3 failures are the long-documented
  environment-only trio (offscreen Chromium stalls the final seconds of
  `timeupdate`, so autoplay-to-end / movie-player-close / watched-flag
  cannot complete in this sandbox; the same flow passes for episodes).
  New checks include: real 10-bit HEVC movie → honest fallback box, codec
  named, controls reachable, media stopped, Back exits; codec facts in the
  player panel; seek step honored through the real settings UI; subtitle
  auto-select by language; subtitle delay shifts real cue times.
- Real Electron launch: **BLOCKED by this sandbox** (the Electron binary
  CDN is outside the network allowlist — `node install.js` →
  `TypeError: fetch failed`). Must be run on the user's machine:
  `./electron/node_modules/.bin/electron ./electron --no-sandbox`.

## Warnings classification (user-observed)

- `No supported WebSocket library detected` / `Unsupported upgrade
  request` → **optional dependency missing in the local venv**
  (`websockets` is in requirements.txt; run.py now warns; UI falls back to
  polling). Fix: `pip install -r requirements.txt`.
- `handshake failed / SSL error / net_error -100` → **network/proxy
  filtering in the environment**, not an app bug.
- GLib warning at shutdown → **harmless shutdown noise**.

## Player backend (for the record)

The Electron app plays through the HTML5 `<video>` element (Chromium),
streamed from `/api/stream/{id}` with Range support; HEVC-class files get
the honest fallback + external handoff (mpv/VLC detection, resume-position
CLI flags). The `playback_backend` setting (auto|vlc|mpv|qt|external)
governs the legacy Qt UI (`python run.py --legacy-qt`).

## Branding

No new logo was created. The existing placeholder (`src/assets/icon.png`,
referenced once in `index.html` and once for the window icon in `main.js`)
stays; replacing that one file swaps the branding everywhere.
