# Phase 2: HTML Scraping & Source Health - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-21
**Phase:** 2-HTML Scraping & Source Health
**Areas discussed:** Pilot HTML source, Compliance, Auth sources, Extraction config, Politeness ceiling, Drift detection, Failure handling (retries/pause), Monitoring, Staleness, Cross-channel dedup, Validation

---

## Pilot HTML Source

| Option | Description | Selected |
|--------|-------------|----------|
| uscourts rulemaking page | Scrape the uscourts.gov rulemaking page behind Phase 1's FRBP feed — same change on both channels, dedup demonstrable end-to-end | ✓ |
| New district local-rules page | Fresh district-court local-rules HTML page — new jurisdiction, but no feed overlap | |
| National HTML-only source | National page with no feed at all — proves HTML-only ingestion, no natural dedup overlap | |

**User's choice:** uscourts rulemaking page
**Notes:** The exact URL/selectors are a research task; the kind of source is locked.

---

## Compliance

| Option | Description | Selected |
|--------|-------------|----------|
| Documented per-source check | Each Source row carries a compliance record (robots.txt, ToS, crawl-delay); onboarding gated until filled | ✓ |
| Programmatic robots.txt only | Fetcher honors robots.txt + crawl-delay at fetch time; no manual ToS sign-off | |
| Polite defaults only | UA + rate limiting only; compliance is operator's informal responsibility | |

**User's choice:** Documented per-source check
**Notes:** Auditable, fits the architect-for-productization constraint.

---

## Auth Sources

| Option | Description | Selected |
|--------|-------------|----------|
| Public pages only | Exclude PACER and any auth-gated source from v1 | ✓ |
| Allow login-gated sources | Support sources behind a login with per-source stored credentials | |
| Defer — researcher documents | Leave open; researcher documents PACER ToS options for a later decision | |

**User's choice:** Public pages only
**Notes:** Resolves the open STATE.md PACER ToS blocker by scoping PACER out of v1.

---

## Extraction Config

| Option | Description | Selected |
|--------|-------------|----------|
| Selector + cleanup rules | CSS selector + a small fixed vocabulary of declarative cleanup rules | ✓ |
| Selector only | One CSS selector defines the region; boilerplate may leak into the diff | |
| Selector + per-source transforms | Selector + arbitrary regex/transform code — violates SRC-06 (code change) | |

**User's choice:** Selector + cleanup rules

---

## Config Home

| Option | Description | Selected |
|--------|-------------|----------|
| JSONB on the Source row | Extraction config as a JSONB column; onboarding = DB insert, no deploy | ✓ |
| Per-source config file | YAML/TOML per source in the repo; adding a source is a commit + deploy | |

**User's choice:** JSONB on the Source row
**Notes:** Directly satisfies SRC-06 (config-only onboarding).

---

## Empty Region

| Option | Description | Selected |
|--------|-------------|----------|
| FETCH_FAILED, never UNCHANGED | Selector matches nothing / empty region → failed fetch + health signal | ✓ |
| Treat as a content change | Empty region routed to review — risks flooding the queue with bogus diffs | |

**User's choice:** FETCH_FAILED, never UNCHANGED

---

## Politeness Ceiling

| Option | Description | Selected |
|--------|-------------|----------|
| Min-interval + conditional reqs | Per-source min interval + ETag/If-Modified-Since + descriptive User-Agent | ✓ |
| Min-interval only | Just the per-source rate limit; skip conditional-request caching | |
| Global default only | One global polite rate; per-source overrides in Phase 4 | |

**User's choice:** Min-interval + conditional requests

---

## Drift Signal

| Option | Description | Selected |
|--------|-------------|----------|
| Structural | Selector still resolves AND region size within an expected band | ✓ |
| Content markers | Specific expected strings/patterns must still appear — brittle | |
| Both structural + markers | Most thorough; more config and more false positives to tune | |

**User's choice:** Structural

---

## On Drift

| Option | Description | Selected |
|--------|-------------|----------|
| Fail + alert, keep polling | Record FETCH_FAILED + alert; source stays active and self-heals | ✓ |
| Auto-pause until fixed | Suspend the source until an operator fixes the config | |
| Alert only | Alert but leave fetch outcome and schedule untouched | |

**User's choice:** Fail + alert, keep polling

---

## Retries

| Option | Description | Selected |
|--------|-------------|----------|
| Bounded retries + backoff | A few retries with exponential backoff inside the poll, then FETCH_FAILED | ✓ |
| Single attempt | One try; FETCH_FAILED immediately, rely on next scheduled poll | |

**User's choice:** Bounded retries + backoff

---

## Auto-pause

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-pause after threshold | After N consecutive failures, auto-pause + escalate | ✓ |
| Keep polling, keep alerting | Never auto-pause; alert keeps firing until fixed | |
| Operator decides each time | First sustained failure escalates with a prompt; human chooses | |

**User's choice:** Auto-pause after threshold

---

## Monitoring

| Option | Description | Selected |
|--------|-------------|----------|
| Health view + Sentry | Read view of per-source last-checked/last-changed/health/failure-count + Sentry | ✓ |
| Sentry + logs only | No dedicated health view; failures surface as errors/logs | |
| Review-UI banner | Unhealthy sources surfaced as a banner in the review SPA | |
| Health view + Sentry + banner | All three | |

**User's choice:** Health view + Sentry

---

## Staleness

| Option | Description | Selected |
|--------|-------------|----------|
| No successful fetch in N days | Staleness = no successful CHANGED/UNCHANGED fetch in N days | ✓ |
| No content change in N days | Alert on no change — risks constant false alarms (rules are quiet for months) | |
| Per-source expected interval | Each source declares an expected interval; stale = overdue | |

**User's choice:** No successful fetch in N days

---

## Change Identity

| Option | Description | Selected |
|--------|-------------|----------|
| Normalized content hash | Hash of normalized substantive rule text — channel-agnostic | ✓ |
| Source-rule + effective date | Identity = rule + effective date — needs both reliably extracted | |
| Canonical URL | Identity = document URL — feed and scrape often differ | |

**User's choice:** Normalized content hash

---

## Dedup Winner

| Option | Description | Selected |
|--------|-------------|----------|
| Keep first, attach observation | First Change stands; second channel attached as an observation/snapshot | ✓ |
| Prefer the richer channel | Upgrade the Change's content with the fuller channel, keep one record | |
| Keep both, link them | Two Change records cross-linked as duplicates | |

**User's choice:** Keep first, attach observation

---

## Validation

| Option | Description | Selected |
|--------|-------------|----------|
| Fixture replay, all cases | Saved HTML fixtures for every path (clean/drift/soft-404/login-wall/empty + feed-scrape pair), replayed through the same adapter | ✓ |
| Live scraping in CI | CI scrapes the real court site — flaky and non-deterministic | |
| Fixtures + live smoke test | Fixture matrix plus one non-blocking live fetch | |

**User's choice:** Fixture replay, all cases
**Notes:** Carries forward Phase 1's deterministic fixture-replay approach.

---

## Health Tests

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — assert health behaviors | Tests explicitly assert staleness alert, drift→FETCH_FAILED, auto-pause, soft-404/login-wall classification | ✓ |
| Fetch/extract paths only | Validate scraping/extraction/dedup; treat health as exercised incidentally | |

**User's choice:** Yes — assert health behaviors

---

## Claude's Discretion

- Tunable threshold values: staleness `N` days, auto-pause `N` consecutive failures, retry count / backoff schedule, structural-fingerprint expected-size band tolerance.
- The exact uscourts.gov HTML page URL and CSS selectors (research task).
- Whether the source-health read view is a JSON API endpoint, a CLI command, or a minimal admin page.
- HTML parsing/fetching library specifics within the locked stack, snapshot retention, alert-delivery wiring.

## Deferred Ideas

- District / state HTML pages — Phase 3 (SRC-03/SRC-04).
- Adaptive polling cadence — Phase 4 (INGEST-06); Phase 2 enforces only the politeness ceiling.
- PACER / login-gated sources — excluded from v1; a future-milestone decision with its own ToS review.
