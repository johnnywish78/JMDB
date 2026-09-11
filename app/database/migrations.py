from app.database.connection import get_connection

SCHEMA_VERSION = 2


def migrate() -> None:
    with get_connection() as db:
        row = db.execute(
            "SELECT version FROM schema_version LIMIT 1"
        ).fetchone()

        current = int(row["version"]) if row else 0

        if current > SCHEMA_VERSION:
            raise RuntimeError(
                f"Database schema {current} is newer than application schema {SCHEMA_VERSION}"
            )

        if current < 2:
            columns = {
                row["name"]
                for row in db.execute(
                    "PRAGMA table_info(media_items)"
                ).fetchall()
            }

            if "sort_title" not in columns:
                db.execute(
                    "ALTER TABLE media_items ADD COLUMN sort_title TEXT"
                )

            db.executescript("""
                CREATE TABLE IF NOT EXISTS people (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    sort_name TEXT,
                    biography TEXT,
                    birthday TEXT,
                    deathday TEXT,
                    place_of_birth TEXT,
                    profile_path TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS media_people (
                    media_id INTEGER NOT NULL
                        REFERENCES media_items(id) ON DELETE CASCADE,
                    person_id INTEGER NOT NULL
                        REFERENCES people(id) ON DELETE CASCADE,
                    role TEXT NOT NULL,
                    character_name TEXT,
                    department TEXT,
                    job TEXT,
                    credit_order INTEGER,
                    PRIMARY KEY (
                        media_id, person_id, role,
                        character_name, job
                    )
                );

                CREATE INDEX IF NOT EXISTS idx_media_people_person
                    ON media_people(person_id);

                CREATE TABLE IF NOT EXISTS genres (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE
                );

                CREATE TABLE IF NOT EXISTS media_genres (
                    media_id INTEGER NOT NULL
                        REFERENCES media_items(id) ON DELETE CASCADE,
                    genre_id INTEGER NOT NULL
                        REFERENCES genres(id) ON DELETE CASCADE,
                    PRIMARY KEY(media_id, genre_id)
                );

                CREATE TABLE IF NOT EXISTS seasons (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    media_id INTEGER NOT NULL
                        REFERENCES media_items(id) ON DELETE CASCADE,
                    season_number INTEGER NOT NULL,
                    title TEXT,
                    overview TEXT,
                    air_date TEXT,
                    episode_count INTEGER,
                    poster_path TEXT,
                    UNIQUE(media_id, season_number)
                );

                CREATE TABLE IF NOT EXISTS episodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    season_id INTEGER NOT NULL
                        REFERENCES seasons(id) ON DELETE CASCADE,
                    media_id INTEGER
                        REFERENCES media_items(id) ON DELETE SET NULL,
                    episode_number INTEGER NOT NULL,
                    title TEXT,
                    overview TEXT,
                    air_date TEXT,
                    runtime_minutes INTEGER,
                    still_path TEXT,
                    UNIQUE(season_id, episode_number)
                );

                CREATE INDEX IF NOT EXISTS idx_episodes_media
                    ON episodes(media_id);

                CREATE TABLE IF NOT EXISTS external_ids (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    media_id INTEGER
                        REFERENCES media_items(id) ON DELETE CASCADE,
                    person_id INTEGER
                        REFERENCES people(id) ON DELETE CASCADE,
                    provider TEXT NOT NULL,
                    external_type TEXT NOT NULL DEFAULT 'id',
                    external_id TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    CHECK (
                        (media_id IS NOT NULL) !=
                        (person_id IS NOT NULL)
                    ),
                    UNIQUE(provider, external_type, external_id),
                    UNIQUE(media_id, provider, external_type)
                );

                CREATE INDEX IF NOT EXISTS idx_external_ids_media
                    ON external_ids(media_id);

                CREATE INDEX IF NOT EXISTS idx_external_ids_person
                    ON external_ids(person_id);

                CREATE TABLE IF NOT EXISTS metadata (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    media_id INTEGER NOT NULL
                        REFERENCES media_items(id) ON DELETE CASCADE,
                    provider TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    fetched_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    expires_at TEXT,
                    UNIQUE(media_id, provider)
                );

                CREATE TABLE IF NOT EXISTS artwork (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    media_id INTEGER
                        REFERENCES media_items(id) ON DELETE CASCADE,
                    person_id INTEGER
                        REFERENCES people(id) ON DELETE CASCADE,
                    provider TEXT,
                    artwork_type TEXT NOT NULL,
                    remote_url TEXT,
                    local_path TEXT,
                    width INTEGER,
                    height INTEGER,
                    language TEXT,
                    is_primary INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    CHECK (
                        (media_id IS NOT NULL) !=
                        (person_id IS NOT NULL)
                    )
                );

                CREATE INDEX IF NOT EXISTS idx_artwork_media
                    ON artwork(media_id);

                CREATE TABLE IF NOT EXISTS collections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT,
                    collection_type TEXT NOT NULL DEFAULT 'custom',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS collection_items (
                    collection_id INTEGER NOT NULL
                        REFERENCES collections(id) ON DELETE CASCADE,
                    media_id INTEGER NOT NULL
                        REFERENCES media_items(id) ON DELETE CASCADE,
                    position INTEGER NOT NULL DEFAULT 0,
                    added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(collection_id, media_id)
                );

                CREATE TABLE IF NOT EXISTS watch_progress (
                    media_id INTEGER PRIMARY KEY
                        REFERENCES media_items(id) ON DELETE CASCADE,
                    file_id INTEGER
                        REFERENCES media_files(id) ON DELETE SET NULL,
                    position_seconds REAL NOT NULL DEFAULT 0,
                    duration_seconds REAL,
                    completed INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS playback_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    media_id INTEGER NOT NULL
                        REFERENCES media_items(id) ON DELETE CASCADE,
                    file_id INTEGER
                        REFERENCES media_files(id) ON DELETE SET NULL,
                    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    ended_at TEXT,
                    position_seconds REAL,
                    duration_seconds REAL,
                    player TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_playback_history_media
                    ON playback_history(media_id);

                CREATE TABLE IF NOT EXISTS services (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    service_type TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS service_credentials (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    service_id INTEGER NOT NULL
                        REFERENCES services(id) ON DELETE CASCADE,
                    key_name TEXT NOT NULL,
                    encrypted_value TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(service_id, key_name)
                );

                CREATE TABLE IF NOT EXISTS service_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    service_id INTEGER NOT NULL
                        REFERENCES services(id) ON DELETE CASCADE,
                    cache_key TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    expires_at TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(service_id, cache_key)
                );

                CREATE TABLE IF NOT EXISTS downloads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL,
                    filename TEXT,
                    path TEXT,
                    state TEXT NOT NULL DEFAULT 'pending',
                    bytes_received INTEGER NOT NULL DEFAULT 0,
                    total_bytes INTEGER,
                    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    completed_at TEXT,
                    error TEXT
                );

                UPDATE media_items
                SET sort_title = title
                WHERE sort_title IS NULL;

                UPDATE schema_version
                SET version = 2;
            """)


if __name__ == "__main__":
    migrate()
    print("Schema migration completed.")
