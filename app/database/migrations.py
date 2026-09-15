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

        logger.info(
            "Database schema is up to date (version %s)",
            current,
        )
