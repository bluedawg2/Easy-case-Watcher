"""Normalization — pure, no I/O.

Converts a list of parsed amendment-cycle entry dicts into a single canonical
string suitable for SHA-256 hashing and change detection.

Rules:
- Filter: keep only entries where is_frbp_relevant() is True.
- Sort by effective_date (stable identity key — review finding #9).
- Per entry: render effective_date, sorted rule_families lines, sorted doc hrefs.
- Document link text (e.g. "Congressional Package (PDF) - April 2026") is
  content, not a volatile timestamp — it is included.
- No HTTP-header timestamps (Last-Modified, ETag) are present in the HTML body;
  no render timestamps need stripping from the content region.
"""

from __future__ import annotations

from brm.detect.relevance import is_frbp_relevant


def normalize(entries: list[dict]) -> str:
    """Return a canonical string representation of FRBP-relevant entries.

    Args:
        entries: List of dicts, each with:
            - effective_date (str): e.g. "December 1, 2026"
            - rule_families (list[str]): li text items
            - document_links (list[dict]): each with 'text' and 'href' keys

    Returns:
        A stable string; identical for the same logical content regardless of
        the original ordering of entries in the source HTML.
    """
    relevant = [e for e in entries if is_frbp_relevant(e)]
    # Sort by effective_date first, then rule_families and doc link hrefs as
    # tie-breakers so output is fully deterministic regardless of input order.
    relevant.sort(
        key=lambda e: (
            e["effective_date"],
            sorted(e.get("rule_families", [])),
            sorted(lnk.get("href", "") for lnk in e.get("document_links", [])),
        )
    )

    blocks: list[str] = []
    for entry in relevant:
        date_line = entry["effective_date"]
        families_lines = "\n".join(sorted(entry.get("rule_families", [])))
        link_lines = "\n".join(
            sorted(
                f"{lnk.get('text', '')} {lnk.get('href', '')}".strip()
                for lnk in entry.get("document_links", [])
            )
        )
        block = f"{date_line}\n{families_lines}"
        if link_lines:
            block += f"\n{link_lines}"
        blocks.append(block)

    return "\n\n".join(blocks)
