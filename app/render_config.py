"""Convert hosted Postgres URLs (Render, Neon, ...) to asyncpg format."""
import os
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

def patch_database_url():
    db_url = os.getenv("DATABASE_URL", "")
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif db_url.startswith("postgresql://") and "+asyncpg" not in db_url:
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    # asyncpg takes ssl=..., not libpq's sslmode=..., and rejects channel_binding
    if db_url.startswith("postgresql+asyncpg://"):
        parts = urlsplit(db_url)
        query = []
        for key, value in parse_qsl(parts.query):
            if key == "sslmode":
                query.append(("ssl", value))
            elif key != "channel_binding":
                query.append((key, value))
        db_url = urlunsplit(parts._replace(query=urlencode(query)))

    if db_url:
        os.environ["DATABASE_URL"] = db_url

patch_database_url()
