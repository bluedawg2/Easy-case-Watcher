"""Change ORM model — a detected rule change record (EFF-01, EFF-02).

Lifecycle status is stored as VARCHAR + CHECK constraint so the taxonomy can
be extended in Phases 5/6 without awkward ALTER TYPE migrations
(RESEARCH Pitfall 5 / Open Question 1 resolved: VARCHAR+CHECK).

Key design choices:
- detected_at (NOT NULL) vs effective_date (Date, NULLABLE):
  separate fields per EFF-01; effective_date is reviewer-entered per D-12.
- updated_at: auto-updated on every row change; the pull-API since-cursor
  (plan 01-05) orders on it.
- summary (JSONB): filled by the AI summarization step (plan 01-04).
- summary_error (Text): set when an AI call fails; drives the summary_failed
  state; includes a retry count (plan 01-04).
- idx_change_status index: every review-queue and pull-API query filters on
  status (review finding #21).
- idx_change_updated_at index: backs the since-cursor incremental pull query.
"""

from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from brm.db import Base
from brm.lifecycle import ALL_STATUSES, STATUS_DETECTED


class Change(Base):
    """A detected change between two snapshots of a rule source.

    Columns
    -------
    id                    : surrogate PK
    source_id             : FK → source.id
    prior_snapshot_id     : FK → snapshot.id, nullable (None on first-ever fetch)
    current_snapshot_id   : FK → snapshot.id
    status                : lifecycle status VARCHAR, restricted by CHECK constraint
    detected_at           : UTC datetime when the change was detected (NOT NULL)
    effective_date        : calendar date when the rule change takes effect (NULLABLE
                            until a reviewer enters it — D-12, EFF-01)
    diff_text             : unified diff text produced by difflib (Text, nullable)
    summary               : JSONB structured AI summary (D-05, D-09; filled plan 01-04)
    summary_error         : Text describing AI call failure and retry count (plan 01-04)
    not_legal_advice_label: server-side constant label for AI-06 (set in plan 01-04)
    reviewer_name         : free-text reviewer identity (plan 01-05; no login table)
    model_id              : AI model string for reproducibility (plan 01-04)
    tenant_id             : nullable multi-tenancy seam (CLAUDE.md)
    created_at            : row-creation timestamp (UTC)
    updated_at            : last-modified timestamp (UTC); auto-updated on write
    """

    __tablename__ = "change"
    __table_args__ = (
        CheckConstraint(
            "status IN ({})".format(
                ", ".join(f"'{s}'" for s in ALL_STATUSES)
            ),
            name="ck_change_status",
        ),
        # Review-queue and pull-API queries filter on status — index prevents
        # table scans as the table grows (review finding #21).
        Index("idx_change_status", "status"),
        # Pull-API since-cursor query orders on updated_at.
        Index("idx_change_updated_at", "updated_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("source.id"), nullable=False)
    prior_snapshot_id: Mapped[int | None] = mapped_column(
        ForeignKey("snapshot.id"), nullable=True
    )
    current_snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("snapshot.id"), nullable=False
    )

    # Lifecycle status — VARCHAR + CHECK (not a native PG ENUM; see module docstring).
    status: Mapped[str] = mapped_column(
        nullable=False,
        default=STATUS_DETECTED,
        server_default=STATUS_DETECTED,
    )

    # EFF-01 — two distinct date/datetime fields.
    detected_at: Mapped[datetime] = mapped_column(nullable=False)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    diff_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # JSONB fields — PostgreSQL-specific for structured storage.
    summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    summary_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    not_legal_advice_label: Mapped[str | None] = mapped_column(nullable=True)
    reviewer_name: Mapped[str | None] = mapped_column(nullable=True)
    model_id: Mapped[str | None] = mapped_column(nullable=True)

    # Multi-tenancy seam — nullable in Phase 1.
    tenant_id: Mapped[str | None] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=datetime.utcnow,
        server_default="now()",
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=datetime.utcnow,
        server_default="now()",
        onupdate=datetime.utcnow,
    )

    def __repr__(self) -> str:
        return f"<Change id={self.id} status={self.status!r} detected_at={self.detected_at}>"
