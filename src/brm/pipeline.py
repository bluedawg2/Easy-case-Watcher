"""run_ingest pipeline orchestrator — the single shared code path.

Wires: fetch → (on CHANGED) store_snapshot → detect_change.

Design (D-03, D-04, review finding #20):
- There is NO `if fixture:` branch anywhere in this file or anywhere in src/.
  The fixture-replay path (tests) and the live polling path differ only in
  whether respx replays a captured file or a real HTTP response is fetched.
  Both paths call this same run_ingest function.
- A successful fetch (CHANGED or UNCHANGED) MUST move source.health_status
  off its default 'unknown' — otherwise a healthy source is indistinguishable
  from a never-checked one (review finding #20).
- FETCH_FAILED is NOT silently treated as no-change; it is an explicit failure
  that sets health_status='failed' and returns None (T-03-01 mitigation).
"""

from __future__ import annotations

import asyncio
import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from brm.ai.summarize import SUMMARY_MODEL, summarize
from brm.detect.detector import detect_change
from brm.detect.diff import content_hash
from brm.ingest.outcome import FetchOutcome
from brm.ingest.snapshot_store import store_snapshot
from brm.lifecycle import (
    STATUS_PROCESSED,
    STATUS_SUMMARY_FAILED,
    IllegalTransitionError,
    assert_transition,
)
from brm.models.snapshot import Snapshot
from brm.schemas.summary import NOT_LEGAL_ADVICE_LABEL, ChangeSummary

if TYPE_CHECKING:
    from brm.ingest.adapter import SourceAdapter
    from brm.models.change import Change
    from brm.models.source import Source


async def run_ingest(
    session: AsyncSession,
    source: "Source",
    adapter: "SourceAdapter",
) -> "Change | None":
    """Fetch one source, store a snapshot if content changed, and detect changes.

    This is the SINGLE shared orchestration function used by both the fixture-
    replay path and the live polling path.  There is no if-fixture branch.

    Args:
        session: An active AsyncSession.
        source:  The Source to fetch.
        adapter: A SourceAdapter implementation (e.g. FrbpSourceAdapter).

    Returns:
        A newly inserted Change with status=detected if a genuine rule change
        is found; None if the content is unchanged, this is the first fetch
        (silent baseline), or the fetch failed.
    """
    result = await adapter.fetch(source)

    now = datetime.now(UTC)

    if result.outcome == FetchOutcome.FETCH_FAILED:
        # Explicit failure — NOT silently treated as no-change (T-03-01).
        source.health_status = "failed"
        source.last_checked_at = now
        return None

    if result.outcome == FetchOutcome.UNCHANGED:
        # Content confirmed unchanged (304 or hash-equal).
        source.health_status = "healthy"
        source.last_checked_at = now
        # Update conditional-GET headers if the server sent them.
        if result.raw_etag is not None:
            source.last_etag = result.raw_etag
        if result.raw_last_modified is not None:
            source.last_modified_http = result.raw_last_modified
        return None

    # outcome == CHANGED — store snapshot, get prior, detect.
    assert result.content is not None, "CHANGED result must carry content"
    new_hash = content_hash(result.content)
    new_snapshot = await store_snapshot(session, source, result.content, new_hash)

    # Look up the immediately preceding snapshot (version DESC offset 1).
    prior_row = (
        await session.execute(
            select(Snapshot)
            .where(Snapshot.source_id == source.id)
            .order_by(Snapshot.version.desc())
            .offset(1)
            .limit(1)
        )
    ).scalars().first()

    change = await detect_change(session, source, prior_row, new_snapshot)

    # Update source bookkeeping — health MUST not remain 'unknown' (finding #20).
    source.health_status = "healthy"
    source.last_checked_at = now
    source.last_changed_at = now
    source.last_content_hash = new_hash
    if result.raw_etag is not None:
        source.last_etag = result.raw_etag
    if result.raw_last_modified is not None:
        source.last_modified_http = result.raw_last_modified

    return change


async def run_summarize(session: AsyncSession, change: "Change") -> "Change":
    """Run the AI summarization step for a detected Change.

    Calls the Anthropic API via summarize(), records the structured result on
    the Change row, and transitions the lifecycle status to processed or
    summary_failed.

    Args:
        session: An active AsyncSession (caller manages transaction).
        change:  A Change row with status "detected" or "summary_failed".
                 The row must have diff_text populated.

    Returns:
        The same Change object with updated status, summary, and related fields.

    Raises:
        ValueError: If change.diff_text is empty or None.
        IllegalTransitionError: If change.status cannot transition to processed
                                (e.g. status is "in_review" or "verified").
                                This propagates — callers must pass a valid Change.
    """
    if not change.diff_text:
        raise ValueError(f"Change {change.id} has no diff_text — cannot summarize.")

    # Reject invalid starting states via lifecycle guard.
    # assert_transition raises IllegalTransitionError if current status can't go to
    # STATUS_PROCESSED.  Both "detected" and "summary_failed" are allowed → processed;
    # anything else raises.
    assert_transition(change.status, STATUS_PROCESSED)

    # Parse current retry count from summary_error if it exists.
    retry_count = 0
    if change.summary_error:
        m = re.search(r"retry_count=(\d+)", change.summary_error)
        if m:
            retry_count = int(m.group(1))

    try:
        result: ChangeSummary = await asyncio.wait_for(
            asyncio.to_thread(summarize, change.diff_text),
            timeout=60.0,
        )
        change.summary = result.model_dump()
        change.not_legal_advice_label = NOT_LEGAL_ADVICE_LABEL
        change.model_id = SUMMARY_MODEL
        change.summary_error = None
        change.status = STATUS_PROCESSED
    except Exception as exc:
        retry_count += 1
        change.summary_error = f"{type(exc).__name__}: {exc} retry_count={retry_count}"
        change.status = STATUS_SUMMARY_FAILED

    await session.flush()
    return change
