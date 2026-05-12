from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import event
from app.config import get_settings
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
    # SQLite-specific: enable WAL mode for concurrency
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
)

# Enable WAL mode for SQLite
if "sqlite" in settings.database_url:
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    """FastAPI dependency — yields an async DB session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Create all tables and seed defaults on startup."""
    from app import models  # noqa: F401 — import so tables are registered
    import os
    os.makedirs("data", exist_ok=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database initialized")

    await _seed_defaults()


async def _seed_defaults():
    from app.models import User, Schema
    from app.services.auth import hash_password
    import uuid, json
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        existing = await session.execute(select(User).limit(1))
        if existing.scalar_one_or_none():
            return

        # ✅ STEP 1: create users
        admin = User(
            id=str(uuid.uuid4()),
            email="admin@docintel.ai",
            name="Jamie Rivera",
            password_hash=hash_password("Admin123!"),
            role="admin",
            department="Legal Ops",
            avatar_initials="JR",
        )

        reviewer = User(
            id=str(uuid.uuid4()),
            email="reviewer@docintel.ai",
            name="Alex Kim",
            password_hash=hash_password("Review123!"),
            role="reviewer",
            department="Finance Ops",
            avatar_initials="AK",
        )

        session.add_all([admin, reviewer])

        # 🔥 CRITICAL FIX — force insert BEFORE using FK
        await session.flush()

        # ✅ STEP 2: create schemas using valid FK
        schemas = [
            Schema(
                id=str(uuid.uuid4()),
                name="Contract Standard",
                doc_type="contract",
                version="2.1",
                status="active",
                definition=json.dumps({"fields": {}}),
                validation_rules=json.dumps([]),
                created_by=admin.id,
            ),
            Schema(
                id=str(uuid.uuid4()),
                name="Invoice",
                doc_type="invoice",
                version="1.3",
                status="active",
                definition=json.dumps({"fields": {}}),
                validation_rules=json.dumps([]),
                created_by=admin.id,
            ),
        ]

        session.add_all(schemas)

        # ✅ STEP 3: commit everything
        await session.commit()

        logger.info("Database seeded successfully")