# JMDB — Johnny Media Database (PyQt6)

اپ دسکتاپ شخصی برای مدیریت کتابخانهٔ فیلم/سریال — PyQt6 + SQLite.

> **وضعیت تحویل (صادقانه):** این یک **scaffold با کیفیت تولیدی** است که داخل محیطی بدون Python/Qt تولید شده است.
> کدها واقعی و import‌های متقابل هماهنگ‌اند، ولی در محیط تولید **اجرا/تست نشده‌اند**.
> اولین اجرای واقعی: بخش «راه‌اندازی» و سپس `scripts/diagnostics.py` را ببینید.

## Quick start (Ubuntu)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # (+ optional backends اگر خواستید)
cp .env.example .env                      # TMDB/OMDb keys (اختیاری)
python run.py
```

Backendهای پخش (اختیاری — با graceful degradation):

```bash
sudo apt install libvlc-dev mpv           # کتابخانه‌های سیستمی
pip install python-vlc python-mpv
```

تست‌ها (منطق خالص، بدون Qt):

```bash
pip install pytest
pytest                 # detector + repositories + search/reco/stats
```

## ساختار

```
app/config       مسیرها، تنظیمات JSON، secrets از .env
app/domain       enums، مدل‌ها (dataclass)، event bus، value objects
app/database     connection (WAL, FK) · schema + migrations · repositories
app/library      filesystem walker · filename detector · indexer · Qt ScanWorker
app/metadata     providers (TMDB/TVmaze/OMDb) · cache · manager · artwork/pixmap
app/search       FTS5 + fallback LIKE        app/recommendations · app/statistics
app/playback     backends (qt/vlc/mpv/external) + PlaybackService (resume/history/autonext)
app/browser      QWebEngine (در صورت نصب) + bookmarks      app/services launcher registry
ui/app           router + state + main window              ui/components cards/flow layout
ui/screens       home · library · detail · personal · discover · settings · player · services
ui/themes        dark.qss / light.qss +Accent tokens
scripts/         scan.py (headless) · diagnostics.py (env probe، --migrate/--reset)
tests/           unit (detector) · database (repos) · services (search/reco/stats)
```

## قواعد معماری

1. جهت وابستگی فقط به سمت پایین: `ui → services/screens → domain/db → config`.
2. UI هرگز مستقیم SQL نمی‌زند — فقط از طریق `repositories`.
3. وابستگی‌های اختیاری (vlc/mpv/webengine) همیشه import-guarded؛ نبودنشان = degrade صادقانه، نه crash.
4. رویدادهای بین‌لایه‌ای فقط از `EventBus` (`app/domain/events.py`) عبور می‌کنند.

مستندات بیشتر: `docs/architecture.md` · `docs/troubleshooting.md`
