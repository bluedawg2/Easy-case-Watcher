"""Snapshot ORM model — append-only versioned content store (INGEST-05).

One row per successful fetch that produced new content.  Rows are INSERT-only;
no UPDATE or DELETE in normal operation.

The UNIQUE(source_id, version) constraint turns a concurrent version-number race
in store_snapshot into a hard DB error instead of silent lineage corruption
(review finding #5 / KIMI finding #7).  A losing concurrent insert fails
cleanly and can be retried.
"""

from datetime import UTC, datetime

from sqlalchemy import ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from brm.db import Base


class Snapshot(Base):
    """Immutable versioned snapshot of a source's normalized content.

    Columns
    -------
    id           : surrogate PK
    source_id    : FK → source.id
    content      : normalized text content (the content that was diffed)
    content_hash : SHA-256 hex digest of the normalized content
    version      : monotonic integer per source (1, 2, 3, …)
    fetched_at   : UTC datetime when this snapshot was recorded
    created_at   : row-creation timestamp (UTC)
    """

    __tablename__ = "snapshot"
    __table_args__ = (
        # Turning the version-number race into a hard DB integrity error.
        UniqueConstraint("source_id", "version", name="uq_snapshot_source_version"),
        # Index to speed up max(version) look-ups during store_snapshot.
        Index("idx_snapshot_source_id", "source_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("source.id"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(nullable=False)
    version: Mapped[int] = mapped_column(nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default="now()",
    )

    def __repr__(self) -> str:
        return (
            f"<Snapshot id={self.id} source_id={self.source_id} version={self.version}>"
        )
