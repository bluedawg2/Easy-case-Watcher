# Phase 2: HTML Scraping & Source Health - Research

**Researched:** 2026-05-21
**Domain:** Async HTML scraping, content-region extraction, source-health/staleness monitoring, cross-channel change deduplication
**Confidence:** HIGH (pilot source live-verified; stack locked & verified; established Phase 1 seams inspected directly in `src/brm/`)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** The Phase 2 HTML source is the uscourts.gov rulemaking *page* that Phase 1's FRBP RSS feed already points at — the same rulemaking content via a second channel, so cross-channel dedup is genuinely demonstrable end-to-end. District/state pages deferred to Phase 3.
- **D-02:** The *specific* HTML page URL and its CSS structure are a research task (resolved below — see "Pilot HTML Source"). The *kind* of source is locked.
- **D-03:** Each Source registry row carries a documented per-source compliance record — robots.txt reviewed, ToS checked, crawl-delay noted. Onboarding is not complete until this record is filled.
- **D-04:** Public, unauthenticated pages only for v1. PACER and any login/auth-gated source are excluded from v1. No stored per-source credentials in this phase.
- **D-05:** Per-source extraction config = a CSS selector to the rule-text region + a small fixed vocabulary of declarative cleanup rules (strip elements by selector; drop nav/header/footer). It must NOT include arbitrary per-source transform/regex code.
- **D-06:** Extraction config lives as a JSONB column on the Source registry row. Onboarding a new HTML source is a DB insert — no code change, no deploy.
- **D-07:** When the configured selector matches nothing, or the extracted region comes back empty, the fetch resolves to FETCH_FAILED — never UNCHANGED, never a content change.
- **D-08:** The Phase 2 politeness ceiling = a per-source minimum interval between fetches, ETag / If-Modified-Since conditional requests, and a descriptive User-Agent on every request. Adaptive cadence is Phase 4.
- **D-09:** The per-source expected-content fingerprint is *structural*: the configured selector still resolves AND the extracted region's size sits within an expected band. Content-marker matching was rejected as too brittle.
- **D-10:** On layout drift (selector breaks / fingerprint fails) the fetch records FETCH_FAILED and raises an operator alert, but the source stays active and keeps being polled — it self-heals if the page recovers. A single drift event does NOT auto-pause.
- **D-11:** On a transient fetch failure (timeout, 5xx, connection reset) the fetcher does bounded retries with exponential backoff *within the single poll*; if still failing it records FETCH_FAILED and the next scheduled poll tries again.
- **D-12:** When a source fails repeatedly — a sustained run of consecutive FETCH_FAILED — it is auto-paused after a threshold (N consecutive failures) and escalated.
- **D-13:** Operators get a source-health read view listing every source with last-checked, last-changed, `health_status`, and consecutive-failure count — plus Sentry for exceptions.
- **D-14:** A source is *stale* when it has had no *successful* fetch (CHANGED or UNCHANGED) in N days. "No *change* in N days" is explicitly NOT staleness.
- **D-15:** The change-identity key for dedup is a hash of the normalized substantive rule text. The same text seen via any channel collapses to one Change record.
- **D-16:** On a duplicate detection the first-detected Change record stands; the second channel's observation is attached to it as an additional observation/snapshot. No second Change record; reviewer is not shown a duplicate.
- **D-17:** Phase 2 is validated via deterministic fixture replay — saved HTML fixtures cover every path (clean page, drifted layout, soft-404, login wall, empty-region, feed+scrape dedup pair). Detection/extraction logic runs identically on fixtures and live snapshots — no production-only branch.
- **D-18:** The validation matrix explicitly exercises and asserts the source-health guarantees, not just the happy path: staleness alert fires, drift raises FETCH_FAILED, auto-pause triggers after N consecutive failures, soft-404/login-wall classified as FETCH_FAILED.

### Claude's Discretion

- Exact values for the tunable thresholds — `N` staleness days, `N` auto-pause consecutive-failure count, retry count / backoff schedule, expected-size band tolerance for the structural fingerprint. (Sensible defaults recommended below; per-source overridable where cheap.)
- The exact uscourts.gov HTML page URL and its CSS selectors (resolved below).
- Whether the source-health read view is a JSON API endpoint, a CLI command, or a minimal admin page — planner picks the lightest fit for an internal-only v1 tool.
- HTML parsing/fetching library specifics within the locked stack (httpx + selectolax), snapshot retention, alert-delivery wiring details.

### Deferred Ideas (OUT OF SCOPE)

- **District / state HTML pages** — Phase 2's pilot is a national rulemaking page only; district local-rules and state exemption pages are Phase 3 (SRC-03/SRC-04).
- **Adaptive polling cadence** — Phase 2 enforces only a per-source politeness *ceiling* (D-08). Cadence-driven scheduling is Phase 4 (INGEST-06). Phase 2 has NO scheduler/worker; ingest runs as a directly-invokable function (as in Phase 1).
- **PACER / login-gated sources** — excluded from v1 by D-04.
- **PDF extraction** — Phase 3.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INGEST-02 | System ingests changes by scraping court-website HTML pages | Pilot HTML source verified (`.field--name-body` selector isolates rule text); `HtmlSourceAdapter` behind the existing `SourceAdapter` Protocol; httpx+selectolax patterns (Pattern 1, Code Examples) |
| INGEST-07 | Polling respects a per-source politeness ceiling | Per-source `min_interval_seconds` gate, ETag/If-Modified-Since conditional requests, descriptive User-Agent (Pattern 4, D-08). Default-value table for politeness fields. |
| SRC-05 | Source-health monitoring distinguishes checked-no-change / checked-error / not-checked; alerts on staleness or layout drift | Tri-state hardening + health-state model (Pattern 5), structural fingerprint (Pattern 3), staleness query (Pattern 6), Sentry alert wiring (Don't Hand-Roll). Threshold defaults table. |
| SRC-06 | A new source can be onboarded as a registry/config operation with no code change | Extraction config + politeness ceiling + compliance record all as columns/JSONB on `Source`; `HtmlSourceAdapter` is config-driven and source-agnostic (Pattern 1, Pattern 2). Onboarding = one DB insert. |
| DETECT-03 | Duplicate detections of the same change (feed + scrape) are deduplicated | Change-identity hash of normalized substantive rule text; `change_identity` column + dedup-on-insert; second observation attached via a `change_observation` row (Pattern 7). |
</phase_requirements>

## Summary

Phase 2 widens ingestion from RSS feeds to scraped HTML pages and hardens the system so a silently-broken scraper can never be mistaken for "no change." The pilot source is **live-verified**: `https://www.uscourts.gov/forms-rules/pending-rules-and-forms-amendments` returns HTTP 200, is a USWDS/Drupal page, exposes both `ETag` and `Last-Modified` headers (so conditional requests work), and — critically — has a single clean rule-text region at the CSS selector `.field--name-body` (1,712 chars of pure amendment text, no nav/header/footer chrome). This is the same rulemaking content Phase 1's FRBP source already tracks, so cross-channel dedup is a genuine end-to-end demo, not a contrived test. `robots.txt` was fetched and reviewed: it is the standard Drupal robots.txt, contains **no `Crawl-delay`**, and does **not** disallow `/forms-rules/` — scraping the pilot page is permitted.

The work builds directly on real Phase 1 seams inspected in `src/brm/`: the `SourceAdapter` Protocol (`src/brm/ingest/adapter.py`), the tri-state `FetchOutcome`/`FetchResult` contract (`src/brm/ingest/outcome.py`), the append-only `store_snapshot` store, the `run_ingest` pipeline orchestrator (`src/brm/pipeline.py`), the `Source`/`Snapshot`/`Change` ORM models, the `lifecycle.py` `HEALTH_STATUSES` set + `assert_transition` guard, and the `difflib`-based hash-gate detector. Phase 2 adds an `HtmlSourceAdapter` *behind the existing seam* — not a new fetch layer — and *extends* the existing tri-state outcome with HTML-specific failure detection (soft-404, login wall, empty region, layout drift). The entire stack is locked by CLAUDE.md and verified current: Python 3.12, **httpx 0.28.1**, **selectolax 0.4.9**, stdlib `difflib`/`hashlib`, PostgreSQL 16 + JSONB, SQLAlchemy 2.x + Alembic, Sentry (`sentry-sdk`).

**Primary recommendation:** Add a config-driven `HtmlSourceAdapter` implementing the existing `SourceAdapter` Protocol; drive extraction from a JSONB `extraction_config` column on `Source` (`{"content_selector": ".field--name-body", "strip_selectors": [...]}`); harden the tri-state outcome with explicit soft-404 / login-wall / empty-region / layout-drift classification (all → FETCH_FAILED, never UNCHANGED); add a structural fingerprint (selector-resolves + size-band) stored per source; track `consecutive_failure_count` and `last_successful_fetch_at` on `Source` to drive auto-pause (D-12) and staleness (D-14); add a `change_identity` SHA-256 column on `Change` keyed on normalized substantive text for cross-channel dedup, with second observations attached to a new `change_observation` table. Validate everything through deterministic fixture replay (D-17) including six failure-path HTML fixtures.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| HTML fetch (httpx, conditional requests, retries) | Backend (ingest adapter) | — | `HtmlSourceAdapter` behind the `SourceAdapter` seam; pure backend I/O |
| Rule-text region extraction (selectolax CSS + strip rules) | Backend (ingest adapter) | — | Config-driven parse; no browser, no client tier — pages are static HTML |
| Per-source extraction config | Database (JSONB column) | Backend (adapter reads it) | Config-as-data on the `Source` row (D-06) — onboarding is a DB insert |
| Tri-state outcome + failure classification | Backend (ingest) | — | Hardens the existing `FetchOutcome` enum; soft-404/login-wall/empty-region detection |
| Structural fingerprint compute/store/check | Backend (ingest) + Database | — | Fingerprint stored per `Source`; computed each fetch, compared in adapter |
| Source-health state (consecutive failures, staleness, auto-pause) | Database (`Source` columns) | Backend (pipeline updates them) | Health is durable per-source state; pipeline transitions it |
| Staleness / drift alerting | Backend (Sentry capture) | — | Sentry is the locked alert sink; staleness is a periodic/manual query |
| Source-health read view | Backend (FastAPI read endpoint **or** CLI) | — | Internal-only read surface; planner picks lightest fit |
| Cross-channel dedup (change identity) | Backend (detector) + Database | — | Identity hash computed in detector; uniqueness enforced by DB constraint |

**Tier note:** Phase 2 has **no scheduler/worker process** — Procrastinate is Phase 4 per ROADMAP. Ingest runs as a directly-invokable function (`run_ingest`, extended), triggered by CLI/test/manual endpoint, exactly as in Phase 1. Do not stand up a Procrastinate worker in Phase 2.

## Standard Stack

All choices are LOCKED in CLAUDE.md — versions below are verified current on PyPI as of 2026-05-21.

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| httpx | 0.28.1 `[VERIFIED: PyPI 2026-05-21]` | Async HTTP client — page fetch, conditional requests, timeouts | Locked in CLAUDE.md; async matches the existing async pipeline; HTTP/2, connection pooling, native timeout control. Already a project dependency (`pyproject.toml`). |
| selectolax | 0.4.9 `[VERIFIED: PyPI 2026-05-21]` | Fast C-backed HTML parsing / CSS-selector extraction | Locked in CLAUDE.md; `css_first()` / `css()` give the selector API D-05 needs; `.decompose()` gives declarative element stripping. Already a project dependency. |
| difflib (stdlib) | stdlib | Cheap deterministic diff pre-filter (reused from Phase 1) | Phase 1 `src/brm/detect/diff.py` already wraps it; no new dependency. |
| hashlib (stdlib) | stdlib | SHA-256 for content hash and change-identity hash | Reused from Phase 1 `content_hash`; change-identity hash (D-15) uses the same primitive. |
| SQLAlchemy + Alembic | 2.0.49 / 1.18.4 `[VERIFIED: pyproject.toml]` | ORM + migration for new `Source`/`Change` columns and the `change_observation` table | Locked; Phase 1 established the hand-written-migration discipline. |
| PostgreSQL JSONB | PG 16 | `extraction_config` and `compliance_record` columns on `Source` | Locked; D-06 mandates JSONB for the extraction config. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| sentry-sdk | 2.60.0 `[VERIFIED: PyPI 2026-05-21, slopcheck OK]` | Error monitoring + the staleness/drift alert sink (D-13) | CLAUDE.md names "Sentry" as load-bearing for the silently-broken-scraper pitfall. Add as a new dependency this phase. Use `sentry_sdk.capture_message(...)` for staleness/drift/auto-pause alerts and `capture_exception` for unexpected errors. Initialize lazily — a missing DSN must be a no-op, never a crash (see Pitfall 5). |
| respx | 0.23.1 (dev) `[VERIFIED: pyproject.toml]` | HTTP mocking for offline fixture-replay tests | Already a Phase 1 dev dependency; reused to replay the six HTML fixtures (D-17). |

### Backoff for D-11 (decision required by planner)
| Option | Recommendation | Tradeoff |
|--------|----------------|----------|
| stdlib loop (`for attempt in range(N): ... await asyncio.sleep(backoff)`) | **Recommended for Phase 2.** | ~15 lines, zero new dependency, fully testable with a mockable sleep. The retry policy is trivial (3 attempts, exponential backoff) — does not justify a library. Matches CLAUDE.md "Don't Hand-Roll" philosophy: this is *not* the hand-rolled category, it is a 3-line loop. |
| `tenacity` 9.1.4 `[VERIFIED: PyPI 2026-05-21, slopcheck OK]` | Alternative only if retry policy grows complex. | Mature, declarative `@retry` decorator with `wait_exponential`. Adds a dependency for what is currently a trivial loop. Reconsider in Phase 4 when adaptive polling lands. |

**Recommendation:** use a stdlib bounded-retry loop in Phase 2. Do not add `tenacity` yet. `[ASSUMED]` — confirm with planner; either is defensible.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| selectolax | BeautifulSoup | CLAUDE.md "What NOT to Use" does not forbid it, but selectolax is locked as the recommended parser; no reason to deviate. |
| selectolax | Playwright (headless browser) | CLAUDE.md: Playwright is an *escape hatch only*, per-source, when a page needs JS rendering. The pilot page is static HTML (verified — full content present in the raw `curl` body). Do NOT adopt Playwright in Phase 2. |
| stdlib retry loop | tenacity | See table above. |

**Installation:**
```bash
uv add sentry-sdk
# httpx, selectolax already in pyproject.toml; respx already a dev dependency
```

**Version verification (run 2026-05-21):**
- `httpx` — 0.28.1 (PyPI; pinned in `pyproject.toml`) — current
- `selectolax` — 0.4.9 (PyPI; unpinned in `pyproject.toml`, latest installed 0.4.9) — current; recommend pinning `selectolax==0.4.9`
- `sentry-sdk` — 2.60.0 (PyPI) — current; new dependency
- `tenacity` — 9.1.4 (PyPI) — current, if chosen

## Package Legitimacy Audit

> slopcheck 0.6.1 ran successfully against all candidate packages on 2026-05-21.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| httpx | PyPI | mature (since 2019) | very high | github.com/encode/httpx | [OK] | Approved — already a project dependency |
| selectolax | PyPI | mature (since 2018) | high | github.com/rushter/selectolax | [OK] | Approved — already a project dependency |
| sentry-sdk | PyPI | mature (since 2019) | very high | github.com/getsentry/sentry-python | [OK] (note: name ends with `-sdk`, classic LLM bait pattern, but package is established and verified) | Approved — new dependency this phase |
| tenacity | PyPI | mature (since 2016) | very high | github.com/jd/tenacity | [OK] | Approved *only if* the planner chooses the library route over the stdlib loop |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

All four packages are confirmed via CLAUDE.md (httpx, selectolax, Sentry are explicitly named in the locked stack) AND pass slopcheck `[OK]` AND are confirmed current on PyPI — they may be tagged `[VERIFIED]`.

## Pilot HTML Source (D-02 — resolved)

**The Phase 2 pilot HTML source is verified and live (fetched 2026-05-21).**

| Property | Value |
|----------|-------|
| URL | `https://www.uscourts.gov/forms-rules/pending-rules-and-forms-amendments` `[VERIFIED: curl HTTP 200, 2026-05-21]` |
| Type | Static HTML (USWDS / Drupal); full rule-text content present in the raw HTML body — **no JavaScript rendering required** `[VERIFIED: curl body inspected]` |
| HTTP status | 200 OK `[VERIFIED]` |
| Conditional-request headers | `ETag: "1779373834"` and `Last-Modified: Thu, 21 May 2026 14:30:34 GMT` both present `[VERIFIED]` — If-None-Match / If-Modified-Since are usable for the politeness ceiling (D-08) |
| `Cache-Control` | `max-age=604800, public` `[VERIFIED]` |
| Rule-text region selector | **`.field--name-body`** — isolates 1,712 chars of pure amendment text (proposed amendments organized by effective year, with PDF links) with no nav/header/footer chrome `[VERIFIED: selectolax extraction 2026-05-21]` |
| Fuller container (rejected) | `.region-content` (1,975 chars) includes the page `<h1>` "Pending Rules and Forms Amendments"; `main.container` (4,059 chars) includes the entire forms/rules nav menu — both pull in chrome. `.field--name-body` is the correct, tightest rule-text region. |
| Same content as Phase 1 | Yes — the page lists "Bankruptcy Rules 1007, 3018, 5009, 9006, 9014, 9017, new Rule 7043" effective Dec 1 2026, and "Bankruptcy Rule 2002, Official Forms 101 and 106C" effective Dec 1 2027 — the exact FRBP amendment material Phase 1's RESEARCH identified. Cross-channel dedup (D-15/D-16) is a real demo. `[VERIFIED]` |

**Compliance record (D-03) — verified for the pilot source:**

| Field | Value |
|-------|-------|
| robots.txt | `https://www.uscourts.gov/robots.txt` fetched 2026-05-21. Standard Drupal robots.txt. `User-agent: *`. **No `Crawl-delay` directive.** `/forms-rules/` is **not** in any `Disallow` rule (disallowed paths are `/admin/`, `/search/`, `/user/login`, `/comment/reply/`, `/node/add/`, `/federal-court-finder/`, etc.). `[VERIFIED]` |
| Scraping permitted? | **Yes** — the pilot page path is not disallowed. `[VERIFIED]` |
| ToS | uscourts.gov is U.S. government public infrastructure; the page is public and unauthenticated (D-04 satisfied). Court sites are government infrastructure — polite scraping (rate limit + descriptive UA) is the CLAUDE.md-mandated etiquette regardless of robots.txt silence. |
| Crawl-delay | None published. Recommended self-imposed per-source minimum interval: **daily** (the page changes a few times a year — see threshold defaults). |

**`[ASSUMED]` caveat:** The selector `.field--name-body` is correct *as of the page's current Drupal theme*. Drupal field-class names are stable across content edits but *can* change on a CMS theme upgrade — this is exactly the layout-drift condition D-09/D-10 are designed to catch. The structural fingerprint (size-band) is the safety net.

## Architecture Patterns

### System Architecture Diagram

```
                         ┌──────────────────────────────────────────────────┐
  FIXTURE PATH (D-17)     │  LIVE PATH (D-04/D-17) — identical code, no branch │
  6 saved HTML fixtures   │  uscourts.gov pending-amendments HTML page         │
  (clean, drift, soft-404,│  + Phase-1 FRBP feed (for the dedup pair)          │
   login-wall, empty,     └──────────────────────┬───────────────────────────┘
   feed+scrape pair)                             │
        │                                        │  httpx GET
        │                                        │  (If-None-Match / If-Modified-Since,
        │                                        │   descriptive User-Agent,
        │                                        │   per-source min-interval gate)
        │                                        ▼
        │                       ┌────────────────────────────────────┐
        └──────────────────────▶│  HtmlSourceAdapter.fetch(source)    │
        (respx replays bytes)   │  (implements SourceAdapter Protocol)│
                                └────────────────┬───────────────────┘
                                                 │
                          ┌──────────────────────┼───────────────────────┐
                          │ TRI-STATE CLASSIFICATION (hardened for HTML)  │
                          │                       │                       │
                  HTTP 304 / hash-equal     HTTP 200 + good content   failure signals:
                          │                       │                  - network err / timeout
                          ▼                       ▼                  - non-2xx-non-304 status
                     UNCHANGED               selectolax parse         - soft-404 (200 + 404 markers)
                          │                  → apply content_selector - login-wall markers
                          │                  → apply strip_selectors  - selector matches nothing (D-07)
                          │                  → extract rule-text      - extracted region empty (D-07)
                          │                       │                  - structural fingerprint fails (D-09)
                          │                  fingerprint check               │
                          │                  (selector resolves +             ▼
                          │                   size in expected band)     FETCH_FAILED
                          │                       │                  (+ Sentry alert on drift, D-10)
                          │                  normalize → SHA-256             │
                          │                       │                          │
                          │              hash == last? ──UNCHANGED            │
                          │                       │ no                       │
                          │                       ▼                          │
                          │                    CHANGED                       │
                          ▼                       ▼                          ▼
                ┌──────────────────────────────────────────────────────────────┐
                │  run_ingest (Phase 1 orchestrator, extended)                  │
                │  - CHANGED   → store_snapshot, detect_change                  │
                │  - UNCHANGED → health=healthy, reset consecutive_failure_count │
                │  - FETCH_FAILED → health=failed, ++consecutive_failure_count;  │
                │                   if count >= AUTO_PAUSE_N → health=paused     │
                │  - every outcome → last_checked_at = now                      │
                │  - CHANGED/UNCHANGED → last_successful_fetch_at = now (D-14)   │
                └──────────────────────────────┬────────────────────────────────┘
                                                │ on CHANGED
                                                ▼
                ┌──────────────────────────────────────────────────────────────┐
                │  detect_change → compute change_identity (SHA-256 of           │
                │  normalized substantive rule text, D-15)                       │
                │   - identity unseen  → new Change row (status=detected)         │
                │   - identity exists  → attach a change_observation row to the   │
                │                        existing Change; create NO new Change    │
                │                        (D-16)                                  │
                └────────────────────────────────────────────────────────────────┘

         ┌─────────────────────────────────────────────────────────────────┐
         │  STALENESS SWEEP (periodic / manual query — no scheduler yet)     │
         │  for each active source: now - last_successful_fetch_at > N days  │
         │     → Sentry alert "source stale" (D-14)                          │
         └─────────────────────────────────────────────────────────────────┘

         ┌─────────────────────────────────────────────────────────────────┐
         │  SOURCE-HEALTH READ VIEW (FastAPI read endpoint OR CLI, D-13)     │
         │  lists every source: last_checked / last_changed / health_status │
         │  / consecutive_failure_count / last_successful_fetch_at          │
         └─────────────────────────────────────────────────────────────────┘
```

### Recommended Project Structure
```
src/brm/
├── ingest/
│   ├── adapter.py          # EXISTING — SourceAdapter Protocol (Phase 1, unchanged)
│   ├── outcome.py          # EXISTING — FetchOutcome / FetchResult (Phase 1; see note below)
│   ├── rss.py              # EXISTING — FrbpSourceAdapter (Phase 1, unchanged)
│   ├── html.py             # NEW — HtmlSourceAdapter (config-driven; implements SourceAdapter)
│   ├── extract.py          # NEW — pure: apply content_selector + strip_selectors → rule text
│   ├── fingerprint.py      # NEW — pure: compute & check structural fingerprint (D-09)
│   ├── failure_detect.py   # NEW — pure: soft-404 / login-wall heuristics (D-07)
│   └── snapshot_store.py   # EXISTING — append-only store (Phase 1, unchanged)
├── detect/
│   ├── normalize.py        # EXISTING — Phase 1; reused for substantive-text normalization
│   ├── diff.py             # EXISTING — content_hash / textual_diff (Phase 1, unchanged)
│   ├── detector.py         # EXTENDED — add change-identity dedup (D-15/D-16)
│   └── identity.py         # NEW — pure: change_identity hash of normalized substantive text
├── health/
│   ├── staleness.py        # NEW — staleness sweep query + Sentry alert (D-14)
│   └── alerts.py           # NEW — thin Sentry wrapper (capture_message for drift/stale/pause)
├── models/
│   ├── source.py           # EXTENDED — extraction_config, compliance_record, fingerprint,
│   │                       #            politeness fields, consecutive_failure_count,
│   │                       #            last_successful_fetch_at  (Alembic migration)
│   ├── change.py           # EXTENDED — change_identity column + unique index
│   ├── change_observation.py  # NEW — second-channel observations attached to a Change (D-16)
│   └── snapshot.py         # EXISTING — unchanged
├── lifecycle.py            # EXTENDED — add "paused" to HEALTH_STATUSES (D-12)
├── pipeline.py             # EXTENDED — run_ingest handles failure counting / auto-pause
└── seed.py                 # EXTENDED — add the pilot HTML source row (config-only insert)
tests/fixtures/html/        # NEW — 6 HTML fixtures (clean, drift, soft404, login, empty, dedup)
```

### Pattern 1: Config-Driven HtmlSourceAdapter Behind the Existing Seam
**What:** A new `HtmlSourceAdapter` implementing the *existing* `SourceAdapter` Protocol (`src/brm/ingest/adapter.py`: `async def fetch(self, source: Source) -> FetchResult`). It is **source-agnostic** — all per-source behavior (which selector, which strip rules, what size band, what min interval) comes from columns on the `Source` row, never from code. This is what makes SRC-06 true: onboarding a new HTML source is a DB insert, and the *same* adapter class handles it.
**When to use:** All HTML sources, now and in Phase 3 (districts/states reuse this adapter unchanged).
**Example:**
```python
# src/brm/ingest/html.py — Source: project Phase 1 seam (src/brm/ingest/adapter.py) + httpx docs
class HtmlSourceAdapter:
    """Implements the SourceAdapter Protocol for config-driven HTML scraping."""

    async def fetch(self, source: Source) -> FetchResult:
        cfg = source.extraction_config          # JSONB: content_selector, strip_selectors
        headers = {"User-Agent": "BankruptcyRuleMonitor/1.0 (+internal monitoring)"}
        if source.last_etag:
            headers["If-None-Match"] = source.last_etag
        if source.last_modified_http:
            headers["If-Modified-Since"] = source.last_modified_http
        # ... (tri-state classification — see Pattern 2)
```

### Pattern 2: Hardened Tri-State Outcome — Every HTML Failure Mode → FETCH_FAILED
**What:** Phase 1's `FetchOutcome` (CHANGED / UNCHANGED / FETCH_FAILED) is *extended in coverage, not in enum values*. The HTML adapter must classify every one of these as **FETCH_FAILED** — never UNCHANGED, never a bogus content change:
- network error / timeout / connection reset (after bounded retry — D-11)
- non-2xx, non-304 HTTP status
- **soft-404**: HTTP 200 whose body contains 404/"page not found" markers (`failure_detect.py`)
- **login wall**: HTTP 200 whose body contains login/sign-in markers (`failure_detect.py`)
- **selector matches nothing** (D-07): `content_selector` resolves to zero nodes
- **empty region** (D-07): selector resolves but extracted text is empty/whitespace
- **structural fingerprint failure** (D-09): selector resolves but extracted size is outside the expected band → layout drift
- HTML 304 → UNCHANGED; HTML 200 with good content whose normalized hash equals `last_content_hash` → UNCHANGED; otherwise → CHANGED

**Critical invariant (from Phase 1 Pitfall 2, carried forward):** every code path provably sets exactly one outcome; no path returns without one. The validation matrix (D-18) asserts this for each failure mode.

**`FetchResult` extension note (planner decision):** The Phase 1 `FetchResult` dataclass is `outcome, content, raw_etag, raw_last_modified, error`. Phase 2 needs to distinguish *why* a fetch failed (drift vs soft-404 vs login-wall) to route alerts (drift → Sentry + keep polling per D-10). Recommended: add an optional `failure_reason: str | None` field to `FetchResult` (a small fixed vocabulary: `"drift"`, `"soft_404"`, `"login_wall"`, `"empty_region"`, `"selector_miss"`, `"transient"`, `"http_error"`). This is additive and does not break the Phase 1 RSS adapter. `[ASSUMED]` — confirm the extension with the planner.

### Pattern 3: Structural Fingerprint (D-09)
**What:** A per-source fingerprint that is *structural*, not content-based: it asserts (a) the configured `content_selector` still resolves to at least one node, and (b) the extracted region's character length sits within an expected band around a learned/seeded baseline. It catches layout drift (selector breaks) and stripped/truncated content without false-firing on legitimate rule-text changes.
**Storage:** A JSONB `structural_fingerprint` column on `Source`, e.g. `{"baseline_size": 1712, "tolerance_factor": 0.5}` → the accepted band is `[baseline_size * (1 - tol), baseline_size * (1 + tol)]`. The baseline is seeded from the first successful fetch (or set explicitly at onboarding).
**Check:** on each fetch, after extraction: if selector missed → FETCH_FAILED (`failure_reason="selector_miss"`); if `len(extracted)` outside band → FETCH_FAILED (`failure_reason="drift"`) + Sentry alert, **source stays active** (D-10).
**Example:**
```python
# src/brm/ingest/fingerprint.py — pure function, runs identically on fixtures and live (D-17)
def check_fingerprint(extracted_text: str, fingerprint: dict) -> tuple[bool, str | None]:
    baseline = fingerprint["baseline_size"]
    tol = fingerprint.get("tolerance_factor", 0.5)
    size = len(extracted_text)
    lo, hi = baseline * (1 - tol), baseline * (1 + tol)
    if not (lo <= size <= hi):
        return False, f"drift: size {size} outside band [{lo:.0f}, {hi:.0f}]"
    return True, None
```
**Why a size band, not a content marker:** D-09 explicitly rejected content-marker matching — when a rule legitimately changes, the markers change too, producing false drift alerts. A size band tolerates real content edits (a rule amendment adds/removes a few hundred chars) while still catching the catastrophic failures (selector returns the whole nav menu = 10x larger; selector returns empty = ~0).

### Pattern 4: Politeness Ceiling (D-08, INGEST-07)
**What:** Three enforced guarantees, all per-source, all config-driven:
1. **Per-source minimum interval** — a `min_interval_seconds` column on `Source`. Before fetching, `run_ingest` checks `now - last_checked_at >= min_interval_seconds`; if not, the poll is a no-op (skipped politely). This is a *ceiling*, not an adaptive schedule (Phase 4).
2. **Conditional requests** — send `If-None-Match` (`source.last_etag`) and `If-Modified-Since` (`source.last_modified_http`); a 304 response → UNCHANGED with no body transfer. The Phase 1 `Source` model *already has* `last_etag` and `last_modified_http` columns — reuse them.
3. **Descriptive User-Agent** — every request carries `User-Agent: BankruptcyRuleMonitor/1.0 (+internal monitoring)` (the exact string Phase 1's RSS adapter already uses — keep it consistent).

### Pattern 5: Source-Health State Model (SRC-05)
**What:** Health is durable per-source state, not a derived value. The Phase 1 `Source` model already has `health_status` (`"unknown" | "healthy" | "failed"`), `last_checked_at`, `last_changed_at`. Phase 2 adds:
- `consecutive_failure_count: int` (default 0) — incremented on FETCH_FAILED, **reset to 0 on any successful fetch**. Drives auto-pause (D-12).
- `last_successful_fetch_at: datetime | None` — set on CHANGED *or* UNCHANGED. Drives staleness (D-14). **Distinct from `last_changed_at`** — this is the D-14 insight: staleness is "no successful *fetch*", not "no *change*".
- A new health status value **`"paused"`** added to `HEALTH_STATUSES` in `lifecycle.py` (D-12 auto-pause). Note: `lifecycle.py`'s `assert_transition` map governs the *Change* lifecycle, not health; `HEALTH_STATUSES` is a plain set — extending it requires the `CheckConstraint` on `Source` to be updated in the migration too (currently `"health_status IN ('unknown','healthy','failed')"`).

**The three states SRC-05 must distinguish (criterion 2):**
| Operator question | How it is answered |
|-------------------|--------------------|
| "checked, no change" | `health_status='healthy'` AND `last_successful_fetch_at` recent AND `last_changed_at` older |
| "checked, error" | `health_status='failed'` (or `'paused'`) AND `consecutive_failure_count > 0` |
| "not checked" | `health_status='unknown'` AND `last_checked_at IS NULL` |

### Pattern 6: Staleness Sweep (D-14)
**What:** A query — not a scheduler (Phase 4) — that finds sources with no successful fetch in N days and fires a Sentry alert. Run manually or via the same CLI that triggers ingest.
```python
# src/brm/health/staleness.py
async def find_stale_sources(session, staleness_days: int) -> list[Source]:
    cutoff = datetime.utcnow() - timedelta(days=staleness_days)
    stmt = select(Source).where(
        Source.health_status != "paused",   # paused sources are already escalated
        or_(Source.last_successful_fetch_at.is_(None),
            Source.last_successful_fetch_at < cutoff),
    )
    return list((await session.scalars(stmt)).all())
# each result → sentry_sdk.capture_message(f"Source {s.id} stale", level="warning")
```
**D-14 trap:** the query keys on `last_successful_fetch_at`, NOT `last_changed_at`. Court rules are quiet for months — keying on `last_changed_at` would alarm constantly on a perfectly healthy source.

### Pattern 7: Cross-Channel Dedup by Change Identity (D-15/D-16, DETECT-03)
**What:** The change-identity key is `SHA-256(normalized substantive rule text)`. The same amendment text seen via the FRBP feed (Phase 1) and the HTML scrape (Phase 2) hashes identically, so dedup is channel-agnostic.
- New column `change_identity: str` on `Change`, with a **partial unique index** (or unique constraint) so the DB enforces one Change per identity.
- New table `change_observation` — `(id, change_id FK, source_id FK, snapshot_id FK, channel, observed_at)` — records each channel that saw the change. The first detection creates the `Change` *and* its first `change_observation`; a later detection with a matching identity creates **only** a second `change_observation` and is attached to the existing `Change` (D-16: "first-detected Change record stands").
- `detect_change` flow: after computing the diff, compute `change_identity`; `SELECT ... WHERE change_identity = ?`; if found → insert `change_observation`, return the existing Change (reviewer sees no duplicate); if not found → insert `Change` + first `change_observation`.

**Identity normalization caveat (`[ASSUMED]` — flag for planner/discuss):** The identity hash must be computed from the *substantive rule text* normalized so that feed-channel and scrape-channel renderings of the same amendment collapse to the same string. The feed entry and the HTML region will have *different surrounding markup and different boilerplate* even after Phase 1 normalization (the feed gives a `<description>`; the page gives a `<div>` region). The planner must define a **channel-independent substantive-text normalization** — most robustly: extract the rule citation tokens + the amendment text, lowercased, whitespace-collapsed, with channel chrome stripped. If the two channels' normalized text does not collapse identically, dedup silently fails (a second Change appears). This is the highest-risk part of Phase 2 and is exactly why D-17 mandates a **feed+scrape fixture pair** to prove it. Recommend the planner make the identity-normalization rule an explicit, tested, pure function with the dedup fixture pair as its acceptance test.

### Anti-Patterns to Avoid
- **Per-source parser code.** D-05/D-06: extraction is config (selector + strip rules), never a Python function per source. A per-source `def parse_sdny(...)` makes onboarding a code change and violates SRC-06.
- **Treating an empty extraction as "rule deleted".** D-07: an empty region is FETCH_FAILED, never a content change. Emitting a "rule deleted" diff on a broken scraper is the exact silent-failure class this phase exists to kill.
- **Keying staleness on `last_changed_at`.** D-14: that alarms on healthy-but-quiet sources. Key on `last_successful_fetch_at`.
- **A production-only / `if fixture:` branch.** D-17/D-04: the six HTML fixtures flow through the *same* `HtmlSourceAdapter` + `run_ingest` code as live fetches (respx replays bytes). Phase 1 already established `test_identical_code_path` as the behavioral proof — extend it, do not grep for `if fixture`.
- **Auto-pausing on a single drift event.** D-10 vs D-12: one drift event keeps the source polling (self-heal); only a *sustained run* of consecutive failures trips the pause. Do not collapse the two rules.
- **Adopting Playwright or a scheduler.** Playwright is a per-source escape hatch (CLAUDE.md) and the pilot page is static; Procrastinate is Phase 4. Both are scope creep here.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTML parsing / CSS selection | Regex over HTML, a custom DOM walker | `selectolax` (`HTMLParser`, `.css()`, `.css_first()`, `.decompose()`) | Regex on HTML is brittle and breaks silently on markup changes (CLAUDE.md "What NOT to Use"). selectolax is C-backed, locked, already a dependency. |
| Async HTTP, conditional requests, timeouts | A `urllib` wrapper, a custom retry-on-socket layer | `httpx.AsyncClient` (timeout, `follow_redirects`, header injection) | Locked; matches the async pipeline; handles HTTP/2, redirects, connection pooling. |
| Textual diff | A custom line-differ | stdlib `difflib` (already wrapped in `src/brm/detect/diff.py`) | Reused from Phase 1; no new code. |
| Content hashing / change identity | A custom checksum | stdlib `hashlib.sha256` (already wrapped as `content_hash`) | The change-identity hash (D-15) is the same primitive. |
| Error monitoring & alert delivery | A custom email/log alert pipeline | `sentry-sdk` (`capture_message`, `capture_exception`) | CLAUDE.md names Sentry as load-bearing — "a scraper that silently breaks is the top operational risk." Drift/staleness/auto-pause alerts all route through it. |
| Schema migration for new columns/tables | Hand-written raw SQL applied ad hoc | Alembic (hand-written migration, per Phase 1's review-finding-#19 discipline) | Versioned, reviewable; Phase 1 established that autogenerate omits CheckConstraints/indexes — write the migration by hand. |
| Robots.txt awareness | A live robots.txt fetch-and-parse on every poll | A documented, human-reviewed `compliance_record` JSONB field per D-03 | D-03 makes compliance an onboarding artifact (reviewed once, recorded), not a runtime dependency. The pilot's robots.txt is already reviewed (see above). |

**Key insight:** Phase 2 adds exactly one genuinely new piece of infrastructure — config-driven extraction. Everything else (fetch, parse, diff, hash, migrate, alert) is a locked library or a Phase 1 seam. The bespoke code is domain logic: the extraction-config schema, the failure-detection heuristics, the structural-fingerprint band, the change-identity normalization.

## Common Pitfalls

### Pitfall 1: Soft-404 read as UNCHANGED
**What goes wrong:** A court CMS serves a "page not found" or maintenance page with HTTP **200** (not 404). A naive fetcher hashes that page, sees a stable hash week after week, and reports UNCHANGED forever — the scraper is broken but green.
**Why it happens:** Many government Drupal/CMS sites return 200 for unknown URLs with a themed error page. Status code alone is not trustworthy.
**How to avoid:** `failure_detect.py` scans the *raw HTML* (before extraction) for soft-404 markers — case-insensitive matches on phrases like "page not found", "404", "the requested page could not be found" combined with the *absence* of the expected `content_selector` resolving. If a soft-404 is detected → FETCH_FAILED (`failure_reason="soft_404"`). Also: D-07's empty-region rule independently catches this — a 404 page will not contain `.field--name-body`.
**Warning signs:** A source with a long UNCHANGED streak and a `content_hash` that has never changed since onboarding — but the live URL 404s in a browser.

### Pitfall 2: Login wall read as content
**What goes wrong:** A page that previously was public becomes auth-gated; the fetcher gets HTTP 200 with a login form, extracts *that* as the rule text, and either reports a bogus CHANGED (the rule "changed" to a login form) or — worse — a stable UNCHANGED on the login page.
**Why it happens:** D-04 scopes auth-gated sources out, but a *previously public* page can become gated mid-life.
**How to avoid:** `failure_detect.py` scans for login-wall markers ("sign in", "log in to continue", `<input type="password">`, "session expired") → FETCH_FAILED (`failure_reason="login_wall"`). The structural fingerprint also helps — a login page is a very different size from the rule region.
**Warning signs:** A sudden CHANGED whose diff replaces all rule text with form-like content.

### Pitfall 3: Layout drift mis-handled — selector silently matches the wrong region
**What goes wrong:** A Drupal theme upgrade renames `.field--name-body`. The selector now matches *nothing* (best case → caught by D-07) — OR a too-loose fallback selector matches the whole `<main>` including nav, producing a giant bogus diff every poll.
**Why it happens:** Onboarding with an over-broad selector, or a selector list with a permissive fallback.
**How to avoid:** Use the *tightest* verified selector (`.field--name-body`, not `.region-content` or `main`). The structural fingerprint size-band catches "selector now matches 10x more content" → FETCH_FAILED (`failure_reason="drift"`) + Sentry alert; the source stays active (D-10) and self-heals if the theme is reverted.
**Warning signs:** A CHANGED diff that is enormous and full of navigation labels.

### Pitfall 4: Cross-channel dedup fails because the two channels normalize differently
**What goes wrong:** The FRBP feed and the HTML page describe the *same* amendment, but their normalized substantive text differs (different boilerplate, different whitespace, the feed truncates the description) → two different `change_identity` hashes → two Change records → the reviewer sees a duplicate. DETECT-03 silently unmet.
**Why it happens:** Phase 1 normalization was designed for *feed* content; the HTML region has different chrome. A hash is unforgiving — one character of difference = a different identity.
**How to avoid:** Define `identity.py` as a pure, *channel-independent* substantive-text normalization (rule-citation tokens + amendment text, lowercased, whitespace-collapsed, all channel chrome stripped) — separate from Phase 1's per-channel `normalize()`. Prove it with the D-17 feed+scrape fixture pair: `change_identity(feed_fixture) == change_identity(scrape_fixture)` is a hard test assertion.
**Warning signs:** The dedup fixture test produces two Change rows instead of one.

### Pitfall 5: A missing Sentry DSN crashes ingest
**What goes wrong:** Sentry is wired in, but in dev/test there is no `SENTRY_DSN`. A naive `sentry_sdk.init()` with no DSN, or an alert call that assumes Sentry is configured, throws — and the *health-monitoring* code becomes the thing that breaks the pipeline.
**Why it happens:** Treating the alert sink as always-present.
**How to avoid:** `health/alerts.py` wraps Sentry: `sentry_sdk.init()` with no DSN is *already a safe no-op* (the SDK degrades gracefully), but make it explicit — read `sentry_dsn` from `config.py` as an *optional* setting (the current `Settings` class has only required fields — add `sentry_dsn: str | None = None`), and if absent, alert calls log locally instead. Tests run with no DSN and must pass. The alert path must never raise into `run_ingest`.
**Warning signs:** Tests fail only when `SENTRY_DSN` is unset; ingest raises from inside an alert call.

### Pitfall 6: Conditional-request 304 handling skips the fingerprint check
**What goes wrong:** A 304 response correctly resolves to UNCHANGED — but if the page later drifts *and* the server still sends a stale ETag, a 304 could mask drift. Lower-probability, but worth noting.
**Why it happens:** 304 short-circuits before the body is even fetched, so the fingerprint never runs.
**How to avoid:** This is acceptable for Phase 2 — a 304 genuinely means "byte-identical to last time", so the region cannot have drifted since the *last 200*. The fingerprint runs on every 200. Document that drift detection is gated on receiving a 200 body; a server that wrongly caches will eventually 200 and be caught. No code needed — just the explicit reasoning in the plan.

## Runtime State Inventory

> Phase 2 is largely greenfield code addition, but it extends existing schema and seed data. Inventory below.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | The `Source` table currently holds (after Phase 1 seed) one FRBP feed row. Phase 2 adds new columns to `Source` (`extraction_config`, `compliance_record`, `structural_fingerprint`, `min_interval_seconds`, `consecutive_failure_count`, `last_successful_fetch_at`) and new columns to `Change` (`change_identity`). Existing rows need backfill defaults. | Alembic migration with sensible server-defaults (`consecutive_failure_count` default 0; nullable JSONB/datetime columns); `change_identity` backfill — compute for any existing Change rows, or allow nullable + populate going forward. |
| Live service config | None — no external service stores Phase 2 state. The pilot source's robots.txt/ETag live on uscourts.gov but are not config the project owns. | None — verified: Phase 2 owns no out-of-git runtime config. |
| OS-registered state | None — no scheduler, no OS task, no cron in Phase 2 (Procrastinate is Phase 4). | None — verified. |
| Secrets/env vars | New optional setting `SENTRY_DSN` (Sentry alert sink). Read via `pydantic-settings` from env/`.env`. No secret rename. | Add `sentry_dsn: str | None = None` to `src/brm/config.py` `Settings`; document in `.env.example` if one exists. |
| Build artifacts / installed packages | New dependency `sentry-sdk` added to `pyproject.toml`. `selectolax` currently unpinned — recommend pinning to `0.4.9`. | `uv add sentry-sdk`; pin `selectolax==0.4.9`; `uv lock` regenerated. |

## Code Examples

### Extract the rule-text region with declarative strip rules (D-05)
```python
# src/brm/ingest/extract.py — pure function; runs identically on fixtures and live (D-17)
# Source: selectolax docs (github.com/rushter/selectolax) + verified against the pilot page
from selectolax.parser import HTMLParser

def extract_region(raw_html: str, content_selector: str,
                   strip_selectors: list[str]) -> str | None:
    """Return the cleaned rule-text region, or None if the selector matched nothing."""
    tree = HTMLParser(raw_html)
    region = tree.css_first(content_selector)
    if region is None:
        return None                       # D-07 — selector miss → caller resolves FETCH_FAILED
    for strip_sel in strip_selectors:      # declarative cleanup vocabulary (D-05)
        for node in region.css(strip_sel):
            node.decompose()
    text = region.text(separator="\n", strip=True)
    return text or None                    # D-07 — empty region → None → FETCH_FAILED
```

### Soft-404 / login-wall detection (D-07, Pitfalls 1 & 2)
```python
# src/brm/ingest/failure_detect.py — pure; small fixed marker vocabulary
SOFT_404_MARKERS = ("page not found", "404", "the requested page could not be found")
LOGIN_MARKERS = ("sign in", "log in to continue", 'type="password"', "session has expired")

def detect_soft_failure(raw_html: str) -> str | None:
    """Return a failure_reason if the page is a soft-404 or login wall, else None."""
    low = raw_html.lower()
    if any(m in low for m in LOGIN_MARKERS):
        return "login_wall"
    if any(m in low for m in SOFT_404_MARKERS):
        return "soft_404"
    return None
```

### Conditional request with descriptive User-Agent (D-08)
```python
# Source: httpx docs (python-httpx.org) + Phase 1 RSS adapter UA string
import httpx

async def fetch_html(source) -> httpx.Response:
    headers = {"User-Agent": "BankruptcyRuleMonitor/1.0 (+internal monitoring)"}
    if source.last_etag:
        headers["If-None-Match"] = source.last_etag
    if source.last_modified_http:
        headers["If-Modified-Since"] = source.last_modified_http
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        return await client.get(source.feed_url, headers=headers)
    # response.status_code == 304 → UNCHANGED; 200 → classify; else → FETCH_FAILED
```

### Bounded retry with exponential backoff for transient failures (D-11)
```python
# Source: stdlib asyncio — no library needed (see Standard Stack rationale)
import asyncio

async def fetch_with_retry(source, max_attempts: int = 3, base_delay: float = 1.0):
    last_err = None
    for attempt in range(max_attempts):
        try:
            return await fetch_html(source)
        except (httpx.TimeoutException, httpx.TransportError) as err:
            last_err = err
            if attempt < max_attempts - 1:
                await asyncio.sleep(base_delay * (2 ** attempt))  # 1s, 2s, 4s
    raise last_err  # caller resolves FETCH_FAILED (failure_reason="transient")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| BeautifulSoup as the default Python HTML parser | C-backed parsers (selectolax / lexbor) for speed | ~2022 onward | CLAUDE.md locks selectolax; far faster, CSS-selector API. |
| Hard-coded per-site scraper functions | Config-driven extraction (selector + declarative cleanup) | Modern scraping practice | D-05/D-06 — onboarding without code change (SRC-06). |
| `requests` + manual retry | `httpx.AsyncClient` with native async, HTTP/2, timeout | ~2021 onward | Matches the project's async pipeline. |

**Deprecated / outdated:**
- Regex-based HTML scraping — brittle, breaks silently (CLAUDE.md "What NOT to Use").
- Trusting HTTP status codes alone — soft-404s (200 + error page) are common on government CMS sites; content-level detection is required.
- `selectolax` is currently **unpinned** in `pyproject.toml` — pin it (`0.4.9`) for reproducibility.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `.field--name-body` remains the correct rule-text selector across uscourts.gov theme changes | Pilot HTML Source | Low at execution time (verified live 2026-05-21); medium long-term — a theme upgrade could rename it. This is precisely the layout-drift D-09/D-10 catches; the structural fingerprint is the safety net. |
| A2 | A stdlib bounded-retry loop (not `tenacity`) is the right choice for D-11 | Standard Stack | Low — the retry policy is trivial (3 attempts, exponential); both options are defensible. Planner confirms. |
| A3 | `FetchResult` should gain an optional `failure_reason` field to route drift alerts | Pattern 2 | Low — additive, does not break the Phase 1 RSS adapter; planner confirms the dataclass extension. |
| A4 | Feed-channel and scrape-channel substantive text *can* be normalized to an identical change-identity hash | Pattern 7, Pitfall 4 | **HIGH** — if the channel-independent normalization is imperfect, cross-channel dedup (DETECT-03) silently fails. This is the riskiest claim in the phase. Mitigation: the D-17 feed+scrape fixture pair is the hard acceptance test; planner must make `identity.py` an explicit, tested pure function. |
| A5 | Adding `"paused"` to `HEALTH_STATUSES` is the right modeling for D-12 auto-pause (vs a separate `is_paused` boolean) | Pattern 5 | Low — a status value keeps health single-valued and consistent with the existing CheckConstraint pattern; planner may prefer a separate boolean. Either satisfies D-12. |
| A6 | Threshold defaults (staleness 7 days, auto-pause 5 failures, retry 3×, fingerprint band ±50%) are sensible for a daily-polled court page | Threshold Defaults | Low — explicitly Claude's-discretion per CONTEXT.md; chosen conservative and per-source-overridable. Planner/user may tune. |

## Threshold Defaults (Claude's Discretion — recommended values)

> All values are recommended defaults; D-08/D-09/D-12/D-14 leave them to discretion. Each should be a per-source-overridable column or JSONB key (cheap insurance), with these as the global defaults.

| Threshold | Recommended default | Rationale |
|-----------|--------------------|-----------|
| Staleness window (D-14) | **7 days** | The pilot page changes a few times a year; a daily-cadence source that has not *successfully fetched* in a week is genuinely broken, not quiet. 7 days is long enough to absorb a multi-day site outage without false alarms, short enough to catch a real break fast. |
| Auto-pause consecutive-failure count (D-12) | **5 consecutive FETCH_FAILED** | At a daily cadence, 5 failures ≈ 5 days of trying — long enough to ride out a transient multi-day outage (D-11's in-poll retry already handles intra-poll blips), short enough to stop burning polls before a week of waste. |
| In-poll retry count (D-11) | **3 attempts** | Covers a brief blip; with exponential backoff the whole poll still finishes in seconds. |
| In-poll backoff schedule (D-11) | **1s, 2s, 4s** (base 1s, factor 2) | Standard exponential backoff; total added latency ≤ 7s — negligible for a daily poll, polite to a government server. |
| Structural fingerprint size-band tolerance (D-09) | **±50%** of baseline (`tolerance_factor: 0.5`) | A real FRBP amendment edit changes the region by a few hundred chars (~10-20% of the verified 1,712-char baseline) — well inside ±50%. A broken selector returns either ~0 chars (empty → caught by D-07) or the whole nav menu (~4,000+ chars → > +50% → caught as drift). ±50% cleanly separates legitimate edits from catastrophic failure. |
| Per-source minimum interval (D-08) | **86,400s (1 day)** for the pilot page | The page changes a few times a year and `Cache-Control` is `max-age=604800`; daily polling is generous coverage and polite. Phase 4 may intensify near effective dates — Phase 2 only sets the ceiling. |
| httpx request timeout | **30.0s** | The exact value Phase 1's RSS adapter uses — keep consistent. |

## Open Questions

1. **Where does the source-health read view live (D-13)?**
   - What we know: it must list every source with last-checked, last-changed, `health_status`, `consecutive_failure_count`; it is internal-only.
   - What's unclear: JSON FastAPI endpoint vs CLI command vs minimal admin page — explicitly planner's discretion.
   - Recommendation: a read-only FastAPI endpoint (`GET /admin/sources/health`) — the FastAPI app already exists from Phase 1, it is the lightest addition, and it is trivially testable. A CLI command is an equally fine fallback. Avoid a new admin UI page (over-build for v1).

2. **Backfill strategy for `change_identity` on existing Change rows.**
   - What we know: Phase 1 may have produced Change rows before `change_identity` existed.
   - What's unclear: whether to backfill (recompute identity for old rows) or leave nullable and populate forward-only.
   - Recommendation: make the column nullable; backfill in the migration if any Change rows exist (recompute from the change's normalized text); the unique constraint applies only to non-null values (partial unique index). At execution time Phase 1 has likely produced zero or few Change rows, so this is low-effort.

3. **Should the structural-fingerprint baseline be seeded at onboarding or learned from the first fetch?**
   - What we know: D-09 needs a baseline size to band around.
   - What's unclear: explicit seeded value vs auto-learned on first successful fetch.
   - Recommendation: auto-learn — on the first successful fetch with no fingerprint set, store `baseline_size = len(extracted)`. Onboarding stays a pure config insert (SRC-06) with no need to hand-measure a size. Allow an explicit override in `extraction_config` for sources where the first fetch might be anomalous.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | All backend code | ✓ | 3.12+ (`requires-python >=3.12`) | — |
| httpx | HTML fetch | ✓ | 0.28.1 (in `pyproject.toml`, installed) | — |
| selectolax | HTML extraction | ✓ | 0.4.9 (installed; pin recommended) | — |
| sentry-sdk | Alert sink | ✗ (not yet a dependency) | 2.60.0 available on PyPI | `uv add sentry-sdk`; with no DSN it is a safe no-op (Pitfall 5) |
| PostgreSQL 16 | Schema (new columns, `change_observation`) | ✓ (Docker Compose, Phase 1) | 16 | — |
| respx | Offline fixture-replay tests | ✓ (dev dependency, Phase 1) | 0.23.1 | — |
| uscourts.gov pilot page | Live verification + fixture capture | ✓ | HTTP 200, verified 2026-05-21 | Fixture replay (D-17) is the primary path; live is parallel verification only |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** `sentry-sdk` is not yet installed — `uv add sentry-sdk` resolves it; absent a DSN it degrades to a no-op so it never blocks execution.

## Validation Architecture

> Nyquist validation is enabled (`workflow.nyquist_validation: true`). Phase 2's validation approach is locked by D-17 (deterministic fixture replay, no production-only branch) and D-18 (the health guarantees are explicitly exercised and asserted).

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio (`asyncio_mode = "auto"`, set in `pyproject.toml`) |
| Config file | `pyproject.toml [tool.pytest.ini_options]` (exists from Phase 1) |
| HTTP mocking | `respx` (dev dependency, Phase 1) — replays the HTML fixtures offline |
| Quick run command | `uv run pytest -x -q` |
| Full suite command | `uv run pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INGEST-02 | A clean HTML fixture flows through `HtmlSourceAdapter` → snapshot → `detected` Change | integration (respx) | `uv run pytest tests/test_html_adapter.py -x -q` | ❌ Wave 0 |
| INGEST-02 / D-05 | `extract_region` applies `content_selector` + `strip_selectors`, returns clean rule text; reorder/strip are deterministic | unit | `uv run pytest tests/test_extract.py -x -q` | ❌ Wave 0 |
| INGEST-04 / D-07 | Empty-region fixture and selector-miss fixture → FETCH_FAILED, never UNCHANGED, never a Change | integration (respx) | `uv run pytest tests/test_html_adapter.py -k "empty or selector" -x -q` | ❌ Wave 0 |
| SRC-05 / D-07 | Soft-404 fixture and login-wall fixture → FETCH_FAILED with the correct `failure_reason` | integration (respx) | `uv run pytest tests/test_failure_detect.py -x -q` | ❌ Wave 0 |
| SRC-05 / D-09 | Drifted-layout fixture (region 10x larger) → fingerprint fails → FETCH_FAILED + Sentry alert; source stays active | integration (respx) | `uv run pytest tests/test_fingerprint.py -x -q` | ❌ Wave 0 |
| SRC-05 / D-12 | N consecutive FETCH_FAILED → `health_status='paused'`; a single failure does NOT pause | integration | `uv run pytest tests/test_health.py -k "pause" -x -q` | ❌ Wave 0 |
| SRC-05 / D-14 | A source with no successful fetch in N days is returned by the staleness sweep + alerts; a quiet-but-fetched source is NOT | unit/integration | `uv run pytest tests/test_health.py -k "stale" -x -q` | ❌ Wave 0 |
| INGEST-07 / D-08 | A poll inside `min_interval_seconds` is skipped; conditional-request headers are sent; 304 → UNCHANGED | integration (respx) | `uv run pytest tests/test_html_adapter.py -k "politeness or conditional" -x -q` | ❌ Wave 0 |
| SRC-06 | A new HTML source inserted as a `Source` row (config only) is ingested by the same adapter with no code change | integration | `uv run pytest tests/test_onboarding.py -x -q` | ❌ Wave 0 |
| DETECT-03 / D-15/D-16 | The feed+scrape fixture pair produces ONE Change with TWO `change_observation` rows — no duplicate Change | integration | `uv run pytest tests/test_dedup.py -x -q` | ❌ Wave 0 |
| D-17 | The fixture-replay path and the live path produce byte-identical detection results (no production-only branch) | integration | `uv run pytest tests/test_fixture_replay.py -k html -x -q` | ❌ Wave 0 (extends Phase 1's `test_identical_code_path`) |

### Sampling Rate
- **Per task commit:** `uv run pytest -x -q`
- **Per wave merge:** `uv run pytest` (full backend suite)
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/fixtures/html/clean.html` — verified pilot page capture (the happy-path fixture; capture live, do not hand-author)
- [ ] `tests/fixtures/html/drifted.html` — same page with the rule region replaced by an order-of-magnitude-larger block (selector matches the nav menu)
- [ ] `tests/fixtures/html/soft_404.html` — an HTTP-200 "page not found" page (capture a real uscourts.gov soft-404, or a realistic synthetic one)
- [ ] `tests/fixtures/html/login_wall.html` — an HTTP-200 page with a login form
- [ ] `tests/fixtures/html/empty_region.html` — the page with `.field--name-body` present but empty
- [ ] `tests/fixtures/html/scrape_dedup.html` + the matching feed fixture — the feed+scrape pair describing the *same* FRBP amendment, to prove `change_identity` collapses them (D-16)
- [ ] `tests/test_extract.py`, `tests/test_failure_detect.py`, `tests/test_fingerprint.py`, `tests/test_html_adapter.py`, `tests/test_health.py`, `tests/test_dedup.py`, `tests/test_onboarding.py` — new test files (TDD — created within their owning tasks)
- [ ] No new framework install — pytest/pytest-asyncio/respx all exist from Phase 1. `sentry-sdk` install is the only new dependency (`uv add sentry-sdk`).

## Project Constraints (from CLAUDE.md)

- **Stack is locked** — Python 3.12, httpx, selectolax, `difflib`, PostgreSQL 16 + JSONB, SQLAlchemy 2.x + Alembic, Sentry. Do not re-litigate or substitute.
- **What NOT to use** — no regex-on-HTML scraping; no Selenium; no Scrapy; no raw `requests`; no NoSQL; no SQLite in production; no LangChain/agent frameworks; no shared database with the other product.
- **Playwright is an escape hatch only** — per-source, when a page needs JS rendering. The pilot page is static; do not adopt Playwright.
- **Procrastinate is Phase 4** — no scheduler/worker in Phase 2.
- **Observability is load-bearing** — "a silently broken scraper is the worst failure mode." Sentry is required, plus a heartbeat / last-successful-poll staleness check that alerts when a source goes stale (this *is* SRC-05 / D-14).
- **Polite scraping** — per-domain rate limiting + a descriptive User-Agent; cache ETags/Last-Modified to avoid refetching unchanged pages. Court sites are government infrastructure.
- **Timezone discipline** — store everything in UTC. The Phase 1 models use naive UTC `datetime.utcnow()` — stay consistent (note: `datetime.utcnow()` is deprecated in 3.12 but is the established Phase 1 convention; do not change it unilaterally in Phase 2 — flag for a future cleanup if desired).
- **Multi-tenancy seam** — new tenant-scoped tables get a nullable `tenant_id` from day one. The new `change_observation` table is *not* tenant-scoped at the row level in v1 (sources and changes are shared per CLAUDE.md "Stack Patterns") — but follow the Phase 1 pattern: add a nullable `tenant_id` if consistency with `Source`/`Change` is wanted.
- **uv** for dependency management; **Ruff** for lint/format; **GSD workflow** for all edits.

## Security Domain

> `security_enforcement` is not set to `false` in config — treated as enabled.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Phase 2 fetches public unauthenticated pages only (D-04); no credentials stored or used. |
| V3 Session Management | no | No sessions in the ingest path. |
| V4 Access Control | partial | The source-health read view (D-13) is internal-only — if exposed as a FastAPI endpoint, reuse Phase 1's `X-API-Key` auth dependency; do not expose source health unauthenticated. |
| V5 Input Validation | **yes** | Untrusted HTML from uscourts.gov crosses a trust boundary into the parser. `extraction_config` JSONB is operator-supplied — validate its shape (Pydantic model: `content_selector: str`, `strip_selectors: list[str]`) before use. |
| V6 Cryptography | partial | SHA-256 for content hash and change identity — stdlib `hashlib`, never hand-rolled. SHA-256 is correct here (identity/integrity, not password storage). |

### Known Threat Patterns for the Phase 2 stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malicious / malformed HTML (entity expansion, oversized payload, deeply nested DOM) | Denial of Service | `selectolax` (lexbor) does not execute scripts and is robust to malformed markup; `httpx` 30s timeout caps slow payloads; oversized/empty bodies resolve to FETCH_FAILED. |
| Silent fetch failure mistaken for "no change" | Spoofing / Tampering | The entire phase — hardened tri-state outcome, soft-404/login-wall detection, structural fingerprint, staleness sweep; D-18 asserts every failure path in tests. |
| SSRF via the source URL | Tampering | Source URLs are a curated, operator-onboarded catalog (SRC-06 is a *registry insert by an operator*, not user-supplied arbitrary-URL monitoring — REQUIREMENTS.md "Out of Scope"). `follow_redirects=True` is needed for uscourts.gov 301s; the redirect target risk is low for curated government sources. Re-examine if onboarding ever accepts untrusted URLs. |
| Operator-supplied `extraction_config` injection | Tampering | Validate the JSONB shape with a Pydantic model; selectors are passed only to `selectolax.css()` (a CSS-selector parser — not code execution). D-05 explicitly forbids arbitrary per-source transform/regex *code*, which closes the code-injection vector by design. |
| Stored XSS — extracted HTML rendered in the review UI | Cross-Site Scripting | Phase 1's review UI renders via React (auto-escaped) and `react-diff-viewer-continued`; Phase 2 stores *extracted text* (selectolax `.text()` strips tags). Do not store raw HTML in a field the UI renders unescaped; never use `dangerouslySetInnerHTML`. |
| Sentry alert path leaking sensitive content | Information Disclosure | Alert messages should carry source IDs / failure reasons / sizes — not full scraped page bodies. Keep `capture_message` payloads metadata-only. |

## Sources

### Primary (HIGH confidence)
- `https://www.uscourts.gov/forms-rules/pending-rules-and-forms-amendments` — fetched 2026-05-21: HTTP 200, ETag + Last-Modified present, static HTML; `.field--name-body` selector verified to isolate the 1,712-char rule-text region.
- `https://www.uscourts.gov/robots.txt` — fetched 2026-05-21: standard Drupal robots.txt, no `Crawl-delay`, `/forms-rules/` not disallowed.
- `src/brm/` — direct inspection of Phase 1 code: `lifecycle.py` (`HEALTH_STATUSES`, `assert_transition`), `models/source.py` `models/snapshot.py` `models/change.py`, `config.py`, `db.py`.
- `.planning/phases/01-end-to-end-feed-slice/01-02-PLAN.md`, `01-03-PLAN.md` — the `SourceAdapter` Protocol, `FetchOutcome`/`FetchResult` contract, `run_ingest` orchestrator, append-only snapshot store, fixture-replay no-branch discipline.
- `.planning/phases/01-end-to-end-feed-slice/01-RESEARCH.md` — established the pending-amendments page has no RSS feed and is the natural Phase 2 HTML twin; FRBP Dec 1 2026/2027 amendment material.
- `CLAUDE.md` — LOCKED technology stack (authoritative).
- PyPI registry — verified 2026-05-21: httpx 0.28.1, selectolax 0.4.9, sentry-sdk 2.60.0, tenacity 9.1.4.
- `slopcheck` 0.6.1 — ran 2026-05-21 against httpx, selectolax, sentry-sdk, tenacity: all `[OK]`.

### Secondary (MEDIUM confidence)
- selectolax usage (`HTMLParser`, `.css`/`.css_first`, `.decompose`, `.text`) — confirmed against the installed package by running extraction on the live pilot page.
- httpx conditional-request / timeout / `follow_redirects` behavior — well-established library behavior; consistent with Phase 1's RSS adapter usage.

### Tertiary (LOW confidence)
- General soft-404 / login-wall marker vocabularies — the exact marker strings in `failure_detect.py` should be refined against the real soft-404/login fixtures captured in Wave 0.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — fully locked in CLAUDE.md, all versions verified on PyPI 2026-05-21, slopcheck clean.
- Pilot source & selectors: HIGH — live-verified 2026-05-21 (HTTP 200, headers, `.field--name-body` extraction confirmed).
- Architecture patterns: HIGH — built on Phase 1 seams inspected directly in `src/brm/` and the Phase 1 PLAN files.
- Cross-channel dedup normalization: MEDIUM — the channel-independent identity normalization (A4) is the riskiest design point; the D-17 feed+scrape fixture pair is the mandated proof.
- Threshold defaults: MEDIUM — explicitly Claude's discretion; chosen conservative, per-source-overridable, but unproven against real long-run polling behavior.
- Pitfalls: HIGH — soft-404/login-wall/drift are well-understood scraping failure modes; CLAUDE.md and Phase 1 already flag the silent-failure class.

**Research date:** 2026-05-21
**Valid until:** 2026-06-20 (30 days — stack is stable; the one volatile item is the pilot page's CSS class, which the structural fingerprint exists to monitor).
