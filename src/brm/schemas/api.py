"""Pydantic schemas for the review-queue and pull-delivery API endpoints."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel

from brm.schemas.summary import ChangeSummary


class ChangeListItem(BaseModel):
    """Lightweight item for the review-queue list endpoint."""

    id: int
    source_layer: str
    headline: str | None
    status: str
    detected_at: datetime
    updated_at: datetime
    summary_error: str | None = None

    model_config = {"from_attributes": True}


class ChangeDetail(BaseModel):
    """Full detail view of a Change, including diff text and summary."""

    id: int
    source_layer: str
    source_url: str
    headline: str | None
    status: str
    detected_at: datetime
    updated_at: datetime
    effective_date: date | None
    summary: dict | None
    diff_text: str | None
    not_legal_advice_label: str | None
    summary_error: str | None = None

    model_config = {"from_attributes": True}


class ApproveRequest(BaseModel):
    """Request body for the approve endpoint.  effective_date is required."""

    effective_date: date  # 422 if missing
    reviewer_name: str


class EditRequest(BaseModel):
    """Request body for the edit endpoint — replaces the AI-generated summary."""

    summary: ChangeSummary
    reviewer_name: str


class RejectRequest(BaseModel):
    """Request body for the reject endpoint."""

    reviewer_name: str


class ChangeOut(BaseModel):
    """Schema for the pull-delivery API — verified changes consumed by the other product."""

    id: int
    source_layer: str
    source_url: str
    headline: str | None
    summary: dict | None
    not_legal_advice_label: str | None
    diff_text: str | None
    detected_at: datetime
    effective_date: date | None
    status: str
    updated_at: datetime

    model_config = {"from_attributes": True}
