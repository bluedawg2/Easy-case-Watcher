"""Tests for the review-queue API endpoints."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import pytest_asyncio

from brm.db import get_session
from brm.lifecycle import (
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
        content_hash="abc123",
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
    status: str = STATUS_PROCESSED,
    diff_text: str | None = "-old\n+new\n",
    summary: dict | None = None,
    summary_error: str | None = None,
) -> Change:
    now = datetime.now(UTC)
    if summary is None and status not in (STATUS_SUMMARY_FAILED,):
        summary = {
            "headline": "Test rule change",
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
        updated_at=now,
        diff_text=diff_text,
        summary=summary,
        summary_error=summary_error,
        not_legal_advice_label="Informational summary — not legal advice.",
    )
    session.add(change)
    await session.flush()
    return change


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_queue_excludes_verified_rejected(client, db_session, api_key):
    """GET /review/queue returns only processed/in_review/summary_failed changes."""
    src = await seed_source(db_session)
    snap = await seed_snapshot(db_session, src.id)

    # Seed one change per status
    statuses = [
        STATUS_PROCESSED,
        STATUS_IN_REVIEW,
        STATUS_SUMMARY_FAILED,
        STATUS_VERIFIED,
        STATUS_REJECTED,
    ]
    change_ids = []
    for i, status in enumerate(statuses):
        c = await seed_change(
            db_session,
            src.id,
            snap.id,
            status=status,
            summary=None if status == STATUS_SUMMARY_FAILED else {
                "headline": f"Change {i}",
                "what_changed": "x",
                "where": "y",
                "to_whom": "z",
                "for_what_cases": "w",
            },
            summary_error="err" if status == STATUS_SUMMARY_FAILED else None,
        )
        change_ids.append((status, c.id))

    resp = await client.get("/review/queue", headers={"X-API-Key": api_key})
    assert resp.status_code == 200
    data = resp.json()
    returned_statuses = {item["status"] for item in data}
    assert returned_statuses <= {STATUS_PROCESSED, STATUS_IN_REVIEW, STATUS_SUMMARY_FAILED}
    assert STATUS_VERIFIED not in returned_statuses
    assert STATUS_REJECTED not in returned_statuses
    assert len(data) == 3


@pytest.mark.asyncio
async def test_approve_records_dates(client, db_session, api_key):
    """POST /review/{id}/approve sets status=verified and effective_date.

    Approve requires in_review status (lifecycle: in_review → verified).
    """
    src = await seed_source(db_session)
    snap = await seed_snapshot(db_session, src.id)
    change = await seed_change(db_session, src.id, snap.id, status=STATUS_IN_REVIEW)
    original_detected_at = change.detected_at

    resp = await client.post(
        f"/review/{change.id}/approve",
        json={"effective_date": "2026-12-01", "reviewer_name": "Alice"},
        headers={"X-API-Key": api_key},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == STATUS_VERIFIED
    assert data["effective_date"] == "2026-12-01"
    # detected_at should be unchanged
    from datetime import timezone
    detected = datetime.fromisoformat(data["detected_at"])
    assert detected.replace(tzinfo=None) == original_detected_at.replace(tzinfo=None)


@pytest.mark.asyncio
async def test_approve_missing_effective_date_returns_422(client, db_session, api_key):
    """POST /review/{id}/approve without effective_date returns 422."""
    src = await seed_source(db_session)
    snap = await seed_snapshot(db_session, src.id)
    change = await seed_change(db_session, src.id, snap.id, status=STATUS_IN_REVIEW)

    resp = await client.post(
        f"/review/{change.id}/approve",
        json={"reviewer_name": "Alice"},
        headers={"X-API-Key": api_key},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_edit_replaces_summary(client, db_session, api_key):
    """POST /review/{id}/edit replaces summary and sets status=in_review."""
    src = await seed_source(db_session)
    snap = await seed_snapshot(db_session, src.id)
    change = await seed_change(db_session, src.id, snap.id, status=STATUS_PROCESSED)

    new_summary = {
        "headline": "Updated headline",
        "what_changed": "Updated what",
        "where": "Updated where",
        "to_whom": "Updated to_whom",
        "for_what_cases": "Updated for_what_cases",
    }
    resp = await client.post(
        f"/review/{change.id}/edit",
        json={"summary": new_summary, "reviewer_name": "Bob"},
        headers={"X-API-Key": api_key},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == STATUS_IN_REVIEW
    assert data["summary"]["headline"] == "Updated headline"


@pytest.mark.asyncio
async def test_edit_re_edit_allowed(client, db_session, api_key):
    """POST /review/{id}/edit from in_review stays in_review (self-loop)."""
    src = await seed_source(db_session)
    snap = await seed_snapshot(db_session, src.id)
    change = await seed_change(db_session, src.id, snap.id, status=STATUS_IN_REVIEW)

    new_summary = {
        "headline": "Re-edited headline",
        "what_changed": "x",
        "where": "y",
        "to_whom": "z",
        "for_what_cases": "w",
    }
    resp = await client.post(
        f"/review/{change.id}/edit",
        json={"summary": new_summary, "reviewer_name": "Bob"},
        headers={"X-API-Key": api_key},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == STATUS_IN_REVIEW


@pytest.mark.asyncio
async def test_reject(client, db_session, api_key):
    """POST /review/{id}/reject sets status=rejected.

    Reject requires in_review status (lifecycle: in_review → rejected).
    """
    src = await seed_source(db_session)
    snap = await seed_snapshot(db_session, src.id)
    change = await seed_change(db_session, src.id, snap.id, status=STATUS_IN_REVIEW)

    resp = await client.post(
        f"/review/{change.id}/reject",
        json={"reviewer_name": "Carol"},
        headers={"X-API-Key": api_key},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == STATUS_REJECTED


@pytest.mark.asyncio
async def test_illegal_transition_returns_409(client, db_session, api_key):
    """POST approve on a verified change returns 409 (illegal transition)."""
    src = await seed_source(db_session)
    snap = await seed_snapshot(db_session, src.id)
    change = await seed_change(db_session, src.id, snap.id, status=STATUS_VERIFIED)

    resp = await client.post(
        f"/review/{change.id}/approve",
        json={"effective_date": "2026-12-01", "reviewer_name": "Alice"},
        headers={"X-API-Key": api_key},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_retry_summary_on_summary_failed(client, db_session, api_key):
    """POST /review/{id}/retry-summary calls run_summarize and returns updated change."""
    src = await seed_source(db_session)
    snap = await seed_snapshot(db_session, src.id)
    change = await seed_change(
        db_session,
        src.id,
        snap.id,
        status=STATUS_SUMMARY_FAILED,
        diff_text="-old\n+new\n",
        summary=None,
        summary_error="TimeoutError: API timeout retry_count=1",
    )

    async def fake_run_summarize(session, change_obj):
        change_obj.status = STATUS_PROCESSED
        change_obj.summary = {
            "headline": "Retried headline",
            "what_changed": "x",
            "where": "y",
            "to_whom": "z",
            "for_what_cases": "w",
        }
        change_obj.summary_error = None
        return change_obj

    with patch("brm.api.review.run_summarize", new_callable=AsyncMock) as mock_rs:
        mock_rs.side_effect = fake_run_summarize
        resp = await client.post(
            f"/review/{change.id}/retry-summary",
            headers={"X-API-Key": api_key},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == STATUS_PROCESSED
    assert data["summary"]["headline"] == "Retried headline"
