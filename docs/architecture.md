# JMDB Architecture

## Layers (dependency direction is strictly downward)

```
run.py
 └─ app/bootstrap      startup (logging/qt/theme) · dependencies (Container) · application
 └─ ui/app             main_window · router · main         ┐
 └─ ui/screens/*       home · library · detail · …         │  UI never writes SQL;
 └─ ui/components/*    MediaCard · FlowLayout · bits       │  only repositories.
 └─ app/services       service_manager (launchers)         ┘
 └─ app/playback       service (Qt-free) · backends (qt/vlc/mpv/external)
 └─ app/search · recommendations · statistics
 └─ app/metadata       manager · providers · cache · artwork
 └─ app/library        filesystem · media_detector · indexer · scanner (QThread)
 └─ app/database       connection · schema · migrations · repositories
 └─ app/domain         enums · models · events · value_objects
 └─ app/config         paths · settings · secrets
```

## Key contracts

- **Container** (`app/bootstrap/dependencies.py`) is the *only* DI root; screens receive it
  and never construct services themselves.
- **Repositories own all SQL.** Row = plain `dict`; genres/seasons are JSON columns,
  expanded by `MediaRepository._expand`.
- **Events** travel on the Qt-free `EventBus` (`library.changed`, `media.state_changed`,
  `playback.*`). MainWindow translates them into route invalidation + re-render.
- **Playback**: `PlayerScreen` owns a backend *widget*; `PlaybackService` (no Qt) owns
  decisions — resume points (`playable_progress`), history rows, watched flags,
  autoplay-next. Backend availability is *probed*, never assumed.
- **Optional deps** (`vlc`, `mpv`, `PyQt6-WebEngine`, providers) are import-guarded;
  absence degrades capability, never crashes startup.

## Degradation matrix

| Missing | Consequence (by design) |
|---|---|
| PyQt6-WebEngine | BrowserScreen shows instructions; Services open externally |
| libvlc / libmpv / Qt codecs | Backend unchecked in Settings; External handoff remains |
| TMDB/OMDb keys | TVMaze (keyless) still enriches series; movies keep filename data |
| `requests` | Metadata subsystem disabled silently |
| FTS5 in SQLite | SearchEngine falls back to `LIKE` matching |

## Data flow (scan)

`QFileDialog folders → ScanWorker(QThread) → media_detector.detect(path) →
LibraryIndexer.index → repositories (SQLite) → MetadataManager.enrich (providers+cache)
→ bus.emit(library.changed) → MainWindow refreshes routes.`

## Relationship to the portable web build

This scaffold mirrors the single-file web prototype (`index.html` at repo parent):
same layer names, same state tables, same determinism rules (placeholder poster hash).
Differences are runtime-imposed only (SQLite vs localStorage, real files vs seed data).
