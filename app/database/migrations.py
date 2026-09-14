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
        
        result = conn.execute(text("SELECT MAX(version) FROM schema_migrations"))
        current = result.scalar() or 0
        
        if current < 1:
            logger.info("Applying migration v1 - Creating all tables...")
            Base.metadata.create_all(bind=engine)
            conn.execute(text("INSERT INTO schema_migrations (version) VALUES (1)"))
            conn.commit()
            logger.info("Migration v1 applied successfully")
        
        logger.info(f"Database schema is up to date (version {current})")
