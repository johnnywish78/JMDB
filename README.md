# JMDB — Johnny Media Database

A local-first personal media center for movies, TV, music, and online services.
PyQt6 desktop app, SQLite storage, no accounts, no telemetry, no cloud.

## What it does

- **Library** — scan local folders into a SQLite database; movies, TV shows
  (show → season → episode), music (artist → album → track), people, artwork.
  Missing/moved files are detected, duplicates flagged.
- **Playback** — play anything with a linked file through VLC, MPV, or the Qt
  backend (auto-resolved, configurable in Settings); or hand off to an external
  player. Resume positions, watch history, "continue watching", next-up episode.
  Embedded player with playlist, subtitles/audio track selection, delays,
  speed, aspect ratio, and full keyboard control.
- **Metadata** — enrich from TMDB / OMDb / TVmaze (video) and MusicBrainz /
  TheAudioDB / Last.fm (music). API keys are optional, stored locally, redacted
  from logs. Providers are called only for features you use.
- **Browser & services** — an embedded browser (PyQt6-WebEngine) for
  non-DRM sites; DRM services (Netflix, Prime Video, Disney+, …) open in the
  system browser because embedded engines cannot play DRM content. Each
  service tile reports its real availability — nothing is faked.
- **Search & discovery** — FTS5 search across everything with filters (type,
  genre, year range, rating, unwatched, favorites); local recommendation
  engine (genres, favorites, ratings, history, shared cast/crew).
- **Organize** — favorites, watchlist, ratings, watched marks, user
  collections (create/rename/delete/reorder), statistics dashboard computed
  from your actual data.

Everything runs locally. The only network traffic is to metadata providers you
configure and websites you open in the browser.

## Requirements

- Python 3.10+
- Core: `PyQt6`, `requests`, `Pillow`, `mutagen`
- Optional (each enables a subsystem; JMDB degrades gracefully when missing):
  - `PyQt6-WebEngine` — embedded browser (else: honest fallback + system browser)
  - `PyQt6-Multimedia` — Qt playback backend
  - `python-vlc` + VLC installed — VLC backend (recommended)
  - `python-mpv` + libmpv — MPV backend

## Run

```bash
pip install -r requirements.txt
python run.py
```

First run creates `~/.jmdb/` (database, config, logs, artwork cache, browser
profile). Add library folders in **Settings → Library folders**, then
**Scan library now**. Set `JMDB_HOME` to relocate everything.

## Layout

```
run.py                     launcher
app/
  bootstrap/               entry point, DI graph, logging (with secret redaction)
  config/                  paths, settings, secrets
  database/                connection, migrations, repositories (read/write models)
  domain/                  entities, value objects, events
  library/                 scanner (movies/TV/music naming conventions, dedupe)
  media/                   catalog read-models for the UI (movies/tv/people/music)
  metadata/                provider clients + enrichers, caching
  playback/                backends (vlc/mpv/qt/external), controller, sessions
  search/                  FTS5 engine + filters
  recommendations/         local recommendation engine
  statistics/              overview + top-N aggregates
  browser/                 WebEngine profile/cookies/downloads/history
  services/                service registry (streaming etc.) with real availability
ui/
  app/                     UIContext, Router, MainWindow, state
  screens/                 21 screens (home, catalogs, details, lists, search, …)
  components/              shared widgets (cards, dialogs, states, detail hero/body)
  player/                  PlayerWindow, controls, playlist, subtitle/audio dialogs
  themes/                  dark/light QSS + ThemeManager
scripts/
  smoke_ui.py              headless full-app smoke (seeds a library, visits all routes)
  screenshot_ui.py         offscreen screenshots of every screen for visual QA
tests/
  integration/             scanner end-to-end (real temp filesystem)
  ui/                      router, components, full-app route smoke
```

## Testing

```bash
python -m pytest tests/ -q          # unit + integration + UI (offscreen Qt)
QT_QPA_PLATFORM=offscreen python3 scripts/smoke_ui.py
```

All tests are hermetic: temp `JMDB_HOME`, offscreen Qt, no network.

## Design notes

- **No fake data.** Screens render from the real database; empty states say so.
- **No secrets in logs.** API keys are stored in the local config store and
  redacted from every log line via a logging filter.
- **DRM is not lied about.** DRM services route to the system browser.
- **Threads marshaled to Qt signals.** Repositories are not touched from the
  UI thread directly for heavy reads; results land via queued connections.
