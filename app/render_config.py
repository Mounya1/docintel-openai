"""Convert Render DATABASE_URL to asyncpg format."""
import os

def patch_database_url():
    db_url = os.getenv("DATABASE_URL", "")
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
        os.environ["DATABASE_URL"] = db_url
    elif db_url.startswith("postgresql://") and "+asyncpg" not in db_url:
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        os.environ["DATABASE_URL"] = db_url

patch_database_url()
