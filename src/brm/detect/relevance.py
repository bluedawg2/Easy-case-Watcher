"""FRBP relevance predicate — pure, no I/O.

An amendment-cycle entry is FRBP-relevant if any item in its rule_families
list mentions Bankruptcy Rules, Bankruptcy Rule (singular), or Official Forms.
This filter provides defence-in-depth: the rulemaking page is FRBP-scoped, but
Civil/Appellate/Criminal amendments appear alongside FRBP ones; we don't want
those to trigger a spurious FRBP change record.
"""

from __future__ import annotations

import re

_FRBP_PATTERN = re.compile(
    r"bankruptcy\s+rules?\b|official\s+forms?\b",
    re.IGNORECASE,
)


def is_frbp_relevant(entry: dict) -> bool:
    """Return True if any rule_family item signals a Bankruptcy Rule amendment.

    Args:
        entry: Dict with keys effective_date (str), rule_families (list[str]),
               document_links (list[dict]).

    Returns:
        True if at least one rule_families item matches the FRBP signal pattern.
    """
    return any(_FRBP_PATTERN.search(item) for item in entry.get("rule_families", []))
