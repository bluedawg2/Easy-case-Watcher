"""Tests for the AI summarization layer (Tasks 2 and 3 of plan 01-04).

All tests mock the Anthropic SDK — they run WITHOUT ANTHROPIC_API_KEY set.
DB tests (tests 5, 9) use the db_session fixture from conftest.py.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from brm.schemas.summary import NOT_LEGAL_ADVICE_LABEL, ChangeSummary
from brm.ai.summarize import SUMMARY_MODEL, SYSTEM_PROMPT, summarize

# ---------------------------------------------------------------------------
# Task 2 tests: schema shape, guardrails, constant
# ---------------------------------------------------------------------------


def test_summary_shape():
    """summarize() returns a ChangeSummary with all five string fields."""
    mock_parsed = ChangeSummary(
        headline="h",
        what_changed="w",
        where="x",
        to_whom="y",
        for_what_cases="z",
    )
    mock_response = MagicMock()
    mock_response.parsed_output = mock_parsed

    with patch("brm.ai.summarize.anthropic.Anthropic") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.messages.parse.return_value = mock_response

        result = summarize("some diff")

    assert isinstance(result, ChangeSummary)
    assert isinstance(result.headline, str)
    assert isinstance(result.what_changed, str)
    assert isinstance(result.where, str)
    assert isinstance(result.to_whom, str)
    assert isinstance(result.for_what_cases, str)
    assert result.headline == "h"
    assert result.what_changed == "w"
    assert result.where == "x"
    assert result.to_whom == "y"
    assert result.for_what_cases == "z"


def test_summary_no_disclaimer_field():
    """ChangeSummary model_fields does NOT include a legal_disclaimer or not_legal_advice field."""
    fields = set(ChangeSummary.model_fields.keys())
    assert "legal_disclaimer" not in fields
    assert "not_legal_advice" not in fields


def test_system_prompt_guardrails():
    """SYSTEM_PROMPT contains the key guardrail phrases."""
    assert "speculate" in SYSTEM_PROMPT
    assert "advice" in SYSTEM_PROMPT
    assert "1-3 sentences" in SYSTEM_PROMPT


def test_label_is_constant():
    """NOT_LEGAL_ADVICE_LABEL is a non-empty string not containing 'TODO'."""
    assert isinstance(NOT_LEGAL_ADVICE_LABEL, str)
    assert len(NOT_LEGAL_ADVICE_LABEL) > 0
    assert "TODO" not in NOT_LEGAL_ADVICE_LABEL


# ---------------------------------------------------------------------------
# Task 3 tests: run_summarize pipeline function
# ---------------------------------------------------------------------------


async def _make_fake_change(db_session, status="detected", diff_text="some diff", feed_url_suffix=""):
    """Helper: create and flush a Source + Snapshot + Change row for testing.

    Uses a unique feed_url per call (via suffix) to avoid UNIQUE constraint
    collisions when multiple tests share the same DB transaction.

    Returns the fully-wired Change object (all FK columns populated).
    """
    from brm.models.change import Change
    from brm.models.snapshot import Snapshot
    from brm.models.source import Source

    src = Source(
        jurisdiction="national",
        layer="FRBP",
        feed_url=f"https://example.com/test-ai{feed_url_suffix}",
        ingestion_method="html",
        adapter_ref="frbp_rulemaking",
        polling_cadence="daily",
        health_status="unknown",
    )
    db_session.add(src)
    await db_session.flush()  # get src.id

    snap = Snapshot(
        source_id=src.id,
        content="content",
        content_hash="a" * 64,
        version=1,
        fetched_at=datetime(2026, 5, 22, 0, 0, 0),
    )
    db_session.add(snap)
    await db_session.flush()  # get snap.id

    change = Change(
        source_id=src.id,
        prior_snapshot_id=None,
        current_snapshot_id=snap.id,
        status=status,
        detected_at=datetime(2026, 5, 22, 0, 0, 0),
        diff_text=diff_text,
    )
    db_session.add(change)
    await db_session.flush()  # get change.id

    return change


@pytest.mark.asyncio
async def test_run_summarize_success(db_session):
    """run_summarize sets status=processed and populates summary fields."""
    from brm.pipeline import run_summarize

    change = await _make_fake_change(db_session, status="detected", diff_text="some diff",
                                     feed_url_suffix="/success")

    mock_result = ChangeSummary(
        headline="h",
        what_changed="w",
        where="x",
        to_whom="y",
        for_what_cases="z",
    )

    with patch("brm.pipeline.summarize", return_value=mock_result):
        updated = await run_summarize(db_session, change)

    assert updated.status == "processed"
    assert isinstance(updated.summary, dict)
    for key in ("headline", "what_changed", "where", "to_whom", "for_what_cases"):
        assert key in updated.summary, f"Missing key: {key}"
    assert updated.not_legal_advice_label == NOT_LEGAL_ADVICE_LABEL
    assert updated.model_id == SUMMARY_MODEL
    assert updated.summary_error is None


@pytest.mark.asyncio
async def test_run_summarize_invalid_status(db_session):
    """run_summarize raises IllegalTransitionError when Change status is not summarizable."""
    from brm.lifecycle import IllegalTransitionError
    from brm.pipeline import run_summarize

    change = await _make_fake_change(db_session, status="in_review", diff_text="some diff",
                                     feed_url_suffix="/invalid-status")

    with pytest.raises(IllegalTransitionError):
        await run_summarize(db_session, change)


@pytest.mark.asyncio
async def test_run_summarize_failure(db_session):
    """run_summarize sets status=summary_failed when summarize raises, and does not re-raise."""
    from brm.pipeline import run_summarize

    change = await _make_fake_change(db_session, status="detected", diff_text="some diff",
                                     feed_url_suffix="/failure")

    with patch("brm.pipeline.summarize", side_effect=Exception("API error")):
        updated = await run_summarize(db_session, change)

    assert updated.status == "summary_failed"
    assert updated.summary_error is not None
    assert "API error" in updated.summary_error


@pytest.mark.asyncio
async def test_run_summarize_retry(db_session):
    """run_summarize on a summary_failed Change succeeds on retry."""
    from brm.pipeline import run_summarize

    # Start with summary_failed state — simulates a prior failed attempt.
    change = await _make_fake_change(
        db_session, status="summary_failed", diff_text="some diff",
        feed_url_suffix="/retry"
    )
    change.summary_error = "Exception: prior error retry_count=1"
    await db_session.flush()

    mock_result = ChangeSummary(
        headline="retry headline",
        what_changed="w",
        where="x",
        to_whom="y",
        for_what_cases="z",
    )

    with patch("brm.pipeline.summarize", return_value=mock_result):
        updated = await run_summarize(db_session, change)

    assert updated.status == "processed"
    assert updated.summary_error is None


@pytest.mark.asyncio
async def test_summary_jsonb_roundtrip(db_session):
    """ChangeSummary JSONB data survives a DB flush and reload with all five string keys."""
    from sqlalchemy import select

    from brm.models.change import Change
    from brm.models.snapshot import Snapshot
    from brm.models.source import Source
    from brm.pipeline import run_summarize

    src = Source(
        jurisdiction="national",
        layer="FRBP",
        feed_url="https://example.com/jsonb-roundtrip",
        ingestion_method="html",
        adapter_ref="frbp_rulemaking",
        polling_cadence="daily",
        health_status="unknown",
    )
    db_session.add(src)
    await db_session.flush()

    snap = Snapshot(
        source_id=src.id,
        content="content",
        content_hash="b" * 64,
        version=1,
        fetched_at=datetime(2026, 5, 22, 0, 0, 0),
    )
    db_session.add(snap)
    await db_session.flush()

    change = Change(
        source_id=src.id,
        prior_snapshot_id=None,
        current_snapshot_id=snap.id,
        status="detected",
        detected_at=datetime(2026, 5, 22, 0, 0, 0),
        diff_text="x",
    )
    db_session.add(change)
    await db_session.flush()

    mock_result = ChangeSummary(
        headline="jsonb headline",
        what_changed="what changed",
        where="FRBP Rule 1001",
        to_whom="all practitioners",
        for_what_cases="all chapter 11 cases",
    )

    with patch("brm.pipeline.summarize", return_value=mock_result):
        await run_summarize(db_session, change)

    await db_session.flush()

    # Reload from DB to verify JSONB round-trip.
    reloaded = await db_session.get(Change, change.id)
    assert reloaded is not None
    assert isinstance(reloaded.summary, dict)
    for key in ("headline", "what_changed", "where", "to_whom", "for_what_cases"):
        assert key in reloaded.summary, f"Missing JSONB key after round-trip: {key}"
        assert isinstance(reloaded.summary[key], str)
