"""Seed the source registry with the one national FRBP rulemaking source.

Inserts exactly one Source row if it does not already exist (idempotent — match
on feed_url).

Decision notes (recorded here per PLAN 01-02 requirement):
- D-01: The seeded source layer is FRBP — the Bankruptcy Rules amendment entries
  on this rulemaking page are the monitored content, not the Code or Forms.
- D-02: The specific source is the verified FRBP rulemaking HTML page per
  01-02-SOURCE-VERIFICATION.md — NOT the generic Judiciary News feed
  (uscourts.gov/news/rss).  The reviewers' unanimous finding #1 (source/domain
  mismatch) is resolved by this verified source.

Run standalone: uv run python -m brm.seed
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from brm.db import SessionLocal
from brm.models.source import Source

# D-02: verified FRBP rulemaking source per 01-02-SOURCE-VERIFICATION.md
_FRBP_FEED_URL = (
    "https://www.uscourts.gov/forms-rules/pending-rules-and-forms-amendments"
)


async def seed(session: AsyncSession | None = None) -> Source:
    """Insert the FRBP rulemaking source if it does not already exist.

    Args:
        session: An active AsyncSession.  If None, a new session is opened.

    Returns:
        The existing or newly inserted Source row.
    """
    if session is not None:
        return await _seed_in_session(session)

    async with SessionLocal() as new_session:
        result = await _seed_in_session(new_session)
        await new_session.commit()
        return result


async def _seed_in_session(session: AsyncSession) -> Source:
    existing = await session.scalar(
        select(Source).where(Source.feed_url == _FRBP_FEED_URL)
    )
    if existing is not None:
        return existing

    source = Source(
        jurisdiction="national",
        # D-01: FRBP layer locked — not the Bankruptcy Code or Official Forms.
        layer="FRBP",
        feed_url=_FRBP_FEED_URL,
        # Source is an HTML rulemaking page (confirmed by live fetch Task 1).
        ingestion_method="html",
        adapter_ref="frbp_rulemaking",
        polling_cadence="daily",
        health_status="unknown",
        # Multi-tenancy seam — nullable in Phase 1; un-scoped intentionally.
        tenant_id=None,
    )
    session.add(source)
    await session.flush()
    return source


if __name__ == "__main__":
    asyncio.run(seed())
