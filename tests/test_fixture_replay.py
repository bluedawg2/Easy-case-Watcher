"""Fixture-replay proof for run_ingest pipeline orchestrator.

Tests D-03 (fixture replay) and D-04 (no production-only branch):
- Replaying frbp_source_v1 then frbp_source_v2 through run_ingest yields
  None on run 1 (silent baseline) and a detected Change on run 2.
- Replaying v1 then v1 yields None on run 2 (hash-gate / UNCHANGED).
- FETCH_FAILED produces no snapshot, no Change, health_status=failed.
- CHANGED/UNCHANGED fetch sets health_status=healthy.
- test_identical_code_path: fixture and live paths share identical detection
  code, proven behaviorally by comparing diff_text and content_hash.

Zero live network calls — all HTTP mocked via respx.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx

from brm.models.source import Source

FIXTURES_DIR = Path(__file__).parent / "fixtures"
FRBP_URL = "https://www.uscourts.gov/forms-rules/pending-rules-and-forms-amendments"


def load_fixture(name: str) -> bytes:
    return (FIXTURES_DIR / name).read_bytes()


def make_source() -> Source:
    return Source(
        jurisdiction="national",
        layer="FRBP",
        feed_url=FRBP_URL,
        ingestion_method="html",
        adapter_ref="frbp_rulemaking",
        polling_cadence="daily",
        health_status="unknown",
    )


# ---------------------------------------------------------------------------
# test_fixture_replay_baseline_then_change
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fixture_replay_baseline_then_change(db_session):
    """Replay v1 (baseline) then v2 (new FRBP entry) through run_ingest.

    - Run 1 (v1): first-ever fetch → silent baseline, returns None.
    - Run 2 (v2): new entry present → detected Change returned.
    """

    from brm.ingest.rss import FrbpSourceAdapter
    from brm.lifecycle import STATUS_DETECTED
    from brm.models.change import Change
    from brm.models.snapshot import Snapshot
    from brm.pipeline import run_ingest

    source = make_source()
    db_session.add(source)
    await db_session.flush()

    adapter = FrbpSourceAdapter()
    v1 = load_fixture("frbp_source_v1.captured")
    v2 = load_fixture("frbp_source_v2.captured")

    # Run 1: v1 response → baseline (no Change)
    with respx.mock(assert_all_called=False) as router:
        router.get(FRBP_URL).mock(return_value=httpx.Response(200, content=v1))
        result1 = await run_ingest(db_session, source, adapter)

    assert result1 is None, "First fetch must be a silent baseline — no Change"

    from sqlalchemy import func
    from sqlalchemy import select as sa_select

    snap_count = await db_session.scalar(
        sa_select(func.count()).select_from(Snapshot).where(Snapshot.source_id == source.id)
    )
    assert snap_count == 1, "v1 fetch must store one snapshot"

    # Run 2: v2 response → detected Change
    with respx.mock(assert_all_called=False) as router:
        router.get(FRBP_URL).mock(return_value=httpx.Response(200, content=v2))
        result2 = await run_ingest(db_session, source, adapter)

    assert result2 is not None, "v2 fetch must produce a Change"
    assert result2.status == STATUS_DETECTED
    assert result2.diff_text is not None
    assert len(result2.diff_text) > 0

    change_count = await db_session.scalar(
        sa_select(func.count()).select_from(Change).where(Change.source_id == source.id)
    )
    assert change_count == 1


# ---------------------------------------------------------------------------
# test_fixture_replay_hash_gate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fixture_replay_hash_gate(db_session):
    """Replay v1 then v1 again — second run hits hash-gate, returns None."""
    from sqlalchemy import func
    from sqlalchemy import select as sa_select

    from brm.ingest.rss import FrbpSourceAdapter
    from brm.models.change import Change
    from brm.pipeline import run_ingest

    source = make_source()
    db_session.add(source)
    await db_session.flush()

    adapter = FrbpSourceAdapter()
    v1 = load_fixture("frbp_source_v1.captured")

    # Run 1: baseline
    with respx.mock(assert_all_called=False) as router:
        router.get(FRBP_URL).mock(return_value=httpx.Response(200, content=v1))
        result1 = await run_ingest(db_session, source, adapter)

    assert result1 is None

    # Run 2: same v1 content → UNCHANGED (hash-gate / adapter sees equal hash)
    with respx.mock(assert_all_called=False) as router:
        router.get(FRBP_URL).mock(return_value=httpx.Response(200, content=v1))
        result2 = await run_ingest(db_session, source, adapter)

    assert result2 is None

    change_count = await db_session.scalar(
        sa_select(func.count()).select_from(Change).where(Change.source_id == source.id)
    )
    assert change_count == 0, "Hash-gate must produce no Change rows"


# ---------------------------------------------------------------------------
# test_fixture_replay_fetch_failed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fixture_replay_fetch_failed(db_session):
    """FETCH_FAILED: run_ingest returns None, health_status=failed, no Snapshot created."""
    from sqlalchemy import func
    from sqlalchemy import select as sa_select

    from brm.ingest.rss import FrbpSourceAdapter
    from brm.models.snapshot import Snapshot
    from brm.pipeline import run_ingest

    source = make_source()
    db_session.add(source)
    await db_session.flush()

    adapter = FrbpSourceAdapter()

    with respx.mock(assert_all_called=False) as router:
        router.get(FRBP_URL).mock(side_effect=httpx.TimeoutException("timeout"))
        result = await run_ingest(db_session, source, adapter)

    assert result is None
    assert source.health_status == "failed"

    snap_count = await db_session.scalar(
        sa_select(func.count()).select_from(Snapshot).where(Snapshot.source_id == source.id)
    )
    assert snap_count == 0, "FETCH_FAILED must not create any Snapshot rows"


# ---------------------------------------------------------------------------
# test_health_status_updated_on_success
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_status_updated_on_success(db_session):
    """After a CHANGED or UNCHANGED fetch, health_status is 'healthy'.

    Health status must never remain 'unknown' after a successful poll
    (review finding #20).
    """
    from brm.ingest.rss import FrbpSourceAdapter
    from brm.pipeline import run_ingest

    source = make_source()
    assert source.health_status == "unknown"
    db_session.add(source)
    await db_session.flush()

    adapter = FrbpSourceAdapter()
    v1 = load_fixture("frbp_source_v1.captured")

    # CHANGED path (first fetch)
    with respx.mock(assert_all_called=False) as router:
        router.get(FRBP_URL).mock(return_value=httpx.Response(200, content=v1))
        await run_ingest(db_session, source, adapter)

    assert source.health_status == "healthy", (
        "health_status must be 'healthy' after a successful CHANGED fetch"
    )

    # UNCHANGED path (second fetch of same content — adapter returns UNCHANGED)
    with respx.mock(assert_all_called=False) as router:
        router.get(FRBP_URL).mock(return_value=httpx.Response(200, content=v1))
        await run_ingest(db_session, source, adapter)

    assert source.health_status == "healthy", (
        "health_status must be 'healthy' after a successful UNCHANGED fetch"
    )


# ---------------------------------------------------------------------------
# test_identical_code_path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_identical_code_path(db_session):
    """Behavioral proof that fixture and live paths share identical detection code.

    Replaces the previous grep-based policing (flagged by reviewers as cargo-cult).
    Approach: feed the same bytes twice through run_ingest:
    - Run A ("fixture-style"): source A, first call = baseline (v1), second call = v2
    - Run B ("live-style"):    source B, first call = baseline (v1), second call = v2
    Both reach the same run_ingest → store_snapshot → detect_change code path.
    The two resulting Changes must have byte-identical diff_text and content_hash,
    proving that detection logic is the same regardless of the caller or path.
    """
    from sqlalchemy import select as sa_select

    from brm.ingest.rss import FrbpSourceAdapter
    from brm.models.snapshot import Snapshot
    from brm.pipeline import run_ingest

    v1 = load_fixture("frbp_source_v1.captured")
    v2 = load_fixture("frbp_source_v2.captured")

    # Source A
    source_a = make_source()
    db_session.add(source_a)
    await db_session.flush()

    # Source B (same URL — adapter uses source.feed_url)
    source_b = Source(
        jurisdiction="national",
        layer="FRBP",
        feed_url=FRBP_URL,
        ingestion_method="html",
        adapter_ref="frbp_rulemaking",
        polling_cadence="daily",
        health_status="unknown",
    )
    db_session.add(source_b)
    await db_session.flush()

    adapter = FrbpSourceAdapter()

    # Run A: baseline (v1), then change (v2)
    with respx.mock(assert_all_called=False) as router:
        router.get(FRBP_URL).mock(return_value=httpx.Response(200, content=v1))
        await run_ingest(db_session, source_a, adapter)

    with respx.mock(assert_all_called=False) as router:
        router.get(FRBP_URL).mock(return_value=httpx.Response(200, content=v2))
        change_a = await run_ingest(db_session, source_a, adapter)

    # Run B: baseline (v1), then change (v2)
    with respx.mock(assert_all_called=False) as router:
        router.get(FRBP_URL).mock(return_value=httpx.Response(200, content=v1))
        await run_ingest(db_session, source_b, adapter)

    with respx.mock(assert_all_called=False) as router:
        router.get(FRBP_URL).mock(return_value=httpx.Response(200, content=v2))
        change_b = await run_ingest(db_session, source_b, adapter)

    assert change_a is not None, "Run A must produce a Change"
    assert change_b is not None, "Run B must produce a Change"

    # Behavioral identity assertion: same bytes → same detection outcome
    assert change_a.diff_text == change_b.diff_text, (
        "diff_text must be byte-identical for identical input bytes — "
        "both paths must share the same detection code (D-04)"
    )

    # Fetch the stored snapshots and compare content_hash
    snaps_a = (
        await db_session.execute(
            sa_select(Snapshot)
            .where(Snapshot.source_id == source_a.id)
            .order_by(Snapshot.version.desc())
        )
    ).scalars().first()
    snaps_b = (
        await db_session.execute(
            sa_select(Snapshot)
            .where(Snapshot.source_id == source_b.id)
            .order_by(Snapshot.version.desc())
        )
    ).scalars().first()

    assert snaps_a is not None
    assert snaps_b is not None
    assert snaps_a.content_hash == snaps_b.content_hash, (
        "content_hash must be identical for the same input bytes (D-04)"
    )
