"""Hash-gate change detector — RESEARCH Pattern 4 + review finding #10.

detect_change is the single function that decides whether a new snapshot
represents a genuine rule change.

Design decisions:
- FIRST-FETCH RULE (review finding #10): prior_snapshot=None means this is
  the very first snapshot for the source.  It establishes a SILENT BASELINE —
  no Change is created.  Emitting a Change here would flood the queue with a
  spurious "everything changed" record that has nothing to diff against.
- HASH-GATE (DETECT-02): equal content hashes mean the content is unchanged;
  no Change, no downstream LLM work.
- DIFF (DETECT-01): only when hashes differ does detect_change compute a
  unified diff and insert a Change row with status=detected.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from brm.detect.diff import textual_diff
from brm.lifecycle import STATUS_DETECTED
from brm.models.change import Change

if TYPE_CHECKING:
    from brm.models.snapshot import Snapshot
    from brm.models.source import Source


async def detect_change(
    session: AsyncSession,
    source: "Source",
    prior_snapshot: "Snapshot | None",
    current_snapshot: "Snapshot",
) -> Change | None:
    """Decide whether a new snapshot represents a genuine change.

    Args:
        session:          An active AsyncSession.
        source:           The Source being monitored.
        prior_snapshot:   The immediately preceding Snapshot, or None if this
                          is the very first fetch for the source.
        current_snapshot: The newly stored Snapshot to compare against.

    Returns:
        A newly inserted Change with status=detected if a genuine content
        change is found; None otherwise (first-fetch baseline or hash-gate).
    """
    # FIRST-FETCH RULE (review finding #10): no prior snapshot means this is
    # the baseline.  Return None immediately — no Change, no diff.
    if prior_snapshot is None:
        return None

    # HASH-GATE (DETECT-02): same content hash means nothing changed.
    if prior_snapshot.content_hash == current_snapshot.content_hash:
        return None

    # Content differs — compute unified diff and create a Change.
    diff = textual_diff(prior_snapshot.content, current_snapshot.content)

    change = Change(
        source_id=source.id,
        prior_snapshot_id=prior_snapshot.id,
        current_snapshot_id=current_snapshot.id,
        status=STATUS_DETECTED,
        detected_at=datetime.now(UTC),
        diff_text=diff,
        effective_date=None,
    )
    session.add(change)
    await session.flush()
    return change
