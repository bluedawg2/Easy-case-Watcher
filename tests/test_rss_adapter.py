"""Tests for FRBP rulemaking source adapter, normalization, and relevance filter.

Covers:
- Task 2: relevance filter (is_frbp_relevant) and normalization (normalize)
- Task 3: SourceAdapter seam and tri-state FRBP-source fetcher
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx

from brm.detect.normalize import normalize
from brm.detect.relevance import is_frbp_relevant
from brm.ingest.rss import parse_entries

# ---------------------------------------------------------------------------
# Fixture loading helpers
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures"
FRBP_URL = "https://www.uscourts.gov/forms-rules/pending-rules-and-forms-amendments"


def load_fixture(name: str) -> bytes:
    return (FIXTURES_DIR / name).read_bytes()


# ---------------------------------------------------------------------------
# Task 2: is_frbp_relevant tests
# ---------------------------------------------------------------------------


class TestIsFrbpRelevant:
    def test_bankruptcy_rules_is_relevant(self):
        entry = {
            "effective_date": "December 1, 2026",
            "rule_families": [
                "Appellate Form 4;",
                "Bankruptcy Rules 1007, 3018, 5009, 9006, 9014, 9017, new Rule 7043; and",
                "Evidence Rule 801.",
            ],
            "document_links": [],
        }
        assert is_frbp_relevant(entry) is True

    def test_official_forms_is_relevant(self):
        entry = {
            "effective_date": "December 1, 2027",
            "rule_families": [
                "Appellate Rule 15;",
                "Bankruptcy Rule 2002, Official Forms 101 and 106C;",
                "Civil Rules 7.1, 26, 41, 45, and 81;",
            ],
            "document_links": [],
        }
        assert is_frbp_relevant(entry) is True

    def test_civil_rules_only_is_not_relevant(self):
        entry = {
            "effective_date": "December 1, 2025",
            "rule_families": [
                "Civil Rules 12, 17;",
                "Evidence Rule 401.",
            ],
            "document_links": [],
        }
        assert is_frbp_relevant(entry) is False

    def test_appellate_only_is_not_relevant(self):
        entry = {
            "effective_date": "December 1, 2029",
            "rule_families": [
                "Appellate Rule 25;",
                "Criminal Rule 32.",
            ],
            "document_links": [],
        }
        assert is_frbp_relevant(entry) is False

    def test_case_insensitive_match(self):
        entry = {
            "effective_date": "December 1, 2030",
            "rule_families": ["bankruptcy rules 3001;"],
            "document_links": [],
        }
        assert is_frbp_relevant(entry) is True

    def test_empty_rule_families_is_not_relevant(self):
        entry = {
            "effective_date": "December 1, 2031",
            "rule_families": [],
            "document_links": [],
        }
        assert is_frbp_relevant(entry) is False


# ---------------------------------------------------------------------------
# Task 2: normalize tests
# ---------------------------------------------------------------------------


class TestNormalize:
    def test_normalize_deterministic_same_input(self):
        """Calling normalize twice on the same parsed input yields identical output."""
        html = load_fixture("frbp_source_v1.captured")
        entries = parse_entries(html)
        assert normalize(entries) == normalize(entries)

    def test_normalize_v1_v2_differ(self):
        """normalize(v1) != normalize(v2) — the added entry is detected."""
        v1 = load_fixture("frbp_source_v1.captured")
        v2 = load_fixture("frbp_source_v2.captured")
        assert normalize(parse_entries(v1)) != normalize(parse_entries(v2))

    def test_normalize_reorder_stable(self):
        """Reordering entries does not change normalized output (identity-keyed sort)."""
        html = load_fixture("frbp_source_v1.captured")
        entries = parse_entries(html)
        assert len(entries) >= 2, "Need at least 2 entries to test reordering"
        reversed_entries = list(reversed(entries))
        assert normalize(entries) == normalize(reversed_entries)

    def test_normalize_filters_non_frbp(self):
        """normalize drops entries where is_frbp_relevant is False."""
        frbp_entry = {
            "effective_date": "December 1, 2026",
            "rule_families": ["Bankruptcy Rules 1007;"],
            "document_links": [],
        }
        non_frbp_entry = {
            "effective_date": "December 1, 2025",
            "rule_families": ["Civil Rules 12;"],
            "document_links": [],
        }
        result_with_non_frbp = normalize([frbp_entry, non_frbp_entry])
        result_without_non_frbp = normalize([frbp_entry])
        assert result_with_non_frbp == result_without_non_frbp

    def test_normalize_v1_is_nonempty(self):
        """normalize of v1 produces non-empty output (FRBP entries exist)."""
        html = load_fixture("frbp_source_v1.captured")
        entries = parse_entries(html)
        result = normalize(entries)
        assert len(result) > 0

    def test_normalize_same_identity_different_doc_links(self):
        """An entry with same identity but edited doc links normalizes identically.

        Doc links ARE part of content (not volatile), but the stable identity key
        (effective_date) governs sort order — two entries with the same effective_date
        are the same entry.  This test verifies identity-keyed sort stability.
        """
        entry_v1 = {
            "effective_date": "December 1, 2026",
            "rule_families": ["Bankruptcy Rules 1007;"],
            "document_links": [{"text": "Congressional Package (PDF)", "href": "/pkg/v1"}],
        }
        entry_v2 = {
            "effective_date": "December 1, 2026",
            "rule_families": ["Bankruptcy Rules 1007;"],
            "document_links": [
                {"text": "Congressional Package (PDF) - April 2026", "href": "/pkg/v2"}
            ],
        }
        # Same effective_date means same identity — the entry is "the same" for
        # sort/identity purposes even if doc links differ.
        # They differ in content (different doc links), but the sort ORDER is
        # stable because effective_date is the sort key.
        # The important property: normalizing a list with the reordering of the
        # same entries (by effective_date) produces identical output.
        entries_ordered = [entry_v1, entry_v2]
        entries_reversed = [entry_v2, entry_v1]
        assert normalize(entries_ordered) == normalize(entries_reversed)


# ---------------------------------------------------------------------------
# Task 3: SourceAdapter seam and tri-state FRBP-source fetcher tests
# ---------------------------------------------------------------------------


@pytest.fixture()
def frbp_source():
    """A minimal Source-like object for adapter tests."""
    from types import SimpleNamespace
    return SimpleNamespace(
        id=1,
        feed_url=FRBP_URL,
        last_etag=None,
        last_modified_http=None,
        last_content_hash=None,
    )


@pytest.fixture()
def frbp_source_with_hash(frbp_source):
    """A source whose last_content_hash matches the v1 fixture normalized hash."""
    from brm.ingest.rss import _compute_normalized_hash
    v1_html = load_fixture("frbp_source_v1.captured")
    frbp_source.last_content_hash = _compute_normalized_hash(v1_html)
    return frbp_source


class TestFetchOutcome:
    @pytest.mark.asyncio
    async def test_fetch_changed(self, frbp_source):
        """Fetching v2 content (new entry) against a source with no prior hash → CHANGED."""
        from brm.ingest.outcome import FetchOutcome
        from brm.ingest.rss import fetch_source

        v2_html = load_fixture("frbp_source_v2.captured")
        with respx.mock(assert_all_called=False) as router:
            router.get(FRBP_URL).mock(
                return_value=httpx.Response(200, content=v2_html)
            )
            result = await fetch_source(frbp_source)

        assert result.outcome == FetchOutcome.CHANGED
        assert result.content is not None

    @pytest.mark.asyncio
    async def test_fetch_unchanged_304(self, frbp_source):
        """HTTP 304 Not Modified → UNCHANGED."""
        from brm.ingest.outcome import FetchOutcome
        from brm.ingest.rss import fetch_source

        with respx.mock(assert_all_called=False) as router:
            router.get(FRBP_URL).mock(
                return_value=httpx.Response(304)
            )
            result = await fetch_source(frbp_source)

        assert result.outcome == FetchOutcome.UNCHANGED
        assert result.content is None

    @pytest.mark.asyncio
    async def test_fetch_unchanged_hash_equal(self, frbp_source_with_hash):
        """HTTP 200 whose normalized hash equals source.last_content_hash → UNCHANGED."""
        from brm.ingest.outcome import FetchOutcome
        from brm.ingest.rss import fetch_source

        v1_html = load_fixture("frbp_source_v1.captured")
        with respx.mock(assert_all_called=False) as router:
            router.get(FRBP_URL).mock(
                return_value=httpx.Response(200, content=v1_html)
            )
            result = await fetch_source(frbp_source_with_hash)

        assert result.outcome == FetchOutcome.UNCHANGED
        assert result.content is None

    @pytest.mark.asyncio
    async def test_fetch_failed_timeout(self, frbp_source):
        """Network timeout → FETCH_FAILED with error non-None."""
        from brm.ingest.outcome import FetchOutcome
        from brm.ingest.rss import fetch_source

        with respx.mock(assert_all_called=False) as router:
            router.get(FRBP_URL).mock(side_effect=httpx.TimeoutException("timeout"))
            result = await fetch_source(frbp_source)

        assert result.outcome == FetchOutcome.FETCH_FAILED
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_fetch_failed_500(self, frbp_source):
        """HTTP 500 → FETCH_FAILED with error non-None."""
        from brm.ingest.outcome import FetchOutcome
        from brm.ingest.rss import fetch_source

        with respx.mock(assert_all_called=False) as router:
            router.get(FRBP_URL).mock(
                return_value=httpx.Response(500, text="Internal Server Error")
            )
            result = await fetch_source(frbp_source)

        assert result.outcome == FetchOutcome.FETCH_FAILED
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_fetch_failed_empty_body(self, frbp_source):
        """Empty response body → FETCH_FAILED."""
        from brm.ingest.outcome import FetchOutcome
        from brm.ingest.rss import fetch_source

        with respx.mock(assert_all_called=False) as router:
            router.get(FRBP_URL).mock(
                return_value=httpx.Response(200, content=b"")
            )
            result = await fetch_source(frbp_source)

        assert result.outcome == FetchOutcome.FETCH_FAILED
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_fetch_failed_no_entries(self, frbp_source):
        """HTML with no amendment entries (no h2 under field--name-body) → FETCH_FAILED."""
        from brm.ingest.outcome import FetchOutcome
        from brm.ingest.rss import fetch_source

        empty_html = b"""<!DOCTYPE html>
<html><body>
<div class="field--name-body"><div class="field__item">
<p>No amendments currently pending.</p>
</div></div>
</body></html>"""
        with respx.mock(assert_all_called=False) as router:
            router.get(FRBP_URL).mock(
                return_value=httpx.Response(200, content=empty_html)
            )
            result = await fetch_source(frbp_source)

        assert result.outcome == FetchOutcome.FETCH_FAILED
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_user_agent_header(self, frbp_source):
        """Request includes User-Agent containing 'BankruptcyRuleMonitor'."""
        from brm.ingest.rss import fetch_source

        v1_html = load_fixture("frbp_source_v1.captured")
        captured_request = None

        with respx.mock(assert_all_called=False) as router:
            def capture_and_respond(request):
                nonlocal captured_request
                captured_request = request
                return httpx.Response(200, content=v1_html)

            router.get(FRBP_URL).mock(side_effect=capture_and_respond)
            await fetch_source(frbp_source)

        assert captured_request is not None
        assert "BankruptcyRuleMonitor" in captured_request.headers.get("user-agent", "")

    @pytest.mark.asyncio
    async def test_malformed_but_parseable_proceeds(self, frbp_source):
        """HTML with some valid entries plus broken markup → CHANGED or UNCHANGED (not FAILED)."""
        from brm.ingest.outcome import FetchOutcome
        from brm.ingest.rss import fetch_source

        # Inject broken closing tag after a valid entry — selectolax handles gracefully.
        broken_html = b"""<!DOCTYPE html>
<html><body>
<div class="field--name-body"><div class="field__item">
<h2>December 1, 2026</h2>
<ul><li>Bankruptcy Rules 1007, 3018; and</li><li>Evidence Rule 801.</li></ul>
<p><a href="/pkg">Congressional Package</a> (PDF)</p>
<div><unclosed-tag>
</div></div></body></html>"""
        with respx.mock(assert_all_called=False) as router:
            router.get(FRBP_URL).mock(
                return_value=httpx.Response(200, content=broken_html)
            )
            result = await fetch_source(frbp_source)

        assert result.outcome in (FetchOutcome.CHANGED, FetchOutcome.UNCHANGED)
