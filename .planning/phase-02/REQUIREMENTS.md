# Phase 2: HTML Scraping & Source Health - Requirements Analysis

## Phase Goal
Widen ingestion to scraped court-website HTML pages and make silent scraper failure impossible to mistake for "no change."

## Business Impact
This phase significantly expands the system's coverage beyond RSS feeds to include direct scraping of court websites, which is essential for comprehensive bankruptcy rule monitoring. It addresses a critical operational risk: silent scraper failures that could be mistaken for legitimate "no change" conditions.

## Key Requirements
1. **HTML Ingestion**: System must ingest changes by scraping court-website HTML pages with per-source extraction configuration
2. **Source Health Monitoring**: Distinguish "checked, no change" from "checked, error" from "not checked"
3. **Failure Detection**: Ensure that content-related errors (soft-404, login walls, empty pages) are recorded as failures rather than "no change"
4. **Source Onboarding**: Enable new HTML sources to be onboarded via configuration only, without code changes
5. **Politeness Policy**: Implement per-source politeness ceilings to respect rate limits and conditional requests

## Implementation Approach
- Create HTML fetcher adapter with per-source extraction configuration
- Implement tri-state fetch hardening with content fingerprints
- Develop source health model with staleness alarms and layout-drift alerting
- Establish config-only source onboarding with politeness ceilings
- Implement cross-channel change deduplication by change identity

## Technical Considerations
- Content normalization to strip boilerplate and navigation elements
- Per-source expected-content fingerprints to detect broken scrapers
- Adaptive error handling for various failure modes (404, login walls, etc.)
- Rate limiting and politeness policies to respect court website constraints
- Deduplication logic to prevent duplicate change processing

## Dependencies
This phase depends on Phase 1 completion, as it builds on the existing backend infrastructure and data models established in Phase 1.

## Success Criteria Alignment
The implementation must ensure:
1. Proper HTML content extraction with boilerplate isolation
2. Reliable source health monitoring and error detection
3. Robust content fingerprinting for scraper validation
4. Configurable source onboarding without code changes
5. Effective cross-channel deduplication