#!/usr/bin/env python3
"""Headless library scan (no Qt):
    python scripts/scan.py /media/movies /media/tv [--no-enrich]
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(prog="jmdb-scan")
    parser.add_argument("folders", nargs="+", help="media folders to scan")
    parser.add_argument("--no-enrich", action="store_true", help="skip metadata providers")
    args = parser.parse_args()

    from app.config.paths import AppPaths
    from app.config.secrets import env
    from app.database.connection import Database
    from app.database.migrations import migrate
    from app.database.repositories import EpisodeRepository, MediaRepository
    from app.library.filesystem import iter_media_files
    from app.library.indexer import LibraryIndexer
    from app.library.media_detector import detect
    from app.metadata.cache import MetadataCache
    from app.metadata.manager import MetadataManager

    paths = AppPaths().ensure()
    db = Database(paths.db_path)
    db.connect()
    migrate(db)
    media_repo = MediaRepository(db)
    indexer = LibraryIndexer(media_repo, EpisodeRepository(db))

    manager = None
    if not args.no_enrich:
        manager = MetadataManager(MetadataCache(db),
                                  tmdb_key=env("TMDB_API_KEY"), omdb_key=env("OMDB_API_KEY"))
        if not manager.configured():
            print("[scan] no providers configured (set TMDB_API_KEY in .env) — index only")
            manager = None

    counts = {"movie": 0, "episode": 0, "music": 0, "errors": 0, "enriched": 0}
    started = time.time()
    for folder in args.folders:
        files = sorted(iter_media_files(Path(folder)))
        print(f"[scan] {folder}: {len(files)} files")
        for i, path in enumerate(files, 1):
            try:
                d = detect(path)
                media_id = indexer.index(d)
                counts[d.kind.value] += 1
                print(f"  [{i:>4}/{len(files)}] {d.kind.value:<7} {d.title}"
                      + (f" S{d.season:02d}E{d.number:02d}" if d.season else ""))
                if manager is not None:
                    if manager.enrich(media_id, d, media_repo=media_repo):
                        counts["enriched"] += 1
                    time.sleep(0.15)
            except Exception as exc:
                counts["errors"] += 1
                print(f"  [error] {path}: {exc}")
    db.close()
    print(f"[scan] done in {time.time() - started:.1f}s → {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
