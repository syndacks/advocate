"""Async database engine and session helpers."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from advocate.config import settings

async_engine = create_async_engine(settings.database_url, pool_pre_ping=True)
AsyncSessionFactory = async_sessionmaker(async_engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncIterator[AsyncSession]:
    """Yield an async SQLAlchemy session for FastAPI dependencies or tasks."""
    async with AsyncSessionFactory() as session:
        yield session
