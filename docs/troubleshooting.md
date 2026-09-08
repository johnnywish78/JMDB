# Troubleshooting

## Qt fails to start on Ubuntu

`qt.qpa.plugin: could not load the Qt platform plugin "xcb"`
→ install platform libs:
`sudo apt install libxcb-xinerama0 libxcb-cursor0 libxkbcommon-x11-0 libgl1`

## Playback backends

- **MPV recommended**: `sudo apt install mpv` then `pip install python-mpv`.
  Embedding needs X11 for `wid=`; on Wayland use the QT or VLC backend.
- **VLC**: `sudo apt install libvlc-dev vlc` then `pip install python-vlc`.
- Backend shows "(unavailable)" in Settings → hover the note row: the probe
  reason is printed there. Probes never crash the app.
- File plays but no sound with Qt Multimedia → install gstreamer plugins:
  `sudo apt install gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly`

## Embedded browser

- `pip install PyQt6-WebEngine`. If running as root or in containers, QtWebEngine
  may need `QTWEBENGINE_DISABLE_SANDBOX=1`.
- Many sites (Netflix, Google) refuse `X-Frame-Options`-less embedding only via DRM —
  Widevine is not bundled; use "External".

## Database

- **Locked errors**: WAL mode is enabled at connect; avoid opening `data/database/jmdb.db`
  in another writer while JMDB runs.
- **Reset**: `python run.py --reset-db` or Settings → Reset everything.
- **Schema drift**: never edit data by hand; add a migration in
  `app/database/migrations.py` and bump the tuple.

## Search finds nothing

If your SQLite lacks FTS5, `media_fts` is skipped and search uses `LIKE` fallback —
check `python scripts/diagnostics.py` → `fts5: ok|missing`.

## Metadata / providers

- Series enrichment works **keyless** via TVMaze. Movies need `TMDB_API_KEY` in `.env`.
- 401 from TMDB = wrong key → Settings shows it in Diagnostics output too.
- Providers are rate-polite (150ms between items); big libraries take time — use
  `--no-enrich` in `scripts/scan.py` to index instantly, enrich later.

## Logs

`data/logs/jmdb.log` — rotate-friendly, plain text. Diagnostics prints the tail.
