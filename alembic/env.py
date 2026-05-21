"""Alembic migration environment — async mode with SQLAlchemy 2.0.

The database URL is read from brm.config.Settings (pydantic-settings) so it
picks up the .env file automatically.  Models are imported before `run_migrations`
is called so that Base.metadata contains all table definitions.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

# ---------------------------------------------------------------------------
# Load application metadata and settings
# ---------------------------------------------------------------------------

# Import models here so Alembic can see them in metadata for autogenerate.
from brm.config import settings
from brm.db import Base

# noqa: F401 — ensure all model tables are registered on Base.metadata
import brm.models  # noqa: F401

# ---------------------------------------------------------------------------
# Alembic config
# ---------------------------------------------------------------------------

config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


# ---------------------------------------------------------------------------
# Migration runners
# ---------------------------------------------------------------------------


def run_migrations_offline() -> None:
    """Emit SQL to stdout without a live database connection.

    Useful for generating migration scripts to inspect or apply manually.
    """
    url = settings.database_url
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations against a live database using an async engine."""
    connectable = create_async_engine(settings.database_url)

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
