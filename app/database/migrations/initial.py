"""Initial schema (migration v1).

Full relational schema for JMDB. All foreign keys are explicit; all
frequently-joined columns are indexed.
"""
from __future__ import annotations

INITIAL_SQL: list[str] = [
    # --- users / profiles -------------------------------------------------
    """CREATE TABLE profiles (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        is_default INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    "INSERT INTO profiles (name, is_default) VALUES ('Default', 1)",

    # --- library locations & files -----------------------------------------
    """CREATE TABLE library_locations (
        id INTEGER PRIMARY KEY,
        path TEXT NOT NULL UNIQUE,
        label TEXT NOT NULL DEFAULT '',
        enabled INTEGER NOT NULL DEFAULT 1,
        added_at TEXT NOT NULL DEFAULT (datetime('now')),
        last_scan_at TEXT,
        last_scan_status TEXT NOT NULL DEFAULT 'never',
        last_scan_error TEXT NOT NULL DEFAULT ''
    )""",
    """CREATE TABLE media_files (
        id INTEGER PRIMARY KEY,
        library_location_id INTEGER NOT NULL REFERENCES library_locations(id) ON DELETE CASCADE,
        path TEXT NOT NULL UNIQUE,
        filename TEXT NOT NULL,
        directory TEXT NOT NULL,
        size_bytes INTEGER NOT NULL DEFAULT 0,
        mtime_ns INTEGER NOT NULL DEFAULT 0,
        kind TEXT NOT NULL,              -- video|audio|subtitle|image|other
        container TEXT NOT NULL DEFAULT '',
        checksum TEXT NOT NULL DEFAULT '',
        is_missing INTEGER NOT NULL DEFAULT 0,
        indexed_at TEXT NOT NULL DEFAULT (datetime('now')),
        last_seen_at TEXT NOT NULL DEFAULT (datetime('now')),
        probe_json TEXT
    )""",
    "CREATE INDEX idx_media_files_kind ON media_files(kind)",
    "CREATE INDEX idx_media_files_location ON media_files(library_location_id)",
    "CREATE INDEX idx_media_files_missing ON media_files(is_missing)",
    "CREATE INDEX idx_media_files_checksum ON media_files(checksum)",

    # --- movies / tv -------------------------------------------------------
    """CREATE TABLE movies (
        id INTEGER PRIMARY KEY,
        title TEXT NOT NULL,
        original_title TEXT NOT NULL DEFAULT '',
        sort_title TEXT NOT NULL DEFAULT '',
        year INTEGER,
        release_date TEXT,
        runtime_seconds INTEGER,
        overview TEXT NOT NULL DEFAULT '',
        tagline TEXT NOT NULL DEFAULT '',
        rating REAL,
        vote_count INTEGER,
        certification TEXT NOT NULL DEFAULT '',
        languages TEXT NOT NULL DEFAULT '',
        countries TEXT NOT NULL DEFAULT '',
        collection_id INTEGER REFERENCES movie_collections(id) ON DELETE SET NULL,
        added_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    "CREATE INDEX idx_movies_title ON movies(title)",
    "CREATE INDEX idx_movies_year ON movies(year)",
    "CREATE INDEX idx_movies_sort ON movies(sort_title)",
    "CREATE INDEX idx_movies_added ON movies(added_at DESC)",

    """CREATE TABLE tv_shows (
        id INTEGER PRIMARY KEY,
        title TEXT NOT NULL,
        original_title TEXT NOT NULL DEFAULT '',
        sort_title TEXT NOT NULL DEFAULT '',
        first_air_date TEXT,
        last_air_date TEXT,
        status TEXT NOT NULL DEFAULT '',
        overview TEXT NOT NULL DEFAULT '',
        rating REAL,
        vote_count INTEGER,
        added_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    "CREATE INDEX idx_tv_shows_title ON tv_shows(title)",
    "CREATE INDEX idx_tv_shows_sort ON tv_shows(sort_title)",
    "CREATE INDEX idx_tv_shows_added ON tv_shows(added_at DESC)",

    """CREATE TABLE seasons (
        id INTEGER PRIMARY KEY,
        tv_show_id INTEGER NOT NULL REFERENCES tv_shows(id) ON DELETE CASCADE,
        season_number INTEGER NOT NULL,
        title TEXT NOT NULL DEFAULT '',
        overview TEXT NOT NULL DEFAULT '',
        air_date TEXT,
        UNIQUE (tv_show_id, season_number)
    )""",

    """CREATE TABLE episodes (
        id INTEGER PRIMARY KEY,
        tv_show_id INTEGER NOT NULL REFERENCES tv_shows(id) ON DELETE CASCADE,
        season_id INTEGER NOT NULL REFERENCES seasons(id) ON DELETE CASCADE,
        season_number INTEGER NOT NULL,
        episode_number INTEGER NOT NULL,
        title TEXT NOT NULL DEFAULT '',
        overview TEXT NOT NULL DEFAULT '',
        air_date TEXT,
        runtime_seconds INTEGER,
        rating REAL,
        UNIQUE (season_id, episode_number)
    )""",
    "CREATE INDEX idx_episodes_show ON episodes(tv_show_id)",
    "CREATE INDEX idx_episodes_season ON episodes(season_id)",
    "CREATE INDEX idx_episodes_air ON episodes(air_date DESC)",

    # file ↔ item links (single representation of file ownership)
    """CREATE TABLE media_file_links (
        id INTEGER PRIMARY KEY,
        media_item_type TEXT NOT NULL,       -- movie|episode|track
        media_item_id INTEGER NOT NULL,
        media_file_id INTEGER NOT NULL REFERENCES media_files(id) ON DELETE CASCADE,
        is_primary INTEGER NOT NULL DEFAULT 0,
        UNIQUE (media_item_type, media_item_id, media_file_id)
    )""",
    "CREATE INDEX idx_links_file ON media_file_links(media_file_id)",
    "CREATE INDEX idx_links_item ON media_file_links(media_item_type, media_item_id)",

    # --- people & credits ----------------------------------------------------
    """CREATE TABLE people (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        biography TEXT NOT NULL DEFAULT '',
        birthday TEXT,
        deathday TEXT,
        place_of_birth TEXT NOT NULL DEFAULT '',
        popularity REAL
    )""",
    "CREATE INDEX idx_people_name ON people(name)",

    """CREATE TABLE credits (
        id INTEGER PRIMARY KEY,
        person_id INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
        media_type TEXT NOT NULL,            -- movie|tv_show|episode
        media_id INTEGER NOT NULL,
        role TEXT NOT NULL,                  -- actor|director|writer|producer|crew|guest_star
        character TEXT NOT NULL DEFAULT '',
        job TEXT NOT NULL DEFAULT '',
        sort_order INTEGER NOT NULL DEFAULT 0,
        UNIQUE (person_id, media_type, media_id, role, character, job)
    )""",
    "CREATE INDEX idx_credits_media ON credits(media_type, media_id)",
    "CREATE INDEX idx_credits_person ON credits(person_id)",

    # --- taxonomies -----------------------------------------------------------
    """CREATE TABLE genres (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL UNIQUE
    )""",
    """CREATE TABLE media_genres (
        media_type TEXT NOT NULL,            -- movie|tv_show
        media_id INTEGER NOT NULL,
        genre_id INTEGER NOT NULL REFERENCES genres(id) ON DELETE CASCADE,
        UNIQUE (media_type, media_id, genre_id)
    )""",
    "CREATE INDEX idx_media_genres_genre ON media_genres(genre_id)",
    """CREATE TABLE studios (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL UNIQUE
    )""",
    """CREATE TABLE media_studios (
        media_type TEXT NOT NULL,            -- movie|tv_show
        media_id INTEGER NOT NULL,
        studio_id INTEGER NOT NULL REFERENCES studios(id) ON DELETE CASCADE,
        UNIQUE (media_type, media_id, studio_id)
    )""",
    """CREATE TABLE networks (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL UNIQUE
    )""",
    """CREATE TABLE show_networks (
        tv_show_id INTEGER NOT NULL REFERENCES tv_shows(id) ON DELETE CASCADE,
        network_id INTEGER NOT NULL REFERENCES networks(id) ON DELETE CASCADE,
        UNIQUE (tv_show_id, network_id)
    )""",
    """CREATE TABLE tags (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL UNIQUE
    )""",
    """CREATE TABLE media_tags (
        media_type TEXT NOT NULL,
        media_id INTEGER NOT NULL,
        tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
        UNIQUE (media_type, media_id, tag_id)
    )""",

    # --- collections ------------------------------------------------------------
    """CREATE TABLE movie_collections (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        overview TEXT NOT NULL DEFAULT ''
    )""",
    """CREATE TABLE user_collections (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        description TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE collection_items (
        id INTEGER PRIMARY KEY,
        collection_id INTEGER NOT NULL REFERENCES user_collections(id) ON DELETE CASCADE,
        media_type TEXT NOT NULL,            -- movie|tv_show|artist|album
        media_id INTEGER NOT NULL,
        position INTEGER NOT NULL DEFAULT 0,
        added_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE (collection_id, media_type, media_id)
    )""",
    "CREATE INDEX idx_collection_items ON collection_items(collection_id)",

    # --- user lists (scoped to profile) --------------------------------------------
    """CREATE TABLE favorites (
        id INTEGER PRIMARY KEY,
        profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
        media_type TEXT NOT NULL,
        media_id INTEGER NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE (profile_id, media_type, media_id)
    )""",
    """CREATE TABLE watchlist (
        id INTEGER PRIMARY KEY,
        profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
        media_type TEXT NOT NULL,
        media_id INTEGER NOT NULL,
        added_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE (profile_id, media_type, media_id)
    )""",
    """CREATE TABLE user_ratings (
        id INTEGER PRIMARY KEY,
        profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
        media_type TEXT NOT NULL,
        media_id INTEGER NOT NULL,
        rating REAL NOT NULL,
        rated_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE (profile_id, media_type, media_id)
    )""",

    # --- playback -----------------------------------------------------------------
    """CREATE TABLE playback_history (
        id INTEGER PRIMARY KEY,
        profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
        media_file_id INTEGER REFERENCES media_files(id) ON DELETE SET NULL,
        media_type TEXT NOT NULL,
        media_id INTEGER NOT NULL,
        started_at TEXT NOT NULL DEFAULT (datetime('now')),
        finished_at TEXT,
        position_seconds REAL NOT NULL DEFAULT 0,
        duration_seconds REAL NOT NULL DEFAULT 0,
        completed INTEGER NOT NULL DEFAULT 0
    )""",
    "CREATE INDEX idx_playback_history_started ON playback_history(started_at DESC)",
    "CREATE INDEX idx_playback_history_media ON playback_history(media_type, media_id)",
    """CREATE TABLE playback_state (
        id INTEGER PRIMARY KEY,
        profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
        media_type TEXT NOT NULL,
        media_id INTEGER NOT NULL,
        media_file_id INTEGER REFERENCES media_files(id) ON DELETE SET NULL,
        position_seconds REAL NOT NULL DEFAULT 0,
        duration_seconds REAL NOT NULL DEFAULT 0,
        updated_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE (profile_id, media_type, media_id)
    )""",

    # --- music ------------------------------------------------------------------------
    """CREATE TABLE music_artists (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        sort_name TEXT NOT NULL DEFAULT '',
        biography TEXT NOT NULL DEFAULT '',
        disambiguation TEXT NOT NULL DEFAULT '',
        added_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    "CREATE INDEX idx_music_artists_name ON music_artists(name)",
    """CREATE TABLE music_albums (
        id INTEGER PRIMARY KEY,
        artist_id INTEGER NOT NULL REFERENCES music_artists(id) ON DELETE CASCADE,
        title TEXT NOT NULL,
        year INTEGER,
        release_date TEXT,
        track_count INTEGER NOT NULL DEFAULT 0,
        added_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    "CREATE INDEX idx_music_albums_artist ON music_albums(artist_id)",
    """CREATE TABLE music_tracks (
        id INTEGER PRIMARY KEY,
        album_id INTEGER NOT NULL REFERENCES music_albums(id) ON DELETE CASCADE,
        artist_id INTEGER NOT NULL REFERENCES music_artists(id) ON DELETE CASCADE,
        title TEXT NOT NULL,
        track_number INTEGER,
        disc_number INTEGER,
        duration_seconds INTEGER,
        added_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    "CREATE INDEX idx_music_tracks_album ON music_tracks(album_id)",
    """CREATE TABLE music_genres (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL UNIQUE
    )""",
    """CREATE TABLE album_genres (
        album_id INTEGER NOT NULL REFERENCES music_albums(id) ON DELETE CASCADE,
        genre_id INTEGER NOT NULL REFERENCES music_genres(id) ON DELETE CASCADE,
        UNIQUE (album_id, genre_id)
    )""",
    """CREATE TABLE artist_genres (
        artist_id INTEGER NOT NULL REFERENCES music_artists(id) ON DELETE CASCADE,
        genre_id INTEGER NOT NULL REFERENCES music_genres(id) ON DELETE CASCADE,
        UNIQUE (artist_id, genre_id)
    )""",
    """CREATE TABLE playlists (
        id INTEGER PRIMARY KEY,
        profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE (profile_id, name)
    )""",
    """CREATE TABLE playlist_tracks (
        id INTEGER PRIMARY KEY,
        playlist_id INTEGER NOT NULL REFERENCES playlists(id) ON DELETE CASCADE,
        track_id INTEGER NOT NULL REFERENCES music_tracks(id) ON DELETE CASCADE,
        position INTEGER NOT NULL DEFAULT 0,
        UNIQUE (playlist_id, track_id)
    )""",

    # --- provider / metadata infrastructure ----------------------------------------------
    """CREATE TABLE external_ids (
        id INTEGER PRIMARY KEY,
        media_type TEXT NOT NULL,
        media_id INTEGER NOT NULL,
        provider TEXT NOT NULL,
        value TEXT NOT NULL,
        UNIQUE (media_type, media_id, provider)
    )""",
    "CREATE INDEX idx_external_ids_value ON external_ids(provider, value)",
    """CREATE TABLE artwork (
        id INTEGER PRIMARY KEY,
        owner_type TEXT NOT NULL,            -- movie|tv_show|season|episode|person|artist|album
        owner_id INTEGER NOT NULL,
        kind TEXT NOT NULL,                  -- poster|backdrop|logo|profile|still|season_poster|album_cover|artist_banner
        source_url TEXT NOT NULL DEFAULT '',
        local_path TEXT NOT NULL DEFAULT '',
        width INTEGER NOT NULL DEFAULT 0,
        height INTEGER NOT NULL DEFAULT 0,
        downloaded_at TEXT,
        last_accessed TEXT,
        UNIQUE (owner_type, owner_id, kind, source_url)
    )""",
    "CREATE INDEX idx_artwork_owner ON artwork(owner_type, owner_id)",
    """CREATE TABLE metadata_cache (
        id INTEGER PRIMARY KEY,
        provider TEXT NOT NULL,
        object_type TEXT NOT NULL,           -- search:<kind> | detail:<kind> ...
        external_key TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        fetched_at TEXT NOT NULL DEFAULT (datetime('now')),
        expires_at TEXT NOT NULL,
        UNIQUE (provider, object_type, external_key)
    )""",
    """CREATE TABLE metadata_sources (
        id INTEGER PRIMARY KEY,
        media_type TEXT NOT NULL,            -- movie|tv_show|person|artist|album
        media_id INTEGER NOT NULL,
        provider TEXT NOT NULL,
        fetched_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE (media_type, media_id, provider)
    )""",

    # --- browser ------------------------------------------------------------------------------
    """CREATE TABLE browser_history (
        id INTEGER PRIMARY KEY,
        url TEXT NOT NULL,
        title TEXT NOT NULL DEFAULT '',
        visited_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    "CREATE INDEX idx_browser_history_time ON browser_history(visited_at DESC)",
    """CREATE TABLE bookmarks (
        id INTEGER PRIMARY KEY,
        title TEXT NOT NULL DEFAULT '',
        url TEXT NOT NULL UNIQUE,
        folder TEXT NOT NULL DEFAULT '',
        added_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE downloads (
        id INTEGER PRIMARY KEY,
        url TEXT NOT NULL,
        path TEXT NOT NULL,
        state TEXT NOT NULL DEFAULT 'running',
        bytes_total INTEGER NOT NULL DEFAULT 0,
        bytes_received INTEGER NOT NULL DEFAULT 0,
        mime_type TEXT NOT NULL DEFAULT '',
        started_at TEXT NOT NULL DEFAULT (datetime('now')),
        finished_at TEXT
    )""",

    # --- services / app config ------------------------------------------------------------------
    """CREATE TABLE service_accounts (
        id INTEGER PRIMARY KEY,
        service_id TEXT NOT NULL UNIQUE,
        config_json TEXT NOT NULL DEFAULT '{}',
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE application_settings (
        key TEXT PRIMARY KEY,
        value_json TEXT NOT NULL,
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
]
