"""Tests for the append-only snapshot store and the FRBP source seed.

Covers Task 4 behaviors:
- store_snapshot inserts new Snapshot rows with monotonically increasing version
- store_snapshot is INSERT-only (no UPDATE/DELETE in the module source)
- duplicate (source_id, version) raises IntegrityError
- seed() is idempotent and seeds one FRBP Source with the verified rulemaking URL
"""

from __future__ import annotations

import inspect

import pytest

from brm.models.snapshot import Snapshot
from brm.models.source import Source

FRBP_RULEMAKING_URL = (
    "https://www.uscourts.gov/forms-rules/pending-rules-and-forms-amendments"
)


# ---------------------------------------------------------------------------
# Task 4: store_snapshot tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_store_snapshot_monotonic_version(db_session):
    """Two store_snapshot calls for the same source produce versions 1 and 2."""
    from brm.ingest.snapshot_store import store_snapshot

    source = Source(
        jurisdiction="national",
        layer="FRBP",
        feed_url=FRBP_RULEMAKING_URL,
        ingestion_method="html",
        adapter_ref="frbp_rulemaking",
        polling_cadence="daily",
        health_status="unknown",
    )
    db_session.add(source)
    await db_session.flush()

    snap1 = await store_snapshot(db_session, source, "content v1", "hash1")
    snap2 = await store_snapshot(db_session, source, "content v2", "hash2")

    assert snap1.version == 1
    assert snap2.version == 2
    assert snap1.source_id == source.id
    assert snap2.source_id == source.id


@pytest.mark.asyncio
async def test_store_snapshot_append_only():
    """No UPDATE or DELETE statement exists anywhere in snapshot_store module source."""
    import brm.ingest.snapshot_store as module

    source_code = inspect.getsource(module)
    assert "update(" not in source_code.lower() or "# no update" in source_code.lower()

    lowered = source_code.lower()
    # Explicit checks — neither 'session.delete' nor 'delete(' should appear
    assert "session.delete" not in lowered
    # Allow 'delete' in comments but not as code
    for line in source_code.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        assert "session.delete" not in stripped.lower(), (
            f"Found session.delete in non-comment line: {stripped!r}"
        )


@pytest.mark.asyncio
async def test_store_snapshot_unique_constraint(db_session):
    """Manually inserting a duplicate (source_id, version) raises IntegrityError."""
    from datetime import UTC, datetime

    from sqlalchemy.exc import IntegrityError

    source = Source(
        jurisdiction="national",
        layer="FRBP",
        feed_url=FRBP_RULEMAKING_URL,
        ingestion_method="html",
        adapter_ref="frbp_rulemaking",
        polling_cadence="daily",
        health_status="unknown",
    )
    db_session.add(source)
    await db_session.flush()

    snap_a = Snapshot(
        source_id=source.id,
        content="first snapshot",
        content_hash="hash_a",
        version=1,
        fetched_at=datetime.now(UTC),
    )
    db_session.add(snap_a)
    await db_session.flush()

    # Attempt to insert a second snapshot with the same (source_id, version=1)
    snap_b = Snapshot(
        source_id=source.id,
        content="second snapshot same version",
        content_hash="hash_b",
        version=1,
        fetched_at=datetime.now(UTC),
    )
    db_session.add(snap_b)
    with pytest.raises(IntegrityError):
        await db_session.flush()


# ---------------------------------------------------------------------------
# Task 4: seed tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_seed_idempotent(db_session):
    """Seeding twice produces exactly one Source row."""
    from sqlalchemy import func, select

    from brm.seed import seed

    await seed(db_session)
    await seed(db_session)

    count = await db_session.scalar(
        select(func.count()).select_from(Source).where(Source.layer == "FRBP")
    )
    assert count == 1


@pytest.mark.asyncio
async def test_seed_layer_frbp(db_session):
    """The seeded source has layer='FRBP' and feed_url pointing at the rulemaking page."""
    from sqlalchemy import select

    from brm.seed import seed

    await seed(db_session)

    source = await db_session.scalar(
        select(Source).where(Source.layer == "FRBP")
    )
    assert source is not None
    assert source.layer == "FRBP"
    assert source.feed_url == FRBP_RULEMAKING_URL
    assert "news/rss" not in source.feed_url
    assert source.ingestion_method == "html"
    assert source.adapter_ref == "frbp_rulemaking"
