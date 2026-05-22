"""SourceAdapter Protocol — the ingestion seam.

All source adapters (FRBP HTML adapter, future RSS/HTML/PDF adapters) implement
this Protocol.  The Protocol is structural (runtime_checkable) so adapters can
satisfy it without explicit subclassing — each adapter is just a class with an
async fetch method.

Phase 2 will add HtmlAdapter and PdfAdapter behind this same seam; the FRBP
adapter in rss.py is the first concrete implementation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from brm.models.source import Source

from brm.ingest.outcome import FetchResult


@runtime_checkable
class SourceAdapter(Protocol):
    """Protocol for a source-fetching adapter."""

    async def fetch(self, source: "Source") -> FetchResult:
        """Fetch the source and return a tri-state result."""
        ...
