"""Tests for the pull-delivery API endpoint GET /changes."""

from datetime import UTC, datetime

import httpx
import pytest
import pytest_asyncio

from brm.db import get_session
from brm.lifecycle import (
    STATUS_DETECTED,
    STATUS_IN_REVIEW,
    STATUS_PROCESSED,
    STATUS_REJECTED,
    STATUS_SUMMARY_FAILED,
    STATUS_VERIFIED,
)
from brm.main import app
from brm.models.change import Change
from brm.models.snapshot import Snapshot
from brm.models.source import Source

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
# DB seeding helpers
# ---------------------------------------------------------------------------


async def seed_source(session) -> Source:
    src = Source(
        jurisdiction="national",
        layer="FRBP",
        feed_url="https://www.uscourts.gov/news/rss",
        ingestion_method="rss",
        adapter_ref="brm.ingest.rss.FrbpSourceAdapter",
        polling_cadence="daily",
        health_status="healthy",
    )
    session.add(src)
    await session.flush()
    return src


async def seed_snapshot(session, source_id: int, version: int = 1) -> Snapshot:
    snap = Snapshot(
        source_id=source_id,
        content="Some rule text",
        content_hash=f"abc{version}",
        version=version,
        fetched_at=datetime.now(UTC),
    )
    session.add(snap)
    await session.flush()
    return snap


async def seed_change(
    session,
    source_id: int,
    snapshot_id: int,
    status: str = STATUS_VERIFIED,
    updated_at: datetime | None = None,
    effective_date=None,
    summary: dict | None = None,
) -> Change:
    now = datetime.now(UTC)
    if summary is None and status == STATUS_VERIFIED:
        summary = {
            "headline": "Test verified change",
            "what_changed": "Something changed",
            "where": "Rule 1007",
            "to_whom": "Debtors",
            "for_what_cases": "Chapter 7",
        }
    change = Change(
        source_id=source_id,
        current_snapshot_id=snapshot_id,
        status=status,
        detected_at=now,
        updated_at=updated_at if updated_at is not None else now,
        diff_text="-old\n+new\n",
        summary=summary,
        not_legal_advice_label="Informational summary — not legal advice.",
        effective_date=effective_date,
    )
    session.add(change)
    await session.flush()
    return change


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_only_verified(client, db_session, api_key):
    """GET /changes returns only verified changes."""
    src = await seed_source(db_session)

    # One change per status
    statuses = [
        STATUS_DETECTED,
        STATUS_PROCESSED,
        STATUS_IN_REVIEW,
        STATUS_SUMMARY_FAILED,
        STATUS_REJECTED,
        STATUS_VERIFIED,
    ]
    for i, status in enumerate(statuses):
        snap = await seed_snapshot(db_session, src.id, version=i + 1)
        summary = (
            {
                "headline": f"Change {i}",
                "what_changed": "x",
                "where": "y",
                "to_whom": "z",
                "for_what_cases": "w",
            }
            if status not in (STATUS_DETECTED, STATUS_SUMMARY_FAILED)
            else None
        )
        await seed_change(db_session, src.id, snap.id, status=status, summary=summary)

    resp = await client.get("/changes", headers={"X-API-Key": api_key})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["status"] == STATUS_VERIFIED


@pytest.mark.asyncio
async def test_since_cursor(client, db_session, api_key):
    """GET /changes?since filters by updated_at strictly greater than since."""
    src = await seed_source(db_session)
    snap1 = await seed_snapshot(db_session, src.id, version=1)
    snap2 = await seed_snapshot(db_session, src.id, version=2)

    t1 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    t2 = datetime(2026, 1, 2, 12, 0, 0, tzinfo=UTC)

    c1 = await seed_change(db_session, src.id, snap1.id, updated_at=t1)
    c2 = await seed_change(db_session, src.id, snap2.id, updated_at=t2)

    # since=t1: only the change at t2 (strictly greater)
    resp = await client.get(
        "/changes",
        params={"since": t1.isoformat()},
        headers={"X-API-Key": api_key},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["id"] == c2.id

    # since=t2: empty — nothing strictly after t2
    resp = await client.get(
        "/changes",
        params={"since": t2.isoformat()},
        headers={"X-API-Key": api_key},
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_stable_order(client, db_session, api_key):
    """GET /changes returns results ordered by updated_at then id."""
    src = await seed_source(db_session)

    t1 = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)
    t2 = datetime(2026, 1, 2, 10, 0, 0, tzinfo=UTC)
    t3 = datetime(2026, 1, 3, 10, 0, 0, tzinfo=UTC)

    snap1 = await seed_snapshot(db_session, src.id, version=1)
    snap2 = await seed_snapshot(db_session, src.id, version=2)
    snap3 = await seed_snapshot(db_session, src.id, version=3)

    c1 = await seed_change(db_session, src.id, snap1.id, updated_at=t1)
    c2 = await seed_change(db_session, src.id, snap2.id, updated_at=t2)
    c3 = await seed_change(db_session, src.id, snap3.id, updated_at=t3)

    resp = await client.get("/changes", headers={"X-API-Key": api_key})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3
    ids = [item["id"] for item in data]
    assert ids == [c1.id, c2.id, c3.id]


@pytest.mark.asyncio
async def test_auth_required(client):
    """GET /changes with no API key returns 401."""
    resp = await client.get("/changes")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_change_out_shape(client, db_session, api_key):
    """ChangeOut includes all required fields."""
    src = await seed_source(db_session)
    snap = await seed_snapshot(db_session, src.id)
    t = datetime(2026, 5, 1, 12, 0, 0, tzinfo=UTC)
    change = await seed_change(
        db_session,
        src.id,
        snap.id,
        updated_at=t,
        effective_date=None,
    )

    resp = await client.get("/changes", headers={"X-API-Key": api_key})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    item = data[0]
    # Verify required fields are present
    assert "summary" in item
    assert "effective_date" in item
    assert "detected_at" in item
    assert "updated_at" in item
    assert "source_layer" in item
    assert "source_url" in item
    assert item["source_layer"] == "FRBP"
    assert item["source_url"] == "https://www.uscourts.gov/news/rss"
    assert item["summary"]["headline"] == "Test verified change"
