# Roadmap: Bankruptcy Rule Monitor

## Overview

The Bankruptcy Rule Monitor is a pipeline-of-stages system that ingests U.S. bankruptcy rule changes from ~140+ heterogeneous sources, detects substantive changes, enriches them with AI (diff, classification, summary, extraction), routes them through tiered human review, holds future-dated changes until they take effect, and exposes verified changes to the consuming product via a pull API. This roadmap is built as **vertical MVP slices**: Phase 1 pushes a single feed-backed source all the way through the pipeline (registry → ingest → detect → AI → route → review → activate → pull API) so there is a working, demonstrable feed early. Each subsequent phase widens source coverage (HTML scraping, PDF extraction, more districts/states) and deepens each pipeline stage (adaptive cadence, full taxonomy, effective-date scheduler, temporal API query, forms supersession, audit/provenance). The hard dependency that snapshots precede diffing, and classification precedes routing, is preserved by sequencing the slices so each builds on a working prior slice.

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: End-to-End Feed Slice** - One RSS-backed national source flows from registry through detect, AI, review, and the pull API
- [ ] **Phase 2: HTML Scraping & Source Health** - Add scraped court-website sources with tri-state fetch outcomes and staleness alerting
- [ ] **Phase 3: PDF Ingestion & District Coverage** - Add PDF text extraction and the initial ~3-district local rules/orders tranche
- [ ] **Phase 4: Adaptive Polling & Deduplication** - Cadence-driven unattended polling with politeness ceilings and cross-channel deduplication
- [ ] **Phase 5: Full AI Taxonomy & Confidence-Gated Routing** - Complete 3-axis classification, structured extraction, and confidence-driven tiered routing
- [ ] **Phase 6: Effective-Date Lifecycle & Scheduler** - Full lifecycle state machine, pending-effective handling, activation scheduler, and effective-date calendar
- [ ] **Phase 7: Temporal Delivery API & Forms Supersession** - As-of-date temporal queries, versioned API contract, and Official Forms supersession tracking
- [ ] **Phase 8: Audit, Lineage & Post-Publish Safety** - Immutable audit trail, AI reproducibility records, stable internal IDs, and auto-publish retraction

## Phase Details

### Phase 1: End-to-End Feed Slice

**Goal**: Prove the whole pipeline with one feed-backed national source — a verified rule change can be detected from an RSS source, AI-processed, reviewed by a human, and pulled by the other product through the API.
**Mode:** mvp
**Depends on**: Nothing (first phase)
**Requirements**: SRC-01, SRC-02, INGEST-01, INGEST-04, INGEST-05, DETECT-01, DETECT-02, AI-01, AI-03, AI-06, ROUTE-03, ROUTE-04, EFF-01, EFF-02, API-01, API-07
**Success Criteria** (what must be TRUE):

  1. A source registry holds at least one national RSS source (Title 11 / FRBP / Official Forms feed) with jurisdiction, layer, feed URL, ingestion method, cadence, and last-checked/last-changed state, and a fetch resolves to an explicit CHANGED / UNCHANGED / FETCH_FAILED outcome with a versioned snapshot stored on success
  2. A content-hash gate prevents an unchanged feed poll from triggering downstream work, and a genuine change produces a `detected` Change record with a textual diff
  3. The AI produces a plain-language summary of what substantively changed, labeled "informational / not legal advice", from the verbatim diff
  4. A reviewer can open the web review queue, see the AI summary, diff, source link, and snapshot, and approve or edit a pending change; an approved change records detected date and effective date as separate fields and advances through the lifecycle to verified
  5. The pull API returns the verified change to a caller, with the other product integrating via the API only (no shared database)

**Plans**: 5 plans

Plans:
**Wave 1**

- [x] 01-01-PLAN.md — Backend scaffold (uv/FastAPI), Docker Postgres 16, core domain models (Source, Snapshot, Change with separate date fields), lifecycle guard with `summary_failed` state, hand-written Alembic migration

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 01-02-PLAN.md — Verify the authoritative FRBP rulemaking source (blocking), SourceAdapter seam + tri-state fetcher, append-only snapshot store, FRBP source seed, captured live-snapshot fixtures

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 01-03-PLAN.md — Hash-gate change detection + difflib textual diff producing `detected` Change records; shared fetch→detect pipeline orchestrator; behavioral no-branch proof

**Wave 4** *(blocked on Wave 3 completion)*

- [ ] 01-04-PLAN.md — Verify the anthropic SDK structured-output call (blocking), AI summary advancing Change to `processed` (off-event-loop, with `summary_failed` failure state + retry), admin CLI, live-integration verification

**Wave 5** *(blocked on Wave 4 completion)*

- [ ] 01-05-PLAN.md — API-key-authenticated review-queue API (approve/edit/reject/retry) + read-only pull delivery API with since-cursor + React/Vite review-queue SPA

**UI hint**: yes

### Phase 2: HTML Scraping & Source Health

**Goal**: Widen ingestion to scraped court-website HTML pages and make silent scraper failure impossible to mistake for "no change."
**Mode:** mvp
**Depends on**: Phase 1
**Requirements**: INGEST-02, INGEST-07, SRC-05, SRC-06, DETECT-03
**Success Criteria** (what must be TRUE):

  1. The system ingests a change by scraping a court-website HTML page, with per-source extraction config that isolates the rule-text region from boilerplate and navigation
  2. Source health monitoring distinguishes "checked, no change" from "checked, error" from "not checked", and a soft-404, login wall, or empty page is recorded as FETCH_FAILED — never UNCHANGED
  3. A staleness or layout-drift condition raises an internal alert, and per-source expected-content fingerprints catch a broken scraper
  4. A new HTML source can be onboarded as a registry/config row with no code change, and polling respects a per-source politeness ceiling (rate limit, conditional requests)
  5. The same change seen via both an HTML scrape and a feed is deduplicated into a single Change record

**Plans**: TBD

Plans:

- [ ] 02-01: HTML fetcher adapter with per-source extraction config and boilerplate stripping
- [ ] 02-02: Tri-state fetch hardening — content fingerprints, soft-404/login-wall detection, content-length floors
- [ ] 02-03: Source health model, staleness alarms, and layout-drift alerting
- [ ] 02-04: Config-only source onboarding and per-source politeness ceiling
- [ ] 02-05: Cross-channel change deduplication by change identity

### Phase 3: PDF Ingestion & District Coverage

**Goal**: Add PDF text extraction and onboard the initial ~3 federal bankruptcy court district tranche plus their launch-state exemption sources.
**Mode:** mvp
**Depends on**: Phase 2
**Requirements**: INGEST-03, SRC-03, SRC-04
**Success Criteria** (what must be TRUE):

  1. The system ingests and extracts text from a PDF source document, detecting text-layer vs scanned PDFs and routing image-only PDFs to OCR
  2. A non-trivial PDF that extracts as near-empty is recorded as a FETCH_FAILED-class event rather than "no content", and extracted text is normalized (de-hyphenation, line-number/header stripping) before diffing
  3. The source registry covers an initial tranche of ~3 federal bankruptcy court districts — local rules, standing orders, and general orders — each with every known publication channel documented
  4. The source registry covers state exemption rules for the launch states containing the v1 district tranche
  5. A real PDF-based rule change from a district source flows end-to-end and appears in the review queue

**Plans**: 4 plans

Plans:

**Wave 1**

- [ ] 03-01-PLAN.md — PDF extraction core: install pypdfium2/pdfplumber, 0002 migration (source_pattern + pdf_provenance), FetchResult.reason_code, two-axis scanned-vs-broken classifier, PDF fixtures

**Wave 2** *(blocked on Wave 1)*

- [ ] 03-02-PLAN.md — PDF text normalization (de-hyphenation, line numbers, ligatures) + PdfSourceAdapter document mode flowing end-to-end through run_ingest

**Wave 3** *(blocked on Wave 2)*

- [ ] 03-03-PLAN.md — Index/listing adapter mode + pdf_provenance stamping, ~3-district tranche onboarding, criterion-5 Oregon LBR end-to-end replay

**Wave 4** *(blocked on Wave 3)*

- [ ] 03-04-PLAN.md — Launch-state exemption source onboarding (OR/CA/TX), selective pdfplumber tabular extraction, exemption text-change detection

### Phase 4: Adaptive Polling & Deduplication

**Goal**: Replace manual triggers with cadence-driven unattended polling that is fast where it matters and polite everywhere.
**Mode:** mvp
**Depends on**: Phase 3
**Requirements**: INGEST-06, AI-05
**Success Criteria** (what must be TRUE):

  1. A polling scheduler computes `next_run_at` per source and runs sources unattended at a daily default cadence with durable per-source task locks
  2. Feed-backed sources poll at a sub-daily cadence while static scraped sources poll daily
  3. Polling has a hard per-source politeness ceiling so cadence intensification can never become unbounded
  4. AI output carries a confidence score that is recorded on the Change record, available to drive later routing decisions

**Plans**: TBD

Plans:

- [ ] 04-01: Procrastinate-based polling scheduler with per-source `next_run_at` and durable task locks
- [ ] 04-02: Cadence policy — daily default, sub-daily for feed-backed sources, politeness ceiling
- [ ] 04-03: AI confidence scoring added to the processing pipeline output

### Phase 5: Full AI Taxonomy & Confidence-Gated Routing

**Goal**: Deepen AI processing into the full 3-axis taxonomy with structured extraction, and route changes by tier with confidence gating.
**Mode:** mvp
**Depends on**: Phase 4
**Requirements**: AI-02, AI-04, ROUTE-01, ROUTE-02, ROUTE-05
**Success Criteria** (what must be TRUE):

  1. The AI classifies each change against the full 3-axis taxonomy — layer/jurisdiction, change type, and severity — with stable enum values
  2. The AI extracts structured data — fees, dollar amounts, dates, form numbers — and each extracted value is validated against its expected type (currency parses, dates are plausible)
  3. Fee, form, and exemption-amount changes auto-publish while rule-text and order changes route to human review
  4. A low-confidence change in an otherwise auto-publish type is escalated to human review instead of auto-publishing
  5. An already auto-published change can be corrected or retracted after publication

**Plans**: TBD

Plans:

- [ ] 05-01: 3-axis taxonomy classification prompt and stable enum schema
- [ ] 05-02: Structured extraction with per-type validators (currency, date, form number)
- [ ] 05-03: Tiered router — type-based auto-publish vs review, confidence-gated escalation
- [ ] 05-04: Correction/retraction path for auto-published changes
- [ ] 05-05: Prompt regression test set against real past bankruptcy rule changes

### Phase 6: Effective-Date Lifecycle & Scheduler

**Goal**: Make timing first-class — full lifecycle state machine, future-dated changes held pending, automatic activation on the effective date, and a forward-looking calendar.
**Mode:** mvp
**Depends on**: Phase 5
**Requirements**: EFF-03, EFF-04, EFF-05, EFF-06, API-04
**Success Criteria** (what must be TRUE):

  1. A verified change with a future effective date stays `pending-effective` and is not treated as in force
  2. A monitored scheduler automatically transitions a pending-effective change to `active` on its effective date, and an alert fires if the activation job fails to run
  3. A pending-effective change can be revised or withdrawn before it activates (postponement / withdrawal)
  4. The system exposes an effective-date calendar of changes landing within the next N days, and polling intensifies for sources with an upcoming effective date
  5. The pull API distinguishes `active` changes from verified-but-`pending-effective` changes

**Plans**: TBD

Plans:

- [ ] 06-01: Effective-date scheduler — pending-effective to active activation job with its own monitoring
- [ ] 06-02: Relative-date resolution (e.g. "30 days after entry") with escalation path for unresolvable phrases
- [ ] 06-03: Postponement/withdrawal handling for pending-effective changes
- [ ] 06-04: Effective-date calendar endpoint and polling-cadence intensification feedback loop
- [ ] 06-05: API active vs pending-effective status distinction

### Phase 7: Temporal Delivery API & Forms Supersession

**Goal**: Complete the delivery contract with as-of-date temporal queries, incremental sync, a versioned contract, and Official Forms supersession tracking.
**Mode:** mvp
**Depends on**: Phase 6
**Requirements**: API-02, API-03, API-05, API-06, AUDIT-05
**Success Criteria** (what must be TRUE):

  1. API responses are filterable by jurisdiction, layer, change type, severity, status, and date ranges
  2. The API supports incremental sync via a since-cursor — a caller can retrieve only what changed since timestamp T
  3. The API answers a temporal query — the rule state in force as of a given date — for filing-date reasoning
  4. The API contract is versioned with stable taxonomy enums, so the consuming product integrates against a stable schema
  5. Official Forms track number, version, and supersession, and a superseded form carries a soft-deprecation reference to its replacement

**Plans**: TBD

Plans:

- [ ] 07-01: Published-changes outbox and filterable read API (jurisdiction, layer, type, severity, status, date ranges)
- [ ] 07-02: Since-cursor incremental sync with cursor pagination
- [ ] 07-03: As-of-date temporal query (rule state in force on a given filing date)
- [ ] 07-04: API contract versioning and stable taxonomy enum publication
- [ ] 07-05: Official Forms version/supersession lifecycle with replacement references

### Phase 8: Audit, Lineage & Post-Publish Safety

**Goal**: Make every published change verifiable and defensible — immutable audit trail, reproducible AI output, stable internal identity, and complete provenance lineage.
**Mode:** mvp
**Depends on**: Phase 7
**Requirements**: AUDIT-01, AUDIT-02, AUDIT-03, AUDIT-04
**Success Criteria** (what must be TRUE):

  1. Every change carries canonical source URL, effective date, and ingestion timestamp as first-class lineage fields, retrievable for any published change
  2. An immutable audit trail records each change's lifecycle — detected, classified, reviewed-by, decision, published — with reviewer identity and timestamps, and corrections are new records that supersede rather than edits that erase history
  3. Each AI-processed change records the model, prompt version, inputs, and confidence so the output is reproducible
  4. Rules, forms, and exemption items have stable, immutable internal IDs that persist across changes to official text or numbering

**Plans**: TBD

Plans:

- [ ] 08-01: First-class lineage fields (canonical source URL, effective date, ingestion timestamp) on every change
- [ ] 08-02: Immutable append-only audit trail across the full lifecycle with reviewer attribution
- [ ] 08-03: AI reproducibility records — model ID, prompt version, inputs, confidence per processed change
- [ ] 08-04: Stable immutable internal IDs for rules, forms, and exemption items

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. End-to-End Feed Slice | 5/5 | Complete | 2026-05-22 |
| 2. HTML Scraping & Source Health | 0/5 | Not started | - |
| 3. PDF Ingestion & District Coverage | 0/4 | Not started | - |
| 4. Adaptive Polling & Deduplication | 0/3 | Not started | - |
| 5. Full AI Taxonomy & Confidence-Gated Routing | 0/5 | Not started | - |
| 6. Effective-Date Lifecycle & Scheduler | 0/5 | Not started | - |
| 7. Temporal Delivery API & Forms Supersession | 0/5 | Not started | - |
| 8. Audit, Lineage & Post-Publish Safety | 0/4 | Not started | - |
