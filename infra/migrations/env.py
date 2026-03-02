"""Alembic async migration environment.

Uses SQLAlchemy's async engine with asyncpg, bridged to Alembic's synchronous
runner via run_sync. The database URL is read from the environment so that
Alembic can run without importing application settings.
"""

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from advocate.storage.orm import Base

# Alembic Config object — available during real Alembic runs, absent in plain imports.
config = getattr(context, "config", None)

# Set up Python logging from the alembic.ini [loggers] section
if config is not None and config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Inject the real database URL from settings (overrides alembic.ini placeholder).
# We read DATABASE_URL directly from the environment here to avoid importing
# the full settings module at migration time (which would require all env vars).
_database_url = os.environ.get("DATABASE_URL")
if config is not None and _database_url:
    config.set_main_option("sqlalchemy.url", _database_url)

# ORM metadata for autogenerate support.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (no live DB connection)."""
    if config is None:
        raise RuntimeError("Alembic config is not available outside a migration context")
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations against a live async engine."""
    if config is None:
        raise RuntimeError("Alembic config is not available outside a migration context")
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode using the async engine."""
    asyncio.run(run_async_migrations())


try:
    is_offline_mode = context.is_offline_mode()
except NameError:
    is_offline_mode = None

if is_offline_mode is True:
    run_migrations_offline()
elif is_offline_mode is False:
    run_migrations_online()
