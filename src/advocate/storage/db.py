"""Async database engine and session helpers."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from advocate.config import settings

engine_kwargs: dict[str, object] = {"pool_pre_ping": True}
if settings.app_env == "test":
    engine_kwargs["poolclass"] = NullPool

async_engine = create_async_engine(settings.database_url, **engine_kwargs)
AsyncSessionFactory = async_sessionmaker(async_engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncIterator[AsyncSession]:
    """Yield an async SQLAlchemy session for FastAPI dependencies or tasks."""
    async with AsyncSessionFactory() as session:
        yield session
