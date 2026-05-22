"""FRBP rulemaking source adapter.

Fetches https://www.uscourts.gov/forms-rules/pending-rules-and-forms-amendments,
a static HTML page (confirmed HTML by live fetch per 01-02-SOURCE-VERIFICATION.md).
Applies a thin HTML-list parse using selectolax to extract amendment-cycle entries.

This per-source HTML parse is behind the SourceAdapter seam — it is NOT the
general per-source HTML-scraping framework (Phase 2 scope).  Phase 2's HtmlAdapter
will not disturb this adapter.

Tri-state outcome (RESEARCH Pattern 2):
  - HTTP 304                         → UNCHANGED
  - Network error / timeout / non-2xx-non-304 / empty body / zero entries
                                     → FETCH_FAILED (error set)
  - HTTP 200, hash == last_content_hash
                                     → UNCHANGED
  - HTTP 200, hash != last_content_hash (or no prior hash)
                                     → CHANGED (content set)
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

import httpx
from selectolax.parser import HTMLParser

from brm.detect.normalize import normalize
from brm.ingest.outcome import FetchOutcome, FetchResult

if TYPE_CHECKING:
    from brm.models.source import Source

_USER_AGENT = "BankruptcyRuleMonitor/1.0 (+internal monitoring)"
_TIMEOUT = 30.0


def parse_entries(html: bytes) -> list[dict]:
    """Parse amendment-cycle entries from the FRBP rulemaking HTML page.

    Selects the content region (div.field--name-body > div.field__item), then
    walks its children grouping siblings by h2 headers.  Each h2 starts a new
    amendment-cycle entry.

    Args:
        html: Raw HTML bytes of the rulemaking page.

    Returns:
        List of entry dicts, each with:
            effective_date (str)       — the h2 text
            rule_families  (list[str]) — li text items from the ul after the h2
            document_links (list[dict])— {'text': ..., 'href': ...} from p > a tags
    """
    tree = HTMLParser(html)

    # Target the content region only — strips nav, header, footer boilerplate.
    # On the live page, field--name-body and field__item are on the SAME div element.
    # In synthetic test HTML they may be nested.  Use the innermost div that has
    # h2 elements as direct children (i.e., as immediate iter() siblings).
    outer = tree.css_first("div.field--name-body")
    if outer is None:
        outer = tree.css_first("div.field__item")
    if outer is None:
        return []

    # Descend into a nested field__item if the outer container's direct children
    # don't include any h2 elements (they are wrapped in an inner div).
    direct_tags = {n.tag for n in outer.iter()}
    if "h2" not in direct_tags:
        inner = outer.css_first(".field__item")
        if inner is not None:
            outer = inner

    container = outer

    entries: list[dict] = []
    current: dict | None = None

    # iter() yields direct children only; we need to handle ul/li and p/a nesting.
    for node in container.iter():
        tag = getattr(node, "tag", None)
        if tag is None:
            continue

        if tag == "h2":
            if current is not None:
                entries.append(current)
            current = {
                "effective_date": node.text(strip=True),
                "rule_families": [],
                "document_links": [],
            }

        elif tag == "ul" and current is not None:
            for li in node.css("li"):
                text = li.text(strip=True)
                if text:
                    current["rule_families"].append(text)

        elif tag == "p" and current is not None:
            for a in node.css("a"):
                href = a.attributes.get("href", "") or ""
                text = a.text(strip=True)
                if href and text:
                    current["document_links"].append({"text": text, "href": href})

    if current is not None:
        entries.append(current)

    return entries


def _compute_normalized_hash(html: bytes) -> str:
    """Parse and normalize HTML, returning the SHA-256 hex digest."""
    entries = parse_entries(html)
    normalized = normalize(entries)
    return hashlib.sha256(normalized.encode()).hexdigest()


async def fetch_source(source: "Source") -> FetchResult:
    """Fetch the FRBP rulemaking source and return a tri-state FetchResult.

    Args:
        source: A Source object (or compatible duck-typed object) with:
                feed_url, last_etag, last_modified_http, last_content_hash.

    Returns:
        FetchResult with outcome CHANGED, UNCHANGED, or FETCH_FAILED.
    """
    headers: dict[str, str] = {"User-Agent": _USER_AGENT}
    if source.last_etag:
        headers["If-None-Match"] = source.last_etag
    if source.last_modified_http:
        headers["If-Modified-Since"] = source.last_modified_http

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True) as client:
            response = await client.get(source.feed_url, headers=headers)
    except httpx.TimeoutException as exc:
        return FetchResult(
            outcome=FetchOutcome.FETCH_FAILED,
            content=None,
            raw_etag=None,
            raw_last_modified=None,
            error=f"Request timed out: {exc}",
        )
    except httpx.RequestError as exc:
        return FetchResult(
            outcome=FetchOutcome.FETCH_FAILED,
            content=None,
            raw_etag=None,
            raw_last_modified=None,
            error=f"Network error: {exc}",
        )

    raw_etag = response.headers.get("etag")
    raw_last_modified = response.headers.get("last-modified")

    if response.status_code == 304:
        return FetchResult(
            outcome=FetchOutcome.UNCHANGED,
            content=None,
            raw_etag=raw_etag,
            raw_last_modified=raw_last_modified,
            error=None,
        )

    if response.status_code != 200:
        return FetchResult(
            outcome=FetchOutcome.FETCH_FAILED,
            content=None,
            raw_etag=raw_etag,
            raw_last_modified=raw_last_modified,
            error=f"HTTP {response.status_code}: {response.text[:200]}",
        )

    body = response.content
    if not body:
        return FetchResult(
            outcome=FetchOutcome.FETCH_FAILED,
            content=None,
            raw_etag=raw_etag,
            raw_last_modified=raw_last_modified,
            error="Empty response body",
        )

    entries = parse_entries(body)
    if not entries:
        return FetchResult(
            outcome=FetchOutcome.FETCH_FAILED,
            content=None,
            raw_etag=raw_etag,
            raw_last_modified=raw_last_modified,
            error="No amendment entries found in response",
        )

    normalized_text = normalize(entries)
    content_hash = hashlib.sha256(normalized_text.encode()).hexdigest()

    if source.last_content_hash and content_hash == source.last_content_hash:
        return FetchResult(
            outcome=FetchOutcome.UNCHANGED,
            content=None,
            raw_etag=raw_etag,
            raw_last_modified=raw_last_modified,
            error=None,
        )

    return FetchResult(
        outcome=FetchOutcome.CHANGED,
        content=normalized_text,
        raw_etag=raw_etag,
        raw_last_modified=raw_last_modified,
        error=None,
    )


class FrbpSourceAdapter:
    """SourceAdapter implementation for the FRBP rulemaking page."""

    async def fetch(self, source: "Source") -> FetchResult:
        return await fetch_source(source)
