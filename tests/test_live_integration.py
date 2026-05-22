"""Live-integration verification — opt-in, requires network.

Run with: uv run pytest -m live tests/test_live_integration.py
"""
import pytest

FRBP_URL = "https://www.uscourts.gov/forms-rules/pending-rules-and-forms-amendments"

pytestmark = pytest.mark.live


@pytest.mark.asyncio
async def test_live_frbp_fetch_parseable():
    """Real FRBP source is fetchable and returns a non-empty entry set."""
    from brm.ingest.outcome import FetchOutcome
    from brm.ingest.rss import FrbpSourceAdapter
    from brm.models.source import Source

    source = Source(
        jurisdiction="national",
        layer="FRBP",
        feed_url=FRBP_URL,
        ingestion_method="html",
        adapter_ref="frbp_rulemaking",
        polling_cadence="daily",
        health_status="unknown",
    )
    adapter = FrbpSourceAdapter()
    result = await adapter.fetch(source)

    assert result.outcome == FetchOutcome.CHANGED, (
        f"Expected CHANGED on first fetch, got {result.outcome}: {result.error}"
    )
    assert result.content, "Expected non-empty normalized content"


@pytest.mark.asyncio
async def test_live_frbp_schema_matches_verification():
    """Observed per-entry schema matches the fields recorded in 01-02-SOURCE-VERIFICATION.md."""
    import httpx

    from brm.ingest.rss import parse_entries

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        resp = await client.get(
            FRBP_URL,
            headers={"User-Agent": "BankruptcyRuleMonitor/1.0 (+internal monitoring)"},
        )
    assert resp.status_code == 200

    entries = parse_entries(resp.content)
    assert len(entries) > 0, "Expected at least one amendment entry"

    for entry in entries:
        assert "effective_date" in entry, f"Missing effective_date: {entry}"
        assert "rule_families" in entry, f"Missing rule_families: {entry}"
        assert isinstance(entry["rule_families"], list)
