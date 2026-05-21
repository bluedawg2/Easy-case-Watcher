"""Pytest fixtures for the Bankruptcy Rule Monitor test suite.

Key design (review finding #18 — exact async transaction strategy):
- All DB tests point at the `brm_test` Postgres database.
- The `db_session` fixture wraps each test in a SAVEPOINT-rollback cycle so
  application code can call `session.commit()` normally while the outer
  transaction is always rolled back at test teardown.
- This is the standard SQLAlchemy "join an external transaction" recipe,
  adapted for async engines.

Test-DB creation mechanism (single, authoritative):
- `brm_test` is created by `scripts/init-test-db.sql` mounted into
  `/docker-entrypoint-initdb.d/` of the `db` compose service.
- There is no POSTGRES_DB override and no second compose service.

Windows note (psycopg 3 compatibility):
- psycopg 3 async requires SelectorEventLoop; Windows defaults to
  ProactorEventLoop. We patch asyncio at import time so all async test
  code runs on the correct event loop.
"""

import asyncio
import selectors
import sys
from typing import AsyncGenerator

import pytest
import pytest_asyncio
import respx
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from brm.config import settings

# ---------------------------------------------------------------------------
# Windows: ensure psycopg-compatible event loop for all async tests
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def event_loop_policy():
    """Override pytest-asyncio's default event loop policy.

    psycopg 3 async cannot use Windows' default ProactorEventLoop.
    Return a policy that creates SelectorEventLoops so that all async
    test coroutines (and the engine connections they open) work correctly.
    On non-Windows platforms this fixture is a no-op (returns the default).
    """
    if sys.platform == "win32":

        class SelectSelectorPolicy(asyncio.DefaultEventLoopPolicy):
            def new_event_loop(self):
                return asyncio.SelectorEventLoop(selectors.SelectSelector())

        return SelectSelectorPolicy()
    return asyncio.DefaultEventLoopPolicy()

# ---------------------------------------------------------------------------
# Test-database URL — swap the database name to `brm_test`
# ---------------------------------------------------------------------------

# Replace only the database name (the last path component), not the username.
# The URL is: postgresql+psycopg://brm:brm@localhost:5432/brm
# We want:    postgresql+psycopg://brm:brm@localhost:5432/brm_test
_test_db_url = settings.database_url.rstrip("/").rsplit("/", 1)[0] + "/brm_test"
_test_engine = create_async_engine(
    _test_db_url,
    echo=False,
    pool_pre_ping=True,
)


# ---------------------------------------------------------------------------
# Async session fixture with SAVEPOINT-rollback isolation
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture()
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Async session fixture that rolls back every test.

    Pattern (SQLAlchemy docs — "joining an external transaction in tests"):
    1. Open an AsyncConnection and begin an outer transaction.
    2. Create an AsyncSession *bound to that connection* (not to the engine),
       so all session work shares the same underlying DBAPI connection.
    3. Open a SAVEPOINT (begin_nested) — this is what the application
       "commits" to when it calls session.commit().
    4. Register a session event that re-opens a new SAVEPOINT after each
       SAVEPOINT ends (to handle applications that commit multiple times).
    5. Yield the session to the test.
    6. Teardown: close the session, roll back the outer transaction, and
       close the connection — leaving the DB in a pristine state.
    """
    async with _test_engine.connect() as conn:
        await conn.begin()  # outer transaction

        session_factory = async_sessionmaker(
            bind=conn,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        session = session_factory()

        await session.begin_nested()  # open initial SAVEPOINT

        # Re-open a SAVEPOINT after every SAVEPOINT ends so that multiple
        # commits within a single test each land inside a new SAVEPOINT and
        # the outer transaction remains open.
        @event.listens_for(session.sync_session, "after_transaction_end")
        def restart_savepoint(sess, transaction):
            if transaction.nested and not transaction._parent.nested:
                sess.begin_nested()

        yield session

        await session.close()
        await conn.rollback()  # discard everything — DB stays clean


# ---------------------------------------------------------------------------
# respx mock client fixture (stub — used by plans 01-02 through 01-05)
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_http():
    """respx mock router for deterministic, offline HTTP replay.

    Use this fixture to intercept httpx requests in fetch-adapter tests.

    Example::

        def test_fetch(mock_http, db_session):
            mock_http.get("https://example.com/feed").mock(
                return_value=httpx.Response(200, content=FIXTURE_XML)
            )
            ...
    """
    with respx.mock(assert_all_called=False) as router:
        yield router
