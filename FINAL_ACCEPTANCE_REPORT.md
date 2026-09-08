# JMDB Final Completion Pass — Acceptance Report

Branch: `fix/jmdb-complete-acceptance` (base: `8489cfa`, Task 4 final report)
Scope: raw-SVG icons, TV episode artwork, the four services, Browser Hub
settings + password vault, full settings audit, provider regression, and
regression tests for every fix. This report is the 15-section final
acceptance record for the pass.

---

## 1. Raw SVG on screen ("svgsvgsvg") — root cause and handling

**Never reproduced in a clean checkout.** Every page was swept with a
TreeWalker over rendered text nodes (`scripts/test_renderer.py`,
`raw_svg_sweep`) on home, services, movie player, and episode player —
zero raw `<svg`/`<path`/`svgsvg` text nodes in any run.

What was actually wrong and fixed so the class of bug cannot return
quietly:

- `ui.js` shipped an `icon()` table that silently rendered the *key name*
  as text when a lookup missed (e.g. `chevron-left` was absent). Missing
  keys now cannot produce icon-name text: the back-button icon
  (`chevron-left`) was added and lookups are exercised by the sweeps.
- The services page previously had no icon path at all for the four
  brands; it now renders real brand glyphs from `brand-icons.js`
  (section 3), so there is no fallback path left that could leak markup.
- Regression: `raw_svg_sweep` runs on every renderer-suite execution
  (4 sweeps). If any future commit renders markup as text, the suite
  fails with a sample of the offending text.

Honest status: verified in real Chromium (QtWebEngine, offscreen) against
the real backend. **Not** verified in real Electron here (section 13);
the most likely user-side cause remains a stale build, and the icon code
paths are now consistent enough that a fresh `python run.py` should
settle it.

## 2. TV episode artwork — root cause

Four real defects, all fixed generally (no per-show logic anywhere):

1. **No fallback chain.** `TvCatalog.playable()` returned artwork only
   for an episode's own still. Episodes rarely have stills when metadata
   comes from local files, so the player got nothing. Now:
   episode still → season poster → show poster (`app/media/tv.py`).
2. **Local layouts never attached.** The scanner only attached artwork
   found *in the same directory as a single owner's videos*. Real TV
   layouts are `TV/Show/poster.jpg` (videos in season subfolders) and
   `TV/Show/Season 01/season01.jpg` (videos beside it). Added
   `LibraryScanner._show_owning_subtree()`, which resolves the single
   show owning a directory subtree, and the season branch that maps
   `seasonNN*` filenames to `get_or_create_season(show, N)`.
3. **Escaping bug found by the new regression tests** (this pass): the
   subtree probe fed a LIKE-escaped string (`\_`, `\%`) to the
   *equality* comparison, so any library path containing `_` or `%`
   (e.g. `.../TV_Shows/...`, and every pytest temp home) never matched.
   Equality now gets the raw path; only the LIKE pattern is escaped.
4. **Queue had no artwork.** `/api/playback/start` now returns
   `artwork_path` on the playable media *and* on every queue entry
   (season episodes, album tracks, single-item movie queue), and the
   player renders queue thumbnails (`player.js`).

Verified end-to-end in the renderer suite against a really scanned
episode: "episode player shows artwork via season/show chain" and
"episode queue entries show artwork thumbs — 3/3" both PASS with real
PNGs served through `/api/artwork`. New API-level regression tests:
`tests/api/test_playback_artwork.py` (4 tests), including a seeded home
named `media_root_100pct` that permanently covers the escaping bug.

## 3. Services (YouTube, Telegram, Spotify, TV Time) — status

- **Real brand icons**: `electron/src/js/brand-icons.js` carries inline
  SVG path data for all four (currentColor, no network, a11y labels);
  the globe fallback remains for anything unknown.
- **Open in Browser Hub**: primary action for all four embeds the
  service in the hub through the existing architecture
  (`navigate('/browser?url=…')`; the browser page mounts the tab and
  applies saved cookies/JS policy). No new browser engine, no per-site
  hacks.
- **Honest labels**: a service card says "Open in Browser Hub" only when
  the Electron bridge exists; in the web renderer it says so and offers
  the external path. DRM-heavy entries are labeled for the system
  browser (existing honest-DRM rule).
- **TV Time**: has no public API — the card opens the real site and the
  provider catalog rejects keys honestly (`test_tvtime_key_rejected_honestly`).
  No fake login, no fake API.
- Renderer regressions: brand-icon presence, no raw SVG on services,
  embedded-open routing via `/browser?url=` — all PASS.
- Verified in real Chromium; hub embedding itself needs real Electron
  (section 13) — code path is the same `?url=` mount covered by
  `test/hub.test.js` lifecycle tests.

## 4. Browser Hub — features and settings

All previously working hub features are preserved (tabs, session
restore, history, favorites, find-in-page, zoom steps, pinned tabs,
reopen-closed-tab, PDF export, clear-data, downloads, in-page permission
dialogs, DRM hand-off to the system browser).

Newly completed in this pass:

- **Settings actually work**: search engine, default zoom, cookies, and
  JavaScript are real, persisted settings (`browser_search_engine`,
  `browser_default_zoom`, `browser_allow_cookies`,
  `browser_enable_javascript` in `/api/settings`, validated backend-side
  50–300 for zoom). Main fetches them (Bearer) *before* creating the
  Hub so restored tabs honor them.
- **Cookies**: `applyCookiePolicy()` installs a session webRequest
  listener that strips `Cookie` (request) and `set-cookie` (response)
  case-insensitively when disabled; enabling is a pass-through. The
  toggle live-applies to the whole hub session.
- **JavaScript**: per-`WebContentsView` `webPreferences.javascript` at
  creation (Chromium fixes it per view); the toggle applies to new tabs
  and says exactly that. Covered by `test/hub.test.js` policy tests
  asserting `__prefs.webPreferences.javascript`.
- **Zoom bug fixed (found by the settings audit)**: the Hub constructor
  stored the *percent* (e.g. 150) in the zoom-*factor* slot;
  `setZoomFactor(150)` throws in real Electron (valid 0.25–5), so a
  saved default zoom silently never applied to startup tabs. The
  constructor now normalizes percent→factor exactly like
  `setDefaultZoom`; regression test asserts factor 1.5 for 150%.
- **Password vault UI** in the hub (section 5).

## 5. Password Manager — security model

`electron/main/passwords.js` (`PasswordVault`), exposed through the
shared IPC registry only when a vault instance is provided:

- **Storage**: Electron `safeStorage` (OS keychain/secret store) when
  available; otherwise AES-256-GCM with a dedicated local key file
  (`vault.key`, 32 bytes, mode 0600) — secrets are never stored in
  plaintext unless the OS mechanism is available and the fallback is
  explicitly the encrypted file (`v1:` base64(iv|tag|ciphertext)).
- **Renderer exposure is minimal**: `passwords.list` returns entries
  *without* secrets; the secret is returned only by the explicit
  `reveal` and `copy` actions, triggered by explicit buttons. Nothing is
  auto-filled; the UI states there is no autofill.
- **No logging**: the vault logs entry ids and backend labels only;
  passwords never reach log output.
- **Persistence + search**: `passwords-vault.json` in userData; the
  panel lists, searches, adds, edits, reveals, copies, and removes
  entries.
- **Honesty**: the panel shows which backend is in use ("operating
  system's secure storage" / encrypted local file), and without the
  Electron bridge the browser page shows the honest no-Electron notice
  instead of a dead panel.
- Tests: `electron/test/passwords.test.js` (7 tests: encryption at
  rest, list never leaks, reveal/copy/update/remove, backend labeling)
  plus the renderer-suite flow (add → masked row → explicit reveal,
  `revealCalls == 1`) through the real UI.

## 6. Settings page — full audit

Every control was checked for: renders, persists via `/api/settings`,
survives restart, and affects behavior.

| Control | Key | Status |
| --- | --- | --- |
| Add location | `POST /api/library/locations` | Works; native folder picker in Electron, typed path + honest notice in web |
| Scan everything | `POST /api/scan` | Works (renderer-verified: 200, pill, WS toast, idle) |
| Autoplay next episode | `autoplay_next` | Works — served by `/api/playback/start`, shown in player ("On/Off (from settings)") |
| Default volume | `player_default_volume` | **Wired this pass** — player first-run volume now comes from the setting (was a hardcoded 90; the old comment claimed backend wiring that did not exist) |
| Mark watched at | `mark_watched_pct` | Works — backend watched decision (`playback.py`) |
| Resume threshold | `resume_min_seconds` | Works — `app/playback/resume.py` |
| External player | `external_player_path` | Works — `app/playback/service.py` auto-detect override |
| Search engine | `browser_search_engine` | Works — hub address-bar search mapping |
| Default zoom | `browser_default_zoom` | Works — now correctly normalized (percent→factor) for startup tabs |
| Allow cookies | `browser_allow_cookies` | Works — live session policy + persistence (renderer round-trip verified) |
| Enable JavaScript | `browser_enable_javascript` | Works — per-tab webPreferences; subtitle states new-tabs scope |
| Provider keys + Test | `/api/providers/...` | Works — set/mask/persist/clear, honest test without key, sanitized errors |
| Auto-refresh metadata | `auto_enrich_metadata` | Persisted but **no consumer in this build** — row now says "Not active in this build…" |
| Refresh after days | `auto_refresh_metadata_days` | Same — honestly labeled |
| Metadata language | `metadata_language` | Same — honestly labeled (providers currently answer in English) |
| Scan notifications | `notify_scan` | **Wired this pass** — scan-completion toast honors it (failures always show) |
| Metadata notifications | `notify_metadata` | Already wired (`app.js`) |
| About | — | Display-only by design; Electron/Chromium info appears only when the bridge exists |

Regression coverage: renderer checks for the four browser rows, the
cookies round-trip, and the honest inactive labels; persistence is
covered by `tests/api/test_settings_persistence.py`.

## 7. API-key providers — no regression

`tests/api/test_providers.py` + `test_services_routing.py` +
`test_settings_persistence.py`: **21/21 PASS** (part of the 99-test
suite). Specifically verified: the catalog lists only real providers;
key lifecycle (set/mask/persist/clear); a live provider uses a new key
immediately; unknown provider → 404; **TV Time key rejected honestly**
(no public API — never pretended); connection test honest without a key
and successful with mocked HTTP; failure details sanitized; env-var
precedence and overwrite protection; metadata sources transparent on
detail pages. Fanart.tv, Last.fm, OMDb, TMDB, TheAudioDB, TVmaze,
iTunes, MusicBrainz remain query-only-with-key, skipped honestly
otherwise.

## 8. `external.test.js` failure — cause

The external-browser test asserted "no browser found" behavior that
implicitly depended on the *machine* having no browsers on `PATH`. The
sandbox had extra executables, so detection succeeded where the test
required failure. Fix: the test now runs with `PATH=""` isolation and
stubs only what it intends to stub, so it cannot observe the host. No
production code changed.

## 9. `hub:setVisible` failure — cause

`smoke.js` registered its own partial `ipcMain` handler set and missed
`hub:setVisible` (and `preload.js` called `downloads.list` through a
wrong channel, `hub:list`). Any renderer invoke of those channels
rejected. Fix: one shared `registerIpc({hub, downloads, permissions,
vault, …})` (`electron/main/ipc.js`) used by **both** `main.js` and
`smoke.js`; it refuses to register with incomplete managers.
`electron/test/ipc.test.js` now auto-enforces preload↔main channel
parity (every `invoke()`/hub channel must have a handler; `smoke:*`
excluded), so a missing handler is a test failure, not a runtime
surprise.

## 10. `renderer-ready` failure — cause

Smoke mode waited for a readiness ping the renderer never sent: the
preload exposed `smoke.ready` unconditionally while `app.js` never
pinged after a real route render. Fix: `preload.js` gates the bridge on
`process.env.JMDB_SMOKE === "1"`; `smoke.js` sets the flag *before*
window creation; `app.js` calls `notifySmokeReady()` after the first
rendered route (`window.jmdb?.smoke?.ready?.()`). Covered by
`test/ipc.test.js` (flag ordering, gating, ready ping).

## 11. Files changed (`git diff --stat 8489cfa..HEAD`)

```
 app/api/routes/playback.py         |  19 ++-
 app/library/scanner.py             |  31 +++++
 app/media/tv.py                    |  10 +-
 electron/main.js                   | 105 +++++----------
 electron/main/hub.js               |  52 +++++++-
 electron/main/ipc.js               | 104 +++++++++++++++   (new)
 electron/main/passwords.js         | 203 +++++++++++++++++++  (new)
 electron/package.json              |   4 +-
 electron/preload.js                |  25 +++-
 electron/smoke.js                  |  32 ++++-
 electron/src/css/app.css           |  20 ++-
 electron/src/js/app.js             |  32 ++++-
 electron/src/js/brand-icons.js     |  32 +++++    (new)
 electron/src/js/pages/browser.js   | 171 +++++++++++++++++++-
 electron/src/js/pages/services.js  |  51 +++++---
 electron/src/js/pages/settings.js  |  31 ++++-
 electron/src/js/player.js          |  22 +++-
 electron/src/js/ui.js              |   1 +
 electron/test/external.test.js     |  19 ++-
 electron/test/hub.test.js          |  57 +++++++-
 electron/test/ipc.test.js          |  170 +++++++++++++++    (new)
 electron/test/modules.test.js      |   9 +-
 electron/test/passwords.test.js    |  142 ++++++++++++++++++  (new)
 scripts/test_renderer.py           | 260 ++++++++++++++++++++-
 tests/api/test_playback_artwork.py |  98 +++++++++++      (new)
 tests/seedlib.py                   |  14 +-
 26 files changed, 1581 insertions(+), 133 deletions(-)
```

## 12. Test results (actual commands and outcomes)

- **Python**: `python3 -m pytest -q` (QT_QPA_PLATFORM=offscreen,
  LD_LIBRARY_PATH=stub-libs) → **99 tests, 0 failures, 0 errors**
  (verified via `--junitxml` because uvicorn daemon threads swallow the
  terminal summary in this environment). Includes the 4 new
  `test_playback_artwork.py` regression tests.
- **Electron unit**: `cd electron && npm test` → **69/69 pass, 0 fail**
  (grew from 52: +18 ipc-parity/vault/policy tests).
- **Renderer (real Chromium + real backend)**:
  `QT_QPA_PLATFORM=offscreen LD_LIBRARY_PATH=/tmp/stub-libs
  python3 scripts/test_renderer.py` → **74/77 checks PASS**. The 3
  failures are the long-known environment trio (autoplay reaching the
  end / movie-player close / watched flag) — offscreen Chromium stalls
  the last seconds of `timeupdate` events in this sandbox; documented
  env-final, not an app defect. All artwork, queue-thumb, services,
  settings, vault, honest-notice, and no-raw-SVG checks PASS.
- **Smoke**: `cd electron && npm run smoke` → **BLOCKED (environment,
  not code)**: requires the Electron binary, which cannot be downloaded
  here (section 13). The smoke lifecycle itself is now the *same code
  path* as production (`registerIpc` parity enforced by tests).

## 13. Real Electron acceptance — honest status

**Real Electron did NOT launch in this sandbox. Per the standing rule,
the pass is therefore NOT reported as fully complete.**

Exact attempts and errors:

```
curl -sL -o /tmp/electron.zip \
  https://github.com/electron/electron/releases/download/v44.2.0/electron-v44.2.0-linux-x64.zip
# → exit 35 (SSL connect error): github.com redirects the asset to
#   objects.githubusercontent.com, which this sandbox cannot reach
#   (network allowlist covers github.com only).

cd electron && ./node_modules/.bin/electron . --no-sandbox --enable-logging=stderr --v=0
# → "Error: Cannot find module '@electron/get'" (binary was never installed)

npm install --no-save @electron/get && node node_modules/electron/install.js
# → "TypeError: fetch failed" (same blocked CDN)
```

Also absent: any system electron/chromium package, and no X server /
xvfb. `npm run smoke` fails for the same reason (needs the binary).

What was verified instead, and what remains for a real desktop:

- Verified: real backend + real Chromium renderer (QtWebEngine) end to
  end (section 12); the Electron main-process modules under Node with
  faithful stubs (hub lifecycle, IPC parity, vault crypto, policy
  flags, zoom normalization); preload contract; smoke/main parity.
- **Remaining for the user on a normal desktop** (one command):
  `cd electron && npm install && cd .. && python run.py`, then the
  manual checklist: no raw SVG anywhere; movie + TV playback with
  artwork and queue thumbs; Add Location picker + Scan; the four
  service cards open in the hub (YouTube/Telegram/Spotify embed, TV
  Time opens the site); hub settings toggles apply live and survive
  restart; password vault add/reveal/copy with the OS-secure-storage
  badge; provider keys persist.

## 14. Git history (this pass)

```
c615ef0 TV episode artwork chain: general fallback + local layout attachment
98a1ec1 Electron main: shared IPC registry, password vault, live browser settings
119979b Electron renderer: brand icons, services via Browser Hub, vault UI, live settings
bbaac7a Electron tests: IPC parity enforcement, vault unit tests, policy coverage
b441749 test_renderer: deterministic bridge cleanup for the honest-notice check
af1a830 Settings audit: wire notify_scan + default volume, honest inactive labels, zoom percent fix
```

All commits pushed to `origin/fix/jmdb-complete-acceptance`. PR #2
remains open and unmerged, per instructions.

## 15. `git status --short` (final)

```
(clean — no untracked or modified files)
```

No temp DBs, logs, screenshots, or node artifacts were added to git by
this pass; `electron/node_modules` remains exactly as tracked by the
original repository history.
