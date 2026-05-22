"""Review-queue API router — endpoints for human reviewers.

All endpoints require the X-API-Key header (require_api_key dependency).

Endpoints:
    GET  /review/queue            — items awaiting review
    GET  /review/{id}             — full change detail
    POST /review/{id}/approve     — approve with effective_date
    POST /review/{id}/edit        — edit AI summary (re-entrant)
    POST /review/{id}/reject      — reject as noise
    POST /review/{id}/retry-summary — re-run AI summarization
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from brm.auth import require_api_key
from brm.db import get_session
from brm.lifecycle import (
    STATUS_IN_REVIEW,
    STATUS_PROCESSED,
    STATUS_REJECTED,
    STATUS_SUMMARY_FAILED,
    STATUS_VERIFIED,
    IllegalTransitionError,
    assert_transition,
)
from brm.models.change import Change
from brm.pipeline import run_summarize
from brm.schemas.api import (
    ApproveRequest,
    ChangeDetail,
    ChangeListItem,
    EditRequest,
    RejectRequest,
)

router = APIRouter(
    prefix="/review",
    tags=["review-queue"],
    dependencies=[Depends(require_api_key)],
)

# ---------------------------------------------------------------------------
# Helper: build ChangeDetail from a Change with loaded relationships
# ---------------------------------------------------------------------------


def _to_detail(change: Change) -> ChangeDetail:
    """Build a ChangeDetail response from a Change with loaded source."""
    return ChangeDetail(
        id=change.id,
        source_layer=change.source.layer,
        source_url=change.source.feed_url,
        headline=change.summary.get("headline") if change.summary else None,
        status=change.status,
        detected_at=change.detected_at,
        updated_at=change.updated_at,
        effective_date=change.effective_date,
        summary=change.summary,
        diff_text=change.diff_text,
        not_legal_advice_label=change.not_legal_advice_label,
        summary_error=change.summary_error,
    )


# ---------------------------------------------------------------------------
# GET /review/queue
# ---------------------------------------------------------------------------


@router.get("/queue", response_model=list[ChangeListItem])
async def get_queue(
    session: AsyncSession = Depends(get_session),
) -> list[ChangeListItem]:
    """Return changes awaiting review, ordered by detected_at DESC."""
    result = await session.execute(
        select(Change)
        .options(selectinload(Change.source))
        .where(
            Change.status.in_(
                [STATUS_PROCESSED, STATUS_IN_REVIEW, STATUS_SUMMARY_FAILED]
            )
        )
        .order_by(Change.detected_at.desc())
    )
    changes = result.scalars().all()
    return [
        ChangeListItem(
            id=c.id,
            source_layer=c.source.layer,
            headline=c.summary.get("headline") if c.summary else None,
            status=c.status,
            detected_at=c.detected_at,
            updated_at=c.updated_at,
            summary_error=c.summary_error,
        )
        for c in changes
    ]


# ---------------------------------------------------------------------------
# GET /review/{id}
# ---------------------------------------------------------------------------


@router.get("/{change_id}", response_model=ChangeDetail)
async def get_change(
    change_id: int,
    session: AsyncSession = Depends(get_session),
) -> ChangeDetail:
    """Return full detail for a single change (404 if not found)."""
    result = await session.execute(
        select(Change)
        .options(selectinload(Change.source), selectinload(Change.current_snapshot))
        .where(Change.id == change_id)
    )
    change = result.scalars().first()
    if change is None:
        raise HTTPException(status_code=404, detail="Change not found")
    return _to_detail(change)


# ---------------------------------------------------------------------------
# POST /review/{id}/approve
# ---------------------------------------------------------------------------


@router.post("/{change_id}/approve", response_model=ChangeDetail)
async def approve_change(
    change_id: int,
    body: ApproveRequest,
    session: AsyncSession = Depends(get_session),
) -> ChangeDetail:
    """Approve a change — sets status=verified and records the effective date."""
    # Lock the row first, then eager-load relationships.
    result = await session.execute(
        select(Change).where(Change.id == change_id).with_for_update()
    )
    change = result.scalars().first()
    if change is None:
        raise HTTPException(status_code=404, detail="Change not found")

    assert_transition(change.status, STATUS_VERIFIED)

    change.effective_date = body.effective_date
    change.reviewer_name = body.reviewer_name
    change.status = STATUS_VERIFIED

    await session.flush()
    await session.refresh(change, ["source"])
    await session.commit()
    return _to_detail(change)


# ---------------------------------------------------------------------------
# POST /review/{id}/edit
# ---------------------------------------------------------------------------


@router.post("/{change_id}/edit", response_model=ChangeDetail)
async def edit_change(
    change_id: int,
    body: EditRequest,
    session: AsyncSession = Depends(get_session),
) -> ChangeDetail:
    """Replace the AI summary and move change to in_review (supports self-loop)."""
    result = await session.execute(
        select(Change).where(Change.id == change_id).with_for_update()
    )
    change = result.scalars().first()
    if change is None:
        raise HTTPException(status_code=404, detail="Change not found")

    assert_transition(change.status, STATUS_IN_REVIEW)

    change.summary = body.summary.model_dump()
    change.reviewer_name = body.reviewer_name
    change.status = STATUS_IN_REVIEW

    await session.flush()
    await session.refresh(change, ["source"])
    await session.commit()
    return _to_detail(change)


# ---------------------------------------------------------------------------
# POST /review/{id}/reject
# ---------------------------------------------------------------------------


@router.post("/{change_id}/reject", response_model=ChangeDetail)
async def reject_change(
    change_id: int,
    body: RejectRequest,
    session: AsyncSession = Depends(get_session),
) -> ChangeDetail:
    """Reject a change as noise."""
    result = await session.execute(
        select(Change).where(Change.id == change_id).with_for_update()
    )
    change = result.scalars().first()
    if change is None:
        raise HTTPException(status_code=404, detail="Change not found")

    assert_transition(change.status, STATUS_REJECTED)

    change.status = STATUS_REJECTED
    change.reviewer_name = body.reviewer_name

    await session.flush()
    await session.refresh(change, ["source"])
    await session.commit()
    return _to_detail(change)


# ---------------------------------------------------------------------------
# POST /review/{id}/retry-summary
# ---------------------------------------------------------------------------


@router.post("/{change_id}/retry-summary", response_model=ChangeDetail)
async def retry_summary(
    change_id: int,
    session: AsyncSession = Depends(get_session),
) -> ChangeDetail:
    """Re-run AI summarization for a summary_failed change."""
    result = await session.execute(
        select(Change).where(Change.id == change_id).with_for_update()
    )
    change = result.scalars().first()
    if change is None:
        raise HTTPException(status_code=404, detail="Change not found")

    await run_summarize(session, change)
    await session.refresh(change, ["source"])
    await session.commit()
    return _to_detail(change)
