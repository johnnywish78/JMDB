"""DDL. Migration 1 = core tables. Migration 2 = FTS5 index + sync triggers.
Migration 3 = metadata_cache provider column + schema version."""

SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS media (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    kind           TEXT NOT NULL CHECK(kind IN ('movie','show','music')),
    title          TEXT NOT NULL,
    original_title TEXT NOT NULL DEFAULT '',
    year           INTEGER,
    rating         REAL NOT NULL DEFAULT 0,
    overview       TEXT NOT NULL DEFAULT '',
    runtime_min    INTEGER NOT NULL DEFAULT 0,
    genres         TEXT NOT NULL DEFAULT '[]',
    file_path      TEXT,
    poster_path    TEXT,
    backdrop_path  TEXT,
    imdb_id        TEXT NOT NULL DEFAULT '',
    tmdb_id        INTEGER,
    seasons        TEXT NOT NULL DEFAULT '[]',
    added_at       INTEGER NOT NULL DEFAULT (strftime('%s','now')*1000),
    UNIQUE(kind, title, year)
);
CREATE INDEX IF NOT EXISTS idx_media_kind ON media(kind);

CREATE TABLE IF NOT EXISTS episodes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    show_id     INTEGER NOT NULL REFERENCES media(id) ON DELETE CASCADE,
    season      INTEGER NOT NULL,
    number      INTEGER NOT NULL,
    title       TEXT NOT NULL DEFAULT '',
    runtime_min INTEGER NOT NULL DEFAULT 0,
    file_path   TEXT,
    UNIQUE(show_id, season, number)
);
CREATE INDEX IF NOT EXISTS idx_episodes_show ON episodes(show_id);

CREATE TABLE IF NOT EXISTS people (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS media_people (
    media_id  INTEGER NOT NULL REFERENCES media(id) ON DELETE CASCADE,
    person_id INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    role      TEXT NOT NULL CHECK(role IN ('actor','director','creator')),
    UNIQUE(media_id, person_id, role)
);

CREATE TABLE IF NOT EXISTS playback_progress (
    media_key   TEXT PRIMARY KEY,
    position_s  INTEGER NOT NULL,
    duration_s  INTEGER NOT NULL,
    updated_at  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS watch_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    media_key   TEXT NOT NULL,
    media_title TEXT NOT NULL,
    subtitle    TEXT NOT NULL DEFAULT '',
    started_at  INTEGER NOT NULL,
    finished_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_history_finished ON watch_history(finished_at);

CREATE TABLE IF NOT EXISTS episodes_watched (
    episode_id INTEGER PRIMARY KEY REFERENCES episodes(id) ON DELETE CASCADE,
    watched_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS movies_watched (
    media_id   INTEGER PRIMARY KEY REFERENCES media(id) ON DELETE CASCADE,
    watched_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS favorites (
    media_id INTEGER PRIMARY KEY REFERENCES media(id) ON DELETE CASCADE,
    added_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS watchlist (
    media_id INTEGER PRIMARY KEY REFERENCES media(id) ON DELETE CASCADE,
    added_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS ratings (
    media_id   INTEGER PRIMARY KEY REFERENCES media(id) ON DELETE CASCADE,
    value      INTEGER NOT NULL CHECK(value BETWEEN 1 AND 10),
    updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS bookmarks (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    name     TEXT NOT NULL,
    url      TEXT NOT NULL UNIQUE,
    position INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS metadata_cache (
    bucket     TEXT NOT NULL,
    key        TEXT NOT NULL,
    provider   TEXT NOT NULL DEFAULT '',
    payload    TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    PRIMARY KEY (bucket, key, provider)
);
"""

SCHEMA_V2 = """
CREATE VIRTUAL TABLE IF NOT EXISTS media_fts USING fts5(
    title, original_title, overview, genres,
    content='media', content_rowid='id'
);
CREATE TRIGGER IF NOT EXISTS media_ai AFTER INSERT ON media BEGIN
    INSERT INTO media_fts(rowid, title, original_title, overview, genres)
    VALUES (new.id, new.title, new.original_title, new.overview, new.genres);
END;
CREATE TRIGGER IF NOT EXISTS media_ad AFTER DELETE ON media BEGIN
    INSERT INTO media_fts(media_fts, rowid, title, original_title, overview, genres)
    VALUES ('delete', old.id, old.title, old.original_title, old.overview, old.genres);
END;
CREATE TRIGGER IF NOT EXISTS media_au AFTER UPDATE ON media BEGIN
    INSERT INTO media_fts(media_fts, rowid, title, original_title, overview, genres)
    VALUES ('delete', old.id, old.title, old.original_title, old.overview, old.genres);
    INSERT INTO media_fts(rowid, title, original_title, overview, genres)
    VALUES (new.id, new.title, new.original_title, new.overview, new.genres);
END;
INSERT INTO media_fts(media_fts) VALUES ('rebuild');
"""

SCHEMA_V3 = """
CREATE TABLE IF NOT EXISTS metadata_cache_v3 (
    bucket     TEXT NOT NULL,
    key        TEXT NOT NULL,
    provider   TEXT NOT NULL DEFAULT '',
    payload    TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    PRIMARY KEY (bucket, key, provider)
);
INSERT OR IGNORE INTO metadata_cache_v3 (bucket, key, provider, payload, created_at)
    SELECT bucket, key, '', payload, created_at FROM metadata_cache;
DROP TABLE IF EXISTS metadata_cache;
ALTER TABLE metadata_cache_v3 RENAME TO metadata_cache;
"""
