"""Tests for API-key authentication on the review-queue endpoints."""

import httpx
import pytest
import pytest_asyncio

from brm.db import get_session
from brm.main import app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def api_key():
    from brm.config import settings

    return settings.api_key


@pytest.fixture
def override_get_session(db_session):
    async def _override():
        yield db_session

    app.dependency_overrides[get_session] = _override
    yield
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(override_get_session):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_key_returns_401(client):
    """GET /review/queue with no X-API-Key header must return 401."""
    resp = await client.get("/review/queue")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_wrong_key_returns_401(client):
    """GET /review/queue with an incorrect key must return 401."""
    resp = await client.get("/review/queue", headers={"X-API-Key": "wrong-key"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_correct_key_returns_200(client, api_key):
    """GET /review/queue with the correct key must return 200."""
    resp = await client.get("/review/queue", headers={"X-API-Key": api_key})
    assert resp.status_code == 200
