"""Source ORM model — the rule-source registry (SRC-01).

One row per monitored source: jurisdiction, layer, feed URL, ingestion method,
adapter reference, polling cadence, fetch-state bookkeeping, and typed health.
"""

from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from brm.db import Base
from brm.lifecycle import HEALTH_STATUSES


class Source(Base):
    """Registry entry for one monitored rule source.

    Columns
    -------
    jurisdiction   : e.g. "national", "SDNY", "CA"
    layer          : e.g. "FRBP", "local_rules", "state_exemptions"
    feed_url       : canonical URL of the source feed or page
    ingestion_method : "rss" | "html" | "pdf"
    adapter_ref    : dotted-path or short key identifying the SourceAdapter impl
    polling_cadence : descriptive cadence string, e.g. "daily", "hourly"
                      (Phase 1: stored but NOT yet driven by any scheduler —
                       a documented Phase-1 limitation per SKELETON.md)
    last_checked_at : datetime of the most recent fetch attempt (nullable)
    last_changed_at : datetime of the most recent detected change (nullable)
    health_status   : typed value — "unknown" | "healthy" | "failed"
                      set to "healthy" on a successful fetch in run_ingest (plan 01-03)
                      set to "failed" on a FETCH_FAILED outcome
    last_etag       : HTTP ETag from the last successful 200 response (nullable)
    last_modified_http : HTTP Last-Modified header value (nullable)
    last_content_hash  : SHA-256 of the last normalized content (nullable)
    tenant_id       : nullable multi-tenancy seam (CLAUDE.md — nullable in Phase 1)
    created_at      : row-creation timestamp (UTC)
    """

    __tablename__ = "source"
    __table_args__ = (
        CheckConstraint(
            "health_status IN ('unknown', 'healthy', 'failed')",
            name="ck_source_health_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    jurisdiction: Mapped[str] = mapped_column(String, nullable=False)
    layer: Mapped[str] = mapped_column(String, nullable=False)
    feed_url: Mapped[str] = mapped_column(String, nullable=False)
    ingestion_method: Mapped[str] = mapped_column(String, nullable=False)
    adapter_ref: Mapped[str] = mapped_column(String, nullable=False)
    polling_cadence: Mapped[str] = mapped_column(String, nullable=False)

    last_checked_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_changed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    health_status: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="unknown",
        server_default="unknown",
    )

    last_etag: Mapped[str | None] = mapped_column(String, nullable=True)
    last_modified_http: Mapped[str | None] = mapped_column(String, nullable=True)
    last_content_hash: Mapped[str | None] = mapped_column(String, nullable=True)

    # Multi-tenancy seam — nullable in Phase 1; no per-tenant auth yet.
    tenant_id: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default="now()",
    )

    def __repr__(self) -> str:
        return f"<Source id={self.id} layer={self.layer!r} url={self.feed_url!r}>"

    @classmethod
    def valid_health_statuses(cls) -> set[str]:
        return HEALTH_STATUSES
