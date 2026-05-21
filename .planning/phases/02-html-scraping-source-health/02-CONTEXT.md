# Phase 2: HTML Scraping & Source Health - Context

**Gathered:** 2026-05-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Widen ingestion from RSS feeds (Phase 1) to **scraped court-website HTML pages**, and make a silently-broken scraper **impossible to mistake for "no change."** This phase adds: an HTML fetcher adapter behind the existing `SourceAdapter` seam; per-source extraction config that isolates the rule-text region from boilerplate/navigation; hardened tri-state fetch outcomes (soft-404 / login wall / empty page → FETCH_FAILED, never UNCHANGED); per-source expected-content fingerprints and layout-drift alerting; source-health monitoring that separates "checked, no change" / "checked, error" / "not checked"; config-only source onboarding with a per-source politeness ceiling; and cross-channel deduplication so the same change seen via feed and scrape becomes one Change record.

This phase does NOT add PDF extraction or district/state coverage (Phase 3), adaptive/cadence-driven polling cadence (Phase 4 — Phase 2 only enforces a *ceiling*, not an adaptive schedule), the full AI taxonomy (Phase 5), or effective-date scheduling (Phase 6).

</domain>

<decisions>
## Implementation Decisions

### Pilot HTML Source
- **D-01:** The Phase 2 HTML source is the **uscourts.gov rulemaking *page*** that Phase 1's FRBP RSS feed already points at — i.e. the same rulemaking content, ingested via a second channel. Rationale: the same change then appears on both the feed (Phase 1) and the scrape (Phase 2), so cross-channel deduplication (criterion 5) is genuinely demonstrable end-to-end without a synthetic pairing. District/state pages are deliberately deferred to Phase 3.
- **D-02:** The *specific* HTML page URL and its CSS structure are a **research task** — researcher should identify the uscourts.gov page that carries the same rulemaking/amendments content as the Phase 1 FRBP feed. The *kind* of source (national rulemaking page overlapping the FRBP feed) is locked; the exact URL/selectors are for research.

### Compliance & Allowed Sources
- **D-03:** Each Source registry row carries a **documented per-source compliance record** — robots.txt reviewed, ToS checked, crawl-delay noted. Source onboarding is not complete until this record is filled. Rationale: auditable, and fits the architect-for-productization constraint.
- **D-04:** **Public, unauthenticated pages only for v1.** PACER and any login/auth-gated source are explicitly **excluded from v1** — this resolves the open STATE.md blocker ("PACER ToS compliance needs a documented decision") by scoping PACER out rather than building credentialed fetching. No stored per-source credentials in this phase.

### Extraction Config
- **D-05:** The per-source extraction config is a **CSS selector to the rule-text region plus a small fixed vocabulary of declarative cleanup rules** (e.g. strip elements by selector, drop nav/header/footer). It must NOT include arbitrary per-source transform/regex code — custom code per source would make onboarding a code change and violate SRC-06.
- **D-06:** Extraction config lives as a **JSONB column on the Source registry row** in Postgres. Onboarding a new HTML source is a DB insert (registry/config operation), no code change and no deploy — this directly satisfies SRC-06.
- **D-07:** When the configured selector matches nothing, or the extracted rule-text region comes back **empty**, the fetch resolves to **FETCH_FAILED — never UNCHANGED and never a content change.** A missing region means the page structure drifted or the scraper broke; it must surface as a health signal, not as silent "no change" or a bogus "rule deleted" diff.

### Politeness Ceiling (Phase 2 scope)
- **D-08:** The Phase 2 politeness ceiling is: a **per-source minimum interval** between fetches that the fetcher enforces, **ETag / If-Modified-Since conditional requests** to skip unchanged pages, and a **descriptive User-Agent** on every request. Adaptive/cadence-driven scheduling is Phase 4 — Phase 2 only guarantees the *ceiling* is respected.

### Drift Detection & Failure Handling
- **D-09:** The per-source expected-content fingerprint is **structural**: the configured selector still resolves AND the extracted region's size sits within an expected band (not suddenly an order of magnitude smaller/larger). This catches layout drift and stripped content. (Content-marker matching was considered and not chosen — too brittle when legitimate content changes.)
- **D-10:** When layout drift is detected (selector breaks / fingerprint fails), the fetch records **FETCH_FAILED and raises an operator alert, but the source stays active and keeps being polled** on schedule — it self-heals if the page recovers. A single drift event does NOT auto-pause the source.
- **D-11:** On a **transient** fetch failure (timeout, 5xx, connection reset), the fetcher does **bounded retries with exponential backoff within the single poll**; if still failing it records FETCH_FAILED and the next scheduled poll tries again.
- **D-12:** When a source fails **repeatedly** — a sustained run of consecutive FETCH_FAILED outcomes — it is **auto-paused after a threshold (N consecutive failures) and escalated**, so it stops burning polls until an operator intervenes. (D-10 vs D-12: one drift event keeps polling; sustained failure trips the auto-pause.)

### Source-Health Monitoring & Staleness
- **D-13:** Operators get a **source-health read view** (endpoint / admin view) listing every source with last-checked, last-changed, `health_status`, and consecutive-failure count — plus **Sentry** for exceptions. This is how "checked, no change" vs "checked, error" vs "not checked" is made visible (criterion 2).
- **D-14:** A source is **stale** when it has had **no *successful* fetch (CHANGED or UNCHANGED) in N days** — this catches a broken scraper. "No *change* in N days" is explicitly NOT staleness: court rules are legitimately quiet for months, so silence is normal and must not trigger false alarms.

### Cross-Channel Deduplication
- **D-15:** The change-identity key for dedup is a **hash of the normalized substantive rule text**. The same text seen via any channel (feed or scrape) collapses to one Change record, robust to source/URL differences between channels.
- **D-16:** On a duplicate detection, the **first-detected Change record stands**; the second channel's observation is **attached to it as an additional observation/snapshot** (evidence both channels saw the change). No second Change record is created and the reviewer is not shown a duplicate.

### Validation Strategy
- **D-17:** Phase 2 is validated via **deterministic fixture replay** (carrying forward Phase 1 D-03/D-04). Saved HTML fixtures cover every path: a clean page, a drifted-layout page, a soft-404, a login wall, an empty-region page, and a feed+scrape pair for the dedup case — all replayed through the same adapter. Offline, deterministic, doubles as the regression suite. Detection/extraction logic must run identically on fixtures and live snapshots — no production-only branch.
- **D-18:** The validation matrix **explicitly exercises and asserts the source-health guarantees**, not just the fetch/extract happy path: staleness alert fires, drift raises FETCH_FAILED, auto-pause triggers after N consecutive failures, and soft-404 / login-wall are classified as FETCH_FAILED. The "silent failure is impossible" promise is tested, not assumed.

### Claude's Discretion
- Exact values for the tunable thresholds — `N` for staleness days, `N` for the auto-pause consecutive-failure count, the retry count / backoff schedule, and the expected-size band tolerance for the structural fingerprint. Planner/researcher should pick sensible defaults (and make them per-source-overridable config where cheap), informed by court-site behavior.
- The exact uscourts.gov HTML page URL and its CSS selectors (per D-02).
- Whether the source-health read view is a JSON API endpoint, a CLI command, or a minimal admin page — planner picks the lightest fit for an internal-only v1 tool; a review-UI banner was considered and not required.
- HTML parsing/fetching library specifics within the locked stack (httpx + selectolax per CLAUDE.md), snapshot retention, and alert-delivery wiring details.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project scope & requirements
- `.planning/PROJECT.md` — project definition, core value, constraints (API-first, no shared DB, architect-for-productization, accuracy/human-review).
- `.planning/REQUIREMENTS.md` — v1 requirements; Phase 2 covers **INGEST-02** (HTML scraping), **INGEST-07** (politeness ceiling), **SRC-05** (source-health monitoring + staleness/drift alerting), **SRC-06** (config-only onboarding), **DETECT-03** (cross-channel dedup).
- `.planning/ROADMAP.md` § "Phase 2: HTML Scraping & Source Health" — goal, the 5 success criteria, and the 5 pre-defined plan slices (02-01 … 02-05).
- `.planning/STATE.md` — Blockers/Concerns note that Phase 2/3 need phase-level research on actual court URLs and feed/page structures; D-04 above resolves the PACER ToS blocker for v1.

### Prior phase context (build directly on these)
- `.planning/phases/01-end-to-end-feed-slice/01-CONTEXT.md` — Phase 1 decisions. Carried forward into Phase 2: the FRBP source family (D-01/D-02 here scrape its HTML twin), the fixture-replay validation strategy with no production-only branch (D-03/D-04 there → D-17 here), the tri-state fetch outcome that Phase 2 hardens.

### Technology stack (locked — do not re-litigate)
- `CLAUDE.md` — full recommended stack. Phase 2 relevant: Python 3.12, **httpx** (async fetch, HTTP/2, ETag/Last-Modified caching), **selectolax** (fast CSS-selector HTML parsing), `difflib` (cheap diff pre-filter), PostgreSQL 16 + JSONB (the extraction-config column), SQLAlchemy 2.x + Alembic (schema migration for new columns/tables), **Sentry** (error monitoring — load-bearing per the "silently broken scraper" pitfall), polite-scraping guidance (per-domain rate limiting, descriptive User-Agent, ETag/Last-Modified caching).

*No external ADRs or design specs exist — requirements and decisions are fully captured in PROJECT.md, REQUIREMENTS.md, ROADMAP.md, CLAUDE.md, 01-CONTEXT.md, and the decisions above.*

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/brm/lifecycle.py` — already defines `HEALTH_STATUSES = {"unknown", "healthy", "failed"}` for `Source.health_status`. Phase 2's health monitoring builds on this enum; if the auto-pause state (D-12) needs a distinct value, this is where it is added.
- `src/brm/models/` — `Source`, `Snapshot`, `Change` domain models (Phase 1 plan 01-01). Phase 2 extends `Source` with the extraction-config JSONB column (D-06), the per-source compliance record (D-03), politeness fields (D-08), and consecutive-failure / last-successful-fetch tracking (D-12/D-14) via an Alembic migration.
- `src/brm/config.py` — `pydantic-settings` config singleton; global tunables and any new Sentry DSN setting go here.
- The `SourceAdapter` seam + append-only snapshot store + tri-state fetcher (Phase 1 plan 01-02) — Phase 2's HTML fetcher is a **new adapter behind this existing seam**, not a new fetch layer.

### Established Patterns
- Tri-state fetch outcome (CHANGED / UNCHANGED / FETCH_FAILED) — established in Phase 1, *hardened* in Phase 2 for HTML (D-07, soft-404/login-wall detection).
- Lifecycle transitions are guarded by `assert_transition` in `lifecycle.py` — any new health/source states follow the same explicit allowed-transition-map pattern.
- Fixture-replay testing against saved source content with no production-only code branch (Phase 1 D-03/D-04) — Phase 2 reuses this exactly (D-17).

### Integration Points
- The HTML adapter plugs into the existing `SourceAdapter` interface; the shared fetch→detect pipeline orchestrator (Phase 1 plan 01-03) routes HTML sources through the same detection/diff path as feed sources — this shared path is what makes cross-channel dedup (D-15/D-16) possible.
- The source-health read view (D-13) is a new read-only surface; whether it sits on the existing FastAPI app or a CLI is planner's discretion.

</code_context>

<specifics>
## Specific Ideas

- The phase's organizing principle, in the user's framing: **a silently-broken scraper must be impossible to mistake for "no change."** Every decision here serves that — D-07 (empty region → FETCH_FAILED), D-09/D-10 (structural drift → FETCH_FAILED + alert), D-14 (staleness = no *successful fetch*, not no change), D-18 (tests assert the failure paths, not just the happy path).
- The pilot source was deliberately chosen to *overlap* Phase 1's feed (D-01) specifically so cross-channel dedup is a real end-to-end demo rather than a contrived test.
- D-10 vs D-12 is an intentional two-tier failure response: a single drift event keeps the source polling (self-heal), but a sustained failure run trips an auto-pause — surfaced explicitly so planner doesn't collapse them into one rule.

</specifics>

<deferred>
## Deferred Ideas

- **District / state HTML pages** — Phase 2's pilot is a national rulemaking page only; district local-rules pages and state exemption pages are Phase 3 (SRC-03/SRC-04). Not scope creep — explicit sequencing.
- **Adaptive polling cadence** — Phase 2 enforces only a per-source politeness *ceiling* (D-08). Cadence-driven scheduling (daily default, sub-daily for feeds, intensification near effective dates) is Phase 4 (INGEST-06).
- **PACER / login-gated sources** — excluded from v1 by D-04. If credentialed court sources are ever needed, that is a future-milestone decision with its own ToS review, not a Phase 2/3 task.

None of the discussion strayed outside the Phase 2 domain — these are sequencing notes, not scope creep.

</deferred>

---

*Phase: 2-HTML Scraping & Source Health*
*Context gathered: 2026-05-21*
