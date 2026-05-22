"""Hash-gate + textual diff helpers — RESEARCH Pattern 4.

Pure functions, stdlib only (difflib + hashlib).  No third-party diff library.

content_hash: SHA-256 over UTF-8 encoded normalized text.
textual_diff: difflib unified diff of prior vs current normalized text.
"""

from __future__ import annotations

import difflib
import hashlib


def content_hash(normalized: str) -> str:
    """Return the SHA-256 hex digest of the normalized content string.

    Args:
        normalized: The canonical normalized text from detect/normalize.py.

    Returns:
        A 64-character lowercase hexadecimal string (SHA-256).
    """
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def textual_diff(old: str, new: str) -> str:
    """Produce a unified diff of old vs new normalized content.

    Uses stdlib difflib.unified_diff — no third-party library.
    Returns an empty string when old == new.

    Args:
        old: Prior normalized content.
        new: Current normalized content.

    Returns:
        A unified diff string with '--- previous' / '+++ current' headers.
        Empty string if content is identical.
    """
    return "".join(
        difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile="previous",
            tofile="current",
        )
    )
