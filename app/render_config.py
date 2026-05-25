"""
Production configuration helper for Render deployment.
Converts Render's DATABASE_URL (postgresql://) to asyncpg format (postgresql+asyncpg://).
"""
import os


def patch_database_url():
    """Convert standard PostgreSQL URL to asyncpg format for SQLAlchemy."""
    db_url = os.getenv("DATABASE_URL", "")
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
        os.environ["DATABASE_URL"] = db_url
    elif db_url.startswith("postgresql://") and "+asyncpg" not in db_url:
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        os.environ["DATABASE_URL"] = db_url


# Run on import
patch_database_url()