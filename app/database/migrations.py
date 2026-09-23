from sqlalchemy import text
from app.database.models import Base
from app.logging import get_logger

logger = get_logger("database.migrations")


def run_migrations(engine):
    logger.info("Running database migrations...")

    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.commit()

        result = conn.execute(
            text("SELECT MAX(version) FROM schema_migrations")
        )
        current = result.scalar() or 0

        if current < 1:
            logger.info("Applying migration v1 - Creating all tables...")
            Base.metadata.create_all(bind=engine)

            conn.execute(
                text(
                    "INSERT INTO schema_migrations (version) "
                    "VALUES (1)"
                )
            )
            conn.commit()

            current = 1
            logger.info("Migration v1 applied successfully")

        if current < 2:
            logger.info(
                "Applying migration v2 - Updating media_items schema..."
            )

            columns = {
                row[1]
                for row in conn.execute(
                    text("PRAGMA table_info(media_items)")
                ).fetchall()
            }

            additions = [
                (
                    "library_id",
                    "INTEGER REFERENCES libraries(id)"
                ),
                ("original_title", "VARCHAR(500)"),
                ("description", "TEXT"),
                ("release_date", "VARCHAR(50)"),
                ("runtime", "INTEGER"),
                ("votes", "INTEGER DEFAULT 0"),
                ("status", "VARCHAR(9)"),
                ("updated_at", "DATETIME"),
                ("scanned_at", "DATETIME"),
            ]

            for column_name, column_definition in additions:
                if column_name not in columns:
                    logger.info(
                        "Adding media_items.%s",
                        column_name,
                    )
                    conn.execute(
                        text(
                            f"ALTER TABLE media_items "
                            f"ADD COLUMN {column_name} "
                            f"{column_definition}"
                        )
                    )

            conn.execute(
                text(
                    "INSERT INTO schema_migrations (version) "
                    "VALUES (2)"
                )
            )
            conn.commit()

            current = 2
            logger.info("Migration v2 applied successfully")

        if current < 3:
            logger.info(
                "Applying migration v3 - Adding TV episode metadata..."
            )

            columns = {
                row[1]
                for row in conn.execute(
                    text("PRAGMA table_info(media_items)")
                ).fetchall()
            }

            additions = [
                ("season_number", "INTEGER"),
                ("episode_number", "INTEGER"),
                ("episode_title", "VARCHAR(500)"),
            ]

            for column_name, column_definition in additions:
                if column_name not in columns:
                    logger.info(
                        "Adding media_items.%s",
                        column_name,
                    )
                    conn.execute(
                        text(
                            f"ALTER TABLE media_items "
                            f"ADD COLUMN {column_name} "
                            f"{column_definition}"
                        )
                    )

            conn.execute(
                text(
                    "INSERT INTO schema_migrations (version) "
                    "VALUES (3)"
                )
            )
            conn.commit()

            current = 3
            logger.info("Migration v3 applied successfully")

        if current < 4:
            logger.info(
                "Applying migration v4 - Adding person metadata..."
            )

            columns = {
                row[1]
                for row in conn.execute(
                    text("PRAGMA table_info(people)")
                ).fetchall()
            }

            additions = [
                ("tmdb_id", "INTEGER"),
                ("imdb_id", "VARCHAR(50)"),
                ("known_for_department", "VARCHAR(100)"),
                ("birthday", "VARCHAR(20)"),
                ("deathday", "VARCHAR(20)"),
                ("place_of_birth", "VARCHAR(255)"),
                ("popularity", "FLOAT"),
            ]

            for column_name, column_definition in additions:
                if column_name not in columns:
                    logger.info(
                        "Adding people.%s",
                        column_name,
                    )
                    conn.execute(
                        text(
                            f"ALTER TABLE people "
                            f"ADD COLUMN {column_name} "
                            f"{column_definition}"
                        )
                    )

            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS "
                    "ix_people_tmdb_id ON people (tmdb_id)"
                )
            )

            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS "
                    "ix_people_imdb_id ON people (imdb_id)"
                )
            )

            conn.execute(
                text(
                    "INSERT INTO schema_migrations (version) "
                    "VALUES (4)"
                )
            )
            conn.commit()

            current = 4
            logger.info("Migration v4 applied successfully")

        if current < 5:
            logger.info(
                "Applying migration v5 - Adding trailer metadata..."
            )

            columns = {
                row[1]
                for row in conn.execute(
                    text("PRAGMA table_info(media_items)")
                ).fetchall()
            }

            additions = [
                ("trailer_key", "VARCHAR(100)"),
                ("trailer_name", "VARCHAR(500)"),
                ("trailer_site", "VARCHAR(50)"),
                ("trailer_type", "VARCHAR(50)"),
                ("trailer_official", "BOOLEAN DEFAULT 0"),
            ]

            for column_name, column_definition in additions:
                if column_name not in columns:
                    logger.info(
                        "Adding media_items.%s",
                        column_name,
                    )
                    conn.execute(
                        text(
                            f"ALTER TABLE media_items "
                            f"ADD COLUMN {column_name} "
                            f"{column_definition}"
                        )
                    )

            conn.execute(
                text(
                    "INSERT INTO schema_migrations (version) "
                    "VALUES (5)"
                )
            )
            conn.commit()

            current = 5
            logger.info("Migration v5 applied successfully")

        logger.info(
            "Database schema is up to date (version %s)",
            current,
        )
