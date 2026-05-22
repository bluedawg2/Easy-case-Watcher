"""Pull-delivery API router — verified changes for the other product.

Endpoint:
    GET /changes?since=<ISO datetime>

Returns verified changes ordered by updated_at, id (stable cursor ordering).
The `since` query parameter filters to changes updated *after* the given
datetime, enabling incremental polling.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from brm.auth import require_api_key
from brm.db import get_session
from brm.lifecycle import STATUS_VERIFIED
from brm.models.change import Change
from brm.schemas.api import ChangeOut

router = APIRouter(
    prefix="/changes",
    tags=["pull-api"],
    dependencies=[Depends(require_api_key)],
)


@router.get("", response_model=list[ChangeOut])
async def get_changes(
    since: Optional[datetime] = Query(None),
    session: AsyncSession = Depends(get_session),
) -> list[ChangeOut]:
    """Return verified changes, optionally filtered to those updated after `since`.

    Args:
        since: Optional ISO datetime cursor. If provided, only changes with
               updated_at > since are returned.
        session: Injected async DB session.

    Returns:
        List of ChangeOut objects ordered by updated_at, then id for stability.
    """
    q = (
        select(Change)
        .options(selectinload(Change.source))
        .where(Change.status == STATUS_VERIFIED)
    )
    if since is not None:
        q = q.where(Change.updated_at > since)
    q = q.order_by(Change.updated_at, Change.id)
    result = await session.execute(q)
    changes = result.scalars().all()
    return [
        ChangeOut(
            id=c.id,
            source_layer=c.source.layer,
            source_url=c.source.feed_url,
            headline=c.summary.get("headline") if c.summary else None,
            summary=c.summary,
            not_legal_advice_label=c.not_legal_advice_label,
            diff_text=c.diff_text,
            detected_at=c.detected_at,
            effective_date=c.effective_date,
            status=c.status,
            updated_at=c.updated_at,
        )
        for c in changes
    ]
