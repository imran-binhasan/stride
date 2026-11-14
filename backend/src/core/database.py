"""Async Database engine, session maker and dependency injection."""

from collections.abc import AsyncGenerator
from uuid import uuid4

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool
from src.config import settings
from src.models.base import Base

# Build engine arguments depending on DB dialect
engine_kwargs = {"echo": settings.DATABASE_ECHO}

if "sqlite" in settings.DATABASE_URL:
    # SQLite does not support standard connection pooling parameters
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    if settings.DB_DISABLE_PREPARED_CACHE:
        # PgBouncer owns pooling. Both SQLAlchemy and asyncpg maintain caches.
        engine_kwargs["poolclass"] = NullPool
        engine_kwargs["connect_args"] = {
            "statement_cache_size": 0,
            "prepared_statement_cache_size": 0,
            "prepared_statement_name_func": lambda: f"__stride_{uuid4().hex}__",
        }
    else:
        engine_kwargs["pool_size"] = settings.DB_POOL_SIZE
        engine_kwargs["max_overflow"] = settings.DB_MAX_OVERFLOW
        engine_kwargs["pool_pre_ping"] = True

engine: AsyncEngine = create_async_engine(settings.DATABASE_URL, **engine_kwargs)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that provides an asynchronous database session per request."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
            from src.core.events import publish_changes

            await publish_changes(session)
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Create all tables in the database (used for initialization and test fixtures)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_db() -> None:
    """Drop all tables in the database (used for test teardown)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
