"""Append-only snapshot store — RESEARCH Pattern 3.

Persists a new versioned Snapshot row on every CHANGED fetch.  The version
number is monotonically increasing per source.

Concurrent fetch safety: a UNIQUE(source_id, version) constraint (defined on
the Snapshot model) converts a lost concurrent-version race into an
IntegrityError instead of silently corrupting snapshot lineage (review
finding #5).  A bounded retry loop re-reads max(version) and retries the insert
on IntegrityError, up to _MAX_RETRIES attempts.

INSERT-only: this module contains no UPDATE or DELETE statements.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from brm.models.snapshot import Snapshot
from brm.models.source import Source

_MAX_RETRIES = 3


async def store_snapshot(
    session: AsyncSession,
    source: Source,
    content: str,
    content_hash: str,
) -> Snapshot:
    """Insert a new append-only Snapshot row for the given source.

    Computes the next version as max(existing version) + 1, or 1 if none exist.
    Retries up to _MAX_RETRIES times on IntegrityError (concurrent insert race).

    Args:
        session:      An active AsyncSession.
        source:       The Source being snapshotted.
        content:      Normalized text content to store.
        content_hash: SHA-256 hex digest of the normalized content.

    Returns:
        The newly inserted Snapshot ORM object.

    Raises:
        IntegrityError: If _MAX_RETRIES consecutive concurrent races are lost.
    """
    for attempt in range(_MAX_RETRIES):
        current_max = await session.scalar(
            select(func.max(Snapshot.version)).where(
                Snapshot.source_id == source.id
            )
        )
        next_version = (current_max or 0) + 1

        snapshot = Snapshot(
            source_id=source.id,
            content=content,
            content_hash=content_hash,
            version=next_version,
            fetched_at=datetime.now(UTC),
        )
        session.add(snapshot)

        try:
            await session.flush()
            return snapshot
        except IntegrityError:
            await session.rollback()
            if attempt == _MAX_RETRIES - 1:
                raise

    raise RuntimeError("Unreachable")  # pragma: no cover
