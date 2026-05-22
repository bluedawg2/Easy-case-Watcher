"""Tests for hash-gate detector and unified-diff helper.

Covers:
- Task 1: content_hash and textual_diff helpers (diff.py)
- Task 1: detect_change function (detector.py)
  - First-fetch baseline: prior_snapshot=None → None (no Change created)
  - Hash-gate: equal hashes → None (no Change created)
  - Diff creates Change: differing content → Change with status=detected
  - Snapshot references: prior_snapshot_id and current_snapshot_id correct
  - Diff format: textual_diff output contains unified-diff headers
  - Hash determinism: same input → same 64-char hex output
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from brm.models.change import Change
from brm.models.snapshot import Snapshot
from brm.models.source import Source

FRBP_URL = "https://www.uscourts.gov/forms-rules/pending-rules-and-forms-amendments"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


async def make_snapshot(session, source, content: str, version: int) -> Snapshot:
    from brm.detect.diff import content_hash

    snap = Snapshot(
        source_id=source.id,
        content=content,
        content_hash=content_hash(content),
        version=version,
        fetched_at=datetime.now(UTC),
    )
    session.add(snap)
    await session.flush()
    return snap


# ---------------------------------------------------------------------------
# Task 1: content_hash helper
# ---------------------------------------------------------------------------


class TestContentHash:
    def test_content_hash_is_64_char_hex(self):
        """content_hash returns a 64-character lowercase hex string (SHA-256)."""
        from brm.detect.diff import content_hash

        result = content_hash("some rule text")
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_content_hash_deterministic(self):
        """Same input always produces the same hash value."""
        from brm.detect.diff import content_hash

        text = "December 1, 2026\nBankruptcy Rules 1007, 3018"
        assert content_hash(text) == content_hash(text)
        assert content_hash(text) == content_hash(text)

    def test_content_hash_different_inputs_differ(self):
        """Different inputs produce different hashes."""
        from brm.detect.diff import content_hash

        assert content_hash("rule text v1") != content_hash("rule text v2")

    def test_content_hash_empty_string(self):
        """content_hash of empty string is the SHA-256 of '' (still 64 chars)."""
        from brm.detect.diff import content_hash

        result = content_hash("")
        assert len(result) == 64


# ---------------------------------------------------------------------------
# Task 1: textual_diff helper
# ---------------------------------------------------------------------------


class TestTextualDiff:
    def test_textual_diff_format(self):
        """textual_diff output contains '--- previous' and '+++ current' headers."""
        from brm.detect.diff import textual_diff

        old = "line one\nline two\n"
        new = "line one\nline three\n"
        result = textual_diff(old, new)
        assert "--- previous" in result
        assert "+++ current" in result

    def test_textual_diff_shows_removed_lines(self):
        """Lines removed from old appear with '-' prefix."""
        from brm.detect.diff import textual_diff

        old = "line one\nline two\n"
        new = "line one\n"
        result = textual_diff(old, new)
        assert "-line two" in result

    def test_textual_diff_shows_added_lines(self):
        """Lines added in new appear with '+' prefix."""
        from brm.detect.diff import textual_diff

        old = "line one\n"
        new = "line one\nline two\n"
        result = textual_diff(old, new)
        assert "+line two" in result

    def test_textual_diff_identical_content_empty(self):
        """textual_diff of identical strings returns an empty string."""
        from brm.detect.diff import textual_diff

        text = "same content\n"
        assert textual_diff(text, text) == ""


# ---------------------------------------------------------------------------
# Task 1: detect_change
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_first_fetch_baseline(db_session):
    """detect_change with prior_snapshot=None returns None — silent baseline.

    Review finding #10: first-ever snapshot establishes a baseline only;
    no Change row should be created.
    """
    from sqlalchemy import func, select

    from brm.detect.detector import detect_change

    source = make_source()
    db_session.add(source)
    await db_session.flush()

    current = await make_snapshot(db_session, source, "initial content", version=1)

    result = await detect_change(db_session, source, prior_snapshot=None, current_snapshot=current)

    assert result is None
    # No Change rows should exist
    count = await db_session.scalar(select(func.count()).select_from(Change))
    assert count == 0


@pytest.mark.asyncio
async def test_hash_gate_blocks(db_session):
    """detect_change with equal hashes returns None and creates no Change row."""
    from sqlalchemy import func, select

    from brm.detect.detector import detect_change

    source = make_source()
    db_session.add(source)
    await db_session.flush()

    content = "December 1, 2026\nBankruptcy Rules 1007"
    prior = await make_snapshot(db_session, source, content, version=1)
    current = await make_snapshot(db_session, source, content, version=2)

    # Both snapshots have the same content → same hash
    assert prior.content_hash == current.content_hash

    result = await detect_change(db_session, source, prior_snapshot=prior, current_snapshot=current)

    assert result is None
    count = await db_session.scalar(select(func.count()).select_from(Change))
    assert count == 0


@pytest.mark.asyncio
async def test_diff_creates_change(db_session):
    """detect_change with differing content creates one Change with status=detected."""
    from sqlalchemy import select

    from brm.detect.detector import detect_change
    from brm.lifecycle import STATUS_DETECTED

    source = make_source()
    db_session.add(source)
    await db_session.flush()

    prior = await make_snapshot(db_session, source, "rule text v1\n", version=1)
    current = await make_snapshot(db_session, source, "rule text v2\n", version=2)

    assert prior.content_hash != current.content_hash

    result = await detect_change(db_session, source, prior_snapshot=prior, current_snapshot=current)

    assert result is not None
    assert result.status == STATUS_DETECTED
    assert result.diff_text is not None
    assert len(result.diff_text) > 0

    # Exactly one Change row in the DB
    changes = (await db_session.execute(select(Change))).scalars().all()
    assert len(changes) == 1


@pytest.mark.asyncio
async def test_change_references_snapshots(db_session):
    """Change.prior_snapshot_id and current_snapshot_id are set correctly."""
    from brm.detect.detector import detect_change

    source = make_source()
    db_session.add(source)
    await db_session.flush()

    prior = await make_snapshot(db_session, source, "v1 content\n", version=1)
    current = await make_snapshot(db_session, source, "v2 content\n", version=2)

    change = await detect_change(db_session, source, prior_snapshot=prior, current_snapshot=current)

    assert change is not None
    assert change.prior_snapshot_id == prior.id
    assert change.current_snapshot_id == current.id
    assert change.source_id == source.id


@pytest.mark.asyncio
async def test_change_detected_at_is_set(db_session):
    """Change.detected_at is set to a recent UTC datetime."""
    from brm.detect.detector import detect_change

    source = make_source()
    db_session.add(source)
    await db_session.flush()

    prior = await make_snapshot(db_session, source, "old content\n", version=1)
    current = await make_snapshot(db_session, source, "new content\n", version=2)

    before = datetime.now(UTC)
    change = await detect_change(db_session, source, prior_snapshot=prior, current_snapshot=current)
    after = datetime.now(UTC)

    assert change is not None
    assert before <= change.detected_at <= after
