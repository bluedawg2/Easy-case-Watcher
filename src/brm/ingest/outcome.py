"""Fetch outcome types — the tri-state result of one source poll.

Every code path in the fetcher resolves to exactly one FetchOutcome value.
CHANGED and FETCH_FAILED carry data; UNCHANGED carries only etag/modified headers.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class FetchOutcome(str, Enum):
    CHANGED = "changed"
    UNCHANGED = "unchanged"
    FETCH_FAILED = "fetch_failed"


@dataclass
class FetchResult:
    """Result of one fetch attempt against a monitored source.

    Attributes:
        outcome:            One of the three FetchOutcome values.
        content:            Normalized text content (set only on CHANGED).
        raw_etag:           ETag header value from the HTTP response (may be None).
        raw_last_modified:  Last-Modified header value from the HTTP response (may be None).
        error:              Human-readable error description (set only on FETCH_FAILED).
    """

    outcome: FetchOutcome
    content: str | None
    raw_etag: str | None
    raw_last_modified: str | None
    error: str | None
