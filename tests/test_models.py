"""Tests for the three core domain models: Source, Snapshot, Change.

These tests run against the brm_test Postgres database using the
SAVEPOINT-rollback fixture from conftest.py — each test is fully isolated
and the DB is left clean.

Requirements covered: SRC-01, EFF-01, INGEST-05
"""

from datetime import date, datetime

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from brm.models import Change, Snapshot, Source


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def make_source(**kwargs) -> Source:
    defaults = dict(
        jurisdiction="national",
        layer="FRBP",
        feed_url="https://www.uscourts.gov/news/rss",
        ingestion_method="rss",
        adapter_ref="brm.ingest.rss.FrbpSourceAdapter",
        polling_cadence="daily",
        health_status="unknown",
    )
    defaults.update(kwargs)
    return Source(**defaults)


# ---------------------------------------------------------------------------
# Source tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_source_columns(db_session):
    """SRC-01: Source row accepts and persists all required registry columns."""
    now = datetime(2026, 5, 21, 12, 0, 0)
    src = make_source(
        last_checked_at=now,
        last_changed_at=now,
        health_status="healthy",
        last_etag='"abc123"',
        last_modified_http="Wed, 21 May 2026 12:00:00 GMT",
        last_content_hash="deadbeef" * 8,
        tenant_id=None,
    )
    db_session.add(src)
    await db_session.flush()

    assert src.id is not None
    assert src.jurisdiction == "national"
    assert src.layer == "FRBP"
    assert src.feed_url == "https://www.uscourts.gov/news/rss"
    assert src.ingestion_method == "rss"
    assert src.adapter_ref == "brm.ingest.rss.FrbpSourceAdapter"
    assert src.polling_cadence == "daily"
    assert src.last_checked_at == now
    assert src.last_changed_at == now
    assert src.health_status == "healthy"
    assert src.last_etag == '"abc123"'
    assert src.last_modified_http == "Wed, 21 May 2026 12:00:00 GMT"
    assert src.last_content_hash == "deadbeef" * 8
    assert src.tenant_id is None


@pytest.mark.asyncio
async def test_source_health_status_invalid(db_session):
    """Source.health_status CHECK constraint rejects invalid values."""
    src = make_source(health_status="broken")
    db_session.add(src)
    with pytest.raises((IntegrityError, Exception)):
        await db_session.flush()


@pytest.mark.asyncio
async def test_source_health_status_valid_values(db_session):
    """All three valid health_status values are accepted."""
    for status in ("unknown", "healthy", "failed"):
        db_session.add(make_source(health_status=status))
    await db_session.flush()
    # If we get here all three values were accepted.


# ---------------------------------------------------------------------------
# Snapshot tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_snapshot_columns(db_session):
    """Snapshot row stores source_id, content, content_hash, version, fetched_at."""
    src = make_source()
    db_session.add(src)
    await db_session.flush()

    now = datetime(2026, 5, 21, 12, 0, 0)
    snap = Snapshot(
        source_id=src.id,
        content="title: Pending Rules\nlink: https://example.com\n",
        content_hash="abc123" * 8,
        version=1,
        fetched_at=now,
    )
    db_session.add(snap)
    await db_session.flush()

    assert snap.id is not None
    assert snap.source_id == src.id
    assert snap.content.startswith("title: Pending Rules")
    assert snap.content_hash == "abc123" * 8
    assert snap.version == 1
    assert snap.fetched_at == now


@pytest.mark.asyncio
async def test_snapshot_unique_constraint(db_session):
    """UNIQUE(source_id, version) prevents duplicate versions."""
    src = make_source()
    db_session.add(src)
    await db_session.flush()

    now = datetime(2026, 5, 21, 12, 0, 0)
    snap1 = Snapshot(
        source_id=src.id,
        content="v1 content",
        content_hash="hash1" * 12,
        version=1,
        fetched_at=now,
    )
    db_session.add(snap1)
    await db_session.flush()

    snap2 = Snapshot(
        source_id=src.id,
        content="v1 duplicate content",
        content_hash="hash2" * 12,
        version=1,  # duplicate version
        fetched_at=now,
    )
    db_session.add(snap2)
    with pytest.raises(IntegrityError):
        await db_session.flush()


# ---------------------------------------------------------------------------
# Change tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_change_detected_at_not_null_and_effective_date_nullable(db_session):
    """EFF-01: detected_at is NOT NULL; effective_date is nullable (D-12)."""
    src = make_source()
    db_session.add(src)
    await db_session.flush()

    now = datetime(2026, 5, 21, 12, 0, 0)
    snap = Snapshot(
        source_id=src.id,
        content="snapshot content",
        content_hash="c" * 64,
        version=1,
        fetched_at=now,
    )
    db_session.add(snap)
    await db_session.flush()

    change = Change(
        source_id=src.id,
        prior_snapshot_id=None,
        current_snapshot_id=snap.id,
        detected_at=now,
        effective_date=None,  # nullable until reviewer enters it
        diff_text="some diff",
    )
    db_session.add(change)
    await db_session.flush()

    assert change.id is not None
    assert change.detected_at == now
    assert change.effective_date is None  # D-12 — nullable
    assert change.status == "detected"


@pytest.mark.asyncio
async def test_change_effective_date_can_be_set(db_session):
    """EFF-01: effective_date accepts a Date value when reviewer enters it."""
    src = make_source()
    db_session.add(src)
    await db_session.flush()

    now = datetime(2026, 5, 21, 12, 0, 0)
    snap = Snapshot(
        source_id=src.id,
        content="content",
        content_hash="d" * 64,
        version=1,
        fetched_at=now,
    )
    db_session.add(snap)
    await db_session.flush()

    effective = date(2026, 12, 1)
    change = Change(
        source_id=src.id,
        current_snapshot_id=snap.id,
        detected_at=now,
        effective_date=effective,
    )
    db_session.add(change)
    await db_session.flush()

    assert change.effective_date == effective


@pytest.mark.asyncio
async def test_change_status_invalid_value(db_session):
    """Change.status CHECK constraint rejects values outside ALL_STATUSES."""
    src = make_source()
    db_session.add(src)
    await db_session.flush()

    now = datetime(2026, 5, 21, 12, 0, 0)
    snap = Snapshot(
        source_id=src.id,
        content="content",
        content_hash="e" * 64,
        version=1,
        fetched_at=now,
    )
    db_session.add(snap)
    await db_session.flush()

    # 'approved' is not a valid status — should be rejected.
    change = Change(
        source_id=src.id,
        current_snapshot_id=snap.id,
        detected_at=now,
        status="approved",  # invalid
    )
    db_session.add(change)
    with pytest.raises((IntegrityError, Exception)):
        await db_session.flush()


@pytest.mark.asyncio
async def test_change_updated_at_present(db_session):
    """Change has an updated_at column for the pull-API since-cursor."""
    src = make_source()
    db_session.add(src)
    await db_session.flush()

    now = datetime(2026, 5, 21, 12, 0, 0)
    snap = Snapshot(
        source_id=src.id,
        content="content",
        content_hash="f" * 64,
        version=1,
        fetched_at=now,
    )
    db_session.add(snap)
    await db_session.flush()

    change = Change(
        source_id=src.id,
        current_snapshot_id=snap.id,
        detected_at=now,
    )
    db_session.add(change)
    await db_session.flush()

    # updated_at must be populated (not None).
    assert change.updated_at is not None
