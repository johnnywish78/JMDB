# JMDB — Complete Acceptance Pass + JPNH-Parity Browser Hub

**Branch:** `fix/jmdb-complete-acceptance` (base `3f48c02`, the PR #1 head)
**Commits:** `ff67e31` (backend acceptance) · `6324da2` (Electron acceptance + JPNH browser port)
**Pull request:** #2 → `arena/01a07762-jmdb` — **opened for review only, never merged**
**Reference for the browser:** `johnnywish78/personal-network-hub` @ `33375db` ("feat: upgrade embedded browser and desktop UI")

---

## 1. Executive Summary

Two phases of work, both fully tested:

1. **Complete acceptance pass** — every acceptance criterion from the task list was exercised against the real app (real backend, real Chromium renderer, real `python run.py` launch chain). Where behavior was dishonest (fake success toasts, capabilities gated on the wrong frontend, missing API contracts), the app was fixed; where the tests themselves were wrong, the tests were fixed and the app was proven correct.
2. **JPNH-parity Browser Hub** — the embedded browser of `personal-network-hub` (now public) was ported feature-for-feature onto JMDB's existing WebContentsView hub: tab favorites, hub menu (search engine, default zoom, print, export-PDF, clear browsing data), in-page permission dialogs, tab cycling shortcuts, history search, and context-menu additions. Everything is wired to real behavior — no dead toggles from the reference were copied.

**Final test battery: pytest 95/95 · node 52/52 · launcher smoke (real `run.py`) 17/17 · renderer suite (real Chromium) 63/63.**

## 2. Scope & Method

- All work was done on a fresh clone (`/home/user/jmdb-fix`), branch `fix/jmdb-complete-acceptance`. The user's main project and home were never touched; no real media library or database was modified; throwaway temp homes only.
- The Electron **binary** cannot be downloaded in this sandbox. Main-process logic is therefore covered by (a) unit tests that load the **real** module files with a stubbed `electron` module, and (b) a launcher smoke test that runs the **real** `python run.py` with the electron binary replaced by a shim which loads the **real** `BackendProcess` and replays main.js's exact boot URL/token/cookie chain. Everything else (backend, renderer, WS, playback) ran for real.
- Every edit was applied via assert-anchored patches and verified by grep markers (25/25 present) after earlier silent-edit incidents; the full diff was audited hunk-by-hunk before committing. No secrets or tokens appear in the diff; test tokens were masked in all output.

## 3. Phase 1 — Backend Acceptance Fixes

| Area | Change | File |
|---|---|---|
| Add-location contract | `POST /api/library/locations` → 201 with full locations list; 400 invalid path; 409 duplicate; canonical-path (`realpath`) duplicate detection | `app/api/routes/library.py`, `app/services_app/coordinator.py` |
| Scan API | `location_id` accepted as query param or body; 404 for unknown locations; 409 when a scan is already running | `app/api/routes/scan.py` |
| Scan lifecycle | `phase` field (`indexing/matching/artwork`) on `LibraryScanProgress`; progress emission throttled to every 10 files or 0.5 s | `app/library/scanner.py`, `app/domain/events.py`, `app/api/context.py` |
| Providers catalog | New `/api/providers`: 9 real providers, chain order, key provenance (env vs file) via `SecretsStore.env_value()`, honest no-key behavior | `app/api/routes/providers.py`, `app/config/secrets.py`, all `app/metadata/providers/*.py` (`website`, `supplies`, `test_connection`) |
| Services per frontend | `/api/services` reads `X-JMDB-Frontend` (electron/qt/web); embedded availability is a property of the **asking client**, not the Python process | `app/api/routes/services.py`, `app/services/service_manager.py` |
| Metadata transparency | Media detail routes attach `metadata.sources` + `last_fetched` (recorded at enrichment time); never breaks a page | `app/api/routes/media.py` |
| Settings | `browser_default_zoom` (50–300, validated, survives restart) | `app/config/settings.py` |
| Dependencies | Runtime requirements now backend-only (FastAPI/uvicorn/websockets); PyQt6-WebEngine moved to dev/legacy — the Electron Browser Hub does not need it | `requirements.txt`, `requirements-dev.txt` |

## 4. Phase 1 — Renderer Acceptance Fixes

- `api.js` sends `X-JMDB-Frontend: electron`; added `api.put`.
- `app.js` scan pill shows real phase text ("Matching media", "Attaching artwork", file counts) and honest finished/failed toasts — all WS-driven (verified end-to-end in real Chromium).
- `settings.js`: provider cards with key provenance and chain order, theme as 3 separate chips, honest add-location toasts (error on invalid, "Already in your library" on duplicates, success + row on valid), search-engine select, **default-zoom row**.
- Detail pages show `Metadata: local files only (no provider key/data)` badges when no provider data exists — the honest default.
- `services.js`: embedded opening gated on the real `window.jmdb.hub` bridge; DRM sites go to the system browser with an honest button label; plain-browser sessions open a new tab.
- `address.js` (new): pure, unit-tested address-bar resolution (explicit scheme → pass-through, localhost → http, domain → https, else configured search engine).

## 5. Phase 2 — JPNH Browser Port (feature parity)

The reference (JPNH) uses `<webview>` tags; JMDB's hub uses `WebContentsView` (the modern API, per this project's constraints). All reference **features** were ported onto that architecture:

| JPNH feature | JMDB implementation | Where |
|---|---|---|
| Pinned tabs + favorites bar (`★`) | `togglePin`, `hub-favorites.json` persisted across restarts, favorites bar with chips, star in tab strip | `hub.js`, `browser.js`, `app.css` |
| Browser settings panel | Hub menu: search engine + default zoom (live `PATCH /api/settings`, applied to new tabs), **Print**, **Export to PDF**, **Clear browsing data** | `browser.js`, `hub.js` |
| Print / Export PDF (Ctrl+P) | `webContents.print()`; `printToPDF` + native save dialog + file write, result reported honestly (saved path / cancelled / error) | `hub.js`, `main.js`, `preload.js` |
| Clear browsing data (cache/cookies/history) | Real `session.clearCache()` / `clearStorageData()` on the hub's **own** `persist:jmdb` partition only (app UI session untouched); confirmation warns that cookies sign you out | `hub.js` |
| In-page permission dialog | Hub-tab permission requests surface in the renderer (Allow / Always allow / Deny, 30 s auto-dismiss); no answer in time → native dialog fallback; "Always allow" persisted per origin | `permissions.js`, `browser.js`, `main.js` |
| Ctrl+Tab / Ctrl+Shift+Tab cycling | `switchTab` with wraparound, wired both renderer-side and main-side (`before-input-event` for web-content focus) | `hub.js`, `browser.js` |
| History search | `recentHistory(query)` substring filter on url/title + search box in the history panel | `hub.js`, `browser.js` |
| Context menu: Save page / View source / Print | Added to the hub section of the shared context menu | `context-menu.js` |
| Zoom controls | `+`/`−` toolbar buttons + existing badge; zoom levels stepped 0.25–3.0 | `browser.js`, `hub.js` |
| Default zoom for new tabs | `browser_default_zoom` setting → `hub.setDefaultZoom()` → applied at tab creation | `settings.py`, `settings.js`, `browser.js`, `hub.js` |

**Not ported (honesty):** JPNH's settings panel contains localStorage-only toggles that are not wired to any real behavior (Do-Not-Track, "Safe Browsing", JavaScript/Images/Pop-ups toggles, language selector, download-location fields). Per this project's no-fake-functionality rule, only features that could be wired to real behavior were ported. JPNH's per-visit history counting (`visits`/`firstVisit`) was not needed — JMDB keeps its existing capped (5000) local history, now with correct titles.

**Bug found and fixed during the port:** `did-navigate` records history with the *previous* page's title (the new title hasn't arrived yet). History entries are now corrected when `page-title-updated` lands — same behavior as JPNH's update-in-place history.

## 6. Test Battery & Evidence (all commands actually run, final code state)

| # | Command | Result |
|---|---|---|
| 1 | `python3 -m pytest` | **95 passed** in 19.5 s |
| 2 | `cd electron && npm test` (`node --test`, 6 files) | **52/52** — incl. 9 new hub tests and 6 new permission tests |
| 3 | Launcher smoke: real `JMDB_HOME=<temp> python3 run.py` with electron binary shimmed to load the real `BackendProcess` | **17/17** — 307 boot + HttpOnly cookie, UI 200, API 200/401, providers 9, services 4 × `embedded=true` with `X-JMDB-Frontend`, invalid location 400 |
| 4 | `QT_QPA_PLATFORM=offscreen python3 scripts/test_renderer.py` (real Chromium/QtWebEngine) | **63/63** — navigation, real API data, theme, 8 provider cards, chain order, Browse… picker, TV-Time no-API note, honest add-location toasts (error **and** success), services = exactly 4 with official https URLs, metadata badge, WS scan lifecycle (pill flash caught via MutationObserver latch after the scan proved to run in ~1 ms on a tiny library), subtitles SRT→WebVTT, **real VP8 playback** (play/pause/seek/autoplay-finish/watched-marking/history), episode subtitles, honest no-Electron notice |

Suite-4 scan-pill note: the app's WS chain was proven correct first (instrumented `onmessage` wrapper + pill MutationObserver showed `scan_started` → pill visible → `scan_finished` → pill hidden within ~1 ms on a near-empty library). The test now latches the pill state via MutationObserver instead of polling, which is race-free by construction.

## 7. Bugs Found & Fixed Along the Way

1. Renderer module graph silently broken: `movie-detail.js` was missing `export function metadataSourceBadge` (imported by show/artist/album detail) → whole `app.js` module failed → nav never populated. Found via QtWebEngine console dump, fixed, re-verified.
2. `settings.js` missing `clear` (ui.js) and `on` (store.js) imports → ReferenceError at runtime.
3. `package.json` test script did not run the new test files.
4. Test-side: `wait_js` returns JS numbers as Python ints; checks comparing to the string `"1"` always failed — the valid-location add had *succeeded* all along (proven by toast/row diagnostics).
5. Test-side: `.service-card .note` selector also matched the embedded-Hub hint text; now filtered to `https://` notes (exactly 4).
6. Hub history entries carried the previous page's title (fixed, see §5).
7. Test-infra incident (no product impact): copying the smoke shim onto the `.bin/electron` symlink overwrote `node_modules/electron/cli.js`; restored via `git checkout` immediately.

## 8. Implemented vs Provider-Limited / Environment-Limited

**Implemented and verified locally (no network needed):** everything in §3–§5, all four test suites, playback of a real VP8 file, subtitles, WS scan lifecycle, favorites persistence, permission flows, print/PDF plumbing (save dialog is exercised in unit tests with a stubbed dialog; `printToPDF` returns real PDF bytes to a real temp path in tests).

**Provider-limited (requires user API keys, by design):** TMDB/OMDb/TVmaze/MusicBrainz/TheAudioDB/Last.fm/Fanart.tv enrichment and their `test_connection` results. No keys are present in this environment, so provider-backed metadata is honestly reported as "local files only". Nothing fakes provider success. TV Time has **no public API** and is documented as such.

**Environment-limited (sandbox):** outbound internet is not available here, so live service loading (YouTube/Telegram/Spotify/TV Time pages), DRM playback (system browser, by design), and real Electron-binary windowing could not be exercised end-to-end; they are covered by the launcher smoke shim + module unit tests instead, as documented in §2. Network failures were never classified as app bugs.

## 9. Security & Honesty Checklist

- `contextIsolation: true`, `nodeIntegration: false`, sandbox enabled; preload remains the only bridge — 9 new narrow hub channels (`togglePin`, `favorites`, `switchTab`, `print`, `exportPdf`, `clearData`, `setDefaultZoom`, `history`-with-query, plus existing).
- Production backend binds `127.0.0.1` only, per-launch token, HttpOnly cookie — unchanged and regression-tested (PR #1 fixes intact, WS auth included).
- "Allow" answers a permission once; only "Always allow" persists. Unknown permissions are denied with no dialog.
- Clearing browsing data warns that it signs you out; it touches only the hub partition.
- No tokens/keys in logs, reports, commits, or the diff (audited).
- No `--no-sandbox` in production code paths.

## 10. Compatibility & Migration Notes

- `POST /api/library/locations` now returns 201 (was 200) and raises 400/409 instead of `{"ok": false}` — the settings page was updated accordingly. Old clients treating non-2xx as failure will still behave correctly.
- `requirements.txt` no longer installs PyQt6 at runtime; the legacy Qt UI moves behind dev extras. `python run.py` (Electron path) is unaffected.
- Existing hub sessions/history keep working; favorites and pinned-tab state are new files in the Electron `userData` directory. Existing tabs keep their zoom; only new tabs pick up `browser_default_zoom`.

## 11. Known Limitations & Follow-ups

- The Electron binary cannot run in this sandbox, so the new hub UI (menu, favorites bar, permission dialog) was verified at the unit/contract level (real module code, stubbed `electron`) and by the renderer suite for the non-Electron fallback path — a final manual pass inside the packaged desktop app is recommended.
- History search is substring-based (like the reference); no time-range filtering.
- Clear-data is all-or-nothing per selected type; no per-site cookie management.
- `view-source:` tabs depend on Chromium support in the embedded view (standard behavior).

## 12. Deliverables

- Branch `fix/jmdb-complete-acceptance` on `johnnywish78/JMDB`: commits `ff67e31` and `6324da2` (+ this report).
- **PR #2** `fix/jmdb-complete-acceptance` → `arena/01a07762-jmdb`: https://github.com/johnnywish78/JMDB/pull/2 — **do not merge without review** (PR #1 remains open and untouched).
- New tests: `tests/api/test_locations.py` (8), `test_scan_lifecycle.py` (5), `test_providers.py` (10), `test_services_routing.py` (6), `test_settings_persistence.py` (5), `tests/test_dependencies.py` (5), `electron/test/{address,external,hub,modules,permissions}.test.js` (+15 files' worth of coverage), `scripts/test_renderer.py` (63 checks).
- Debug/verification artifacts (not committed): launcher smoke shim, WS/pill probes, repro scripts — all under `/tmp` in the work sandbox.
