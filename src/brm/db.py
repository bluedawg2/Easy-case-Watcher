"""Async database engine, session factory, and ORM base.

Design rules (from RESEARCH Pitfall 6):
- One AsyncSession per request/operation — never share a session.
- Use create_async_engine with the psycopg 3 async driver (postgresql+psycopg://).
- No module-level shared session objects.
- expire_on_commit=False so objects remain usable after a commit without an
  extra round-trip to reload them.
"""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from brm.config import settings

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,  # check connections are alive before use
)

# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------

SessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# ---------------------------------------------------------------------------
# ORM declarative base — all models inherit from this
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# FastAPI dependency — yields one AsyncSession per request
# ---------------------------------------------------------------------------


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: open a session, yield it, close it.

    Usage::

        @router.get("/")
        async def handler(session: AsyncSession = Depends(get_session)):
            ...
    """
    async with SessionLocal() as session:
        yield session
