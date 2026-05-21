# Project Research Summary

**Project:** Bankruptcy Rule Monitor
**Domain:** Scheduled regulatory-change monitoring service (multi-source ingestion + LLM pipeline + human review + pull API)
**Researched:** 2026-05-20
**Confidence:** HIGH (stack and architecture); MEDIUM-HIGH (features); HIGH (pitfalls)

## Executive Summary

The Bankruptcy Rule Monitor is a pipeline-of-stages system, not a request/response app. Experts build products like this as a sequence of durable-state stages: fetch, normalize, diff, LLM-enrich, route, review, activate, deliver, where each stage advances a record through an explicit lifecycle persisted in the database. The key insight from research is that the three hardest problems are all operational, not algorithmic: (1) reliably detecting when a scraper has silently failed vs. genuinely found no change, (2) keeping the review queue populated with signal rather than noise, and (3) correctly sequencing the detected date / effective date lifecycle so future-dated changes activate at exactly the right moment. None of these are solved by the LLM; they require deliberate data modeling and operational instrumentation from day one.

The recommended approach is Python + FastAPI + PostgreSQL + Procrastinate (Postgres-backed task queue), with the Anthropic SDK used directly for four well-defined single-turn operations: diff analysis, classification, summarization, and structured extraction. The source landscape of ~140+ heterogeneous courts is absorbed by a ~4-adapter ingestion layer (HTML, PDF, RSS, notice-list) where all per-source variation lives in config rows, not code paths. The hash-gate-before-LLM pattern is the central cost lever: the vast majority of polls find no change; only hash mismatches reach the LLM. A React SPA review queue is the right call over HTMX given the productization roadmap.

The dominant risks are operational rather than technical. Silent scraper failure, where a broken fetch is indistinguishable from no change, is the single worst failure mode and must be designed out from the very first ingestion phase, not added later. LLM hallucination and overconfidence on legal text is real and well-documented (legal hallucination rates 58-88% in studies); the mitigation is grounding every LLM claim on the verbatim diff, validating structured extractions against expected types, and keeping the auto-publish tier deliberately narrow. The effective-date model must be three separate fields (detected, published, effective) and a real lifecycle state machine from day one; this is a core data-model requirement, not a scheduler feature.

## Key Findings

### Recommended Stack

The system runs as two process types from one Python codebase: a FastAPI web process (the review UI backend and delivery API) and a Procrastinate worker process (all scrapers, the LLM pipeline, and the effective-date scheduler). PostgreSQL serves as both the primary datastore and the durable job queue, eliminating the need for Redis or RabbitMQ at this workload scale (~140 sources, thousands of jobs per day). The critical licensing decision is to use pypdfium2 (Apache-2.0/BSD-3-Clause) rather than PyMuPDF (AGPL), which is non-negotiable given the productization path. Use the Anthropic SDK directly; never an agent framework for this fixed-operation LLM workload.

**Core technologies:**
- Python 3.12 + FastAPI 0.136.x + Uvicorn: async-native API, automatic OpenAPI schema, Pydantic v2 validation
- PostgreSQL 16 + SQLAlchemy 2.0 + Alembic: single datastore for relational data, JSONB for LLM output, job queue
- Procrastinate 3.x: Postgres-backed task queue with deferred/scheduled tasks, retries, per-source task locks
- Anthropic SDK 0.103.x: direct SDK use for diff-classify-summarize-extract; Message Batches API for bulk non-urgent diffs
- httpx 0.28.x + selectolax + feedparser + pypdfium2 (+ pdfplumber for tabular sources): per-kind fetcher adapters
- React 19 + Vite 6 + shadcn/ui + TanStack Query + react-diff-viewer-continued: review-queue SPA
- Sentry: error monitoring; a silently broken scraper is the top operational risk

**What NOT to use:** PyMuPDF (AGPL license risk), LangChain/LlamaIndex (no benefit for fixed-operation LLM work), Redis/RabbitMQ (Postgres handles the workload trivially), shared DB with the other product (explicitly out of scope).

### Expected Features

**Must have (table stakes) -- all in v1:**
- Source registry: one config+state row per source; operational backbone; everything keys off it
- Multi-source ingestion (RSS/feed + HTML scraping + PDF extraction): coverage requires both paths
- Content snapshot/archive (versioned, append-only): prerequisite for diffing; cannot diff without a stored before
- Substantive change detection with normalization: diff must filter out nav/timestamp/boilerplate noise before the LLM sees it
- AI classification into the 3-axis taxonomy (layer/jurisdiction, change type, severity): drives routing and API filtering
- AI plain-language summary: machine and human consumers both require it
- AI structured extraction (fees, dates, form numbers) with type validation
- Effective-date model: detected vs. effective as separate fields + lifecycle state machine
- Pending-to-active scheduler: changes must activate on the right calendar date, not at detection
- Tiered routing: auto-publish fees/forms/exemption amounts; human review for rule/order text
- Web review queue with approve/reject/edit, showing verbatim diff + AI summary + source link
- Audit trail (immutable: source URL, raw fetch bytes, diff, LLM output + model/prompt version, reviewer + decision + timestamps)
- Pull read API filterable by jurisdiction/layer/type/severity/status with since-cursor incremental sync
- Source health/staleness monitoring with alerting: FETCH_FAILED must never be recorded as UNCHANGED
- Adaptive polling cadence (daily default, sub-daily for feeds, intensified near upcoming effective dates)

**Should have (competitive differentiators) -- v1.x after initial validation:**
- Full ~90-district coverage (start with a tranche, roll out incrementally)
- Upcoming-effective-date calendar/forecast endpoint
- Effective-date-aware rule-state-as-of-date-X temporal query
- Official Forms version/supersession lifecycle tracking
- Confidence calibration from reviewer correction history

**Defer (v2+):**
- Webhook / push notifications (deliberately deferred per PROJECT.md)
- Multi-tenant customer-facing product layer and dashboards
- Case-law / opinion monitoring adjacency

**Anti-features to explicitly avoid:** shared database with the other product, auto-publishing rule/order text changes without review, real-time minute-level polling, legal interpretation/advice, board dashboards at v1.

### Architecture Approach

The system is a pipeline-of-stages over durable state: each stage picks up records in the prior status, advances them, and persists the result before handing off. No in-memory orchestration; every stage is independently retryable. Four key patterns: (1) hash-gate before expensive work (normalize, hash, compare; only diff and call LLM on mismatches), (2) confidence-based tiered routing (auto-publish only low-stakes + high-confidence; everything else escalates to humans), (3) transactional outbox for downstream decoupling (delivery API serves from published_changes only; internal tables never exposed), (4) adaptive cadence as computed state (effective-date scheduler feeds upcoming dates to the polling scheduler; one-directional).

**Major components:**
1. Source Registry: one config+state row per monitored source; ~4 fetcher adapters absorb all heterogeneity via fetchConfig
2. Adaptive Polling Scheduler + Fetcher Adapters (HTML, PDF, RSS, notice-list) + Normalizer + Snapshot Store: ingestion plane
3. Diff / Change Detection: cheap hash gate then textual diff; only candidates proceed to the LLM
4. LLM Processing Pipeline (classify, summarize, extract, confidence) + Tiered Router
5. Review Queue + Web UI: exception queue for rule/order text; verbatim diff prominent; AI summary secondary
6. Effective-Date Scheduler: PENDING-to-ACTIVE activation job (monitored); feeds upcoming dates back to polling scheduler
7. Published Changes Outbox + Delivery API: the external contract; independent of the internal model; cursor-paginated pull

### Critical Pitfalls

1. **Silent scraper failure mistaken for no change** -- Implement a tri-state fetch result (CHANGED / UNCHANGED / FETCH_FAILED) from day one. Per-source expected-content fingerprints, staleness alarms, and raw byte snapshots are core architecture, not polish. A source that never changes for months is suspicious.

2. **Diff noise flooding the review queue** -- Normalize aggressively before diffing: strip boilerplate, timestamps, nav, PDF headers/footers. Use the LLM as a second gate to confirm substance before routing to a human. Track the reviewer rejection rate; treat >10% as a defect.

3. **LLM hallucination and overconfidence on legal text** -- Ground every LLM claim on the verbatim diff text. Validate all extracted values against expected types. Show verbatim old/new text prominently in the review UI; the AI summary is secondary context. Pin model + prompt version and record them with every LLM output. Legal hallucination rates are 58-88% in studies; the safeguards are non-optional.

4. **Effective-date errors (wrong activation timing)** -- Three separate date fields from the start: detected, published, effective. PENDING is a real lifecycle state with a monitored activation job. Relative date phrases must be resolved to concrete dates or escalated; never silently dropped.

5. **Auto-publish tier publishing a wrong change downstream** -- The routing decision itself is a fallible LLM classification. Gate auto-publish on confidence floor + extraction validation. Keep an audit trail and a rollback path for every auto-published change. Post-publish sampling is a required operational process.

6. **Coverage gaps (a source exists but is not monitored)** -- Each district publishes local rules, general orders, and standing orders on separate channels. The source registry must document every known channel per district, including confirmed absences. The registry is a living, versioned artifact with a re-audit cadence, not a one-time setup.

## Implications for Roadmap

The architecture research provides an explicit, dependency-driven build order. Feature dependencies in FEATURES.md confirm the same sequencing. Phases map directly to the pipeline planes.

### Phase 1: Data Model and Source Registry Foundation

**Rationale:** Nothing can be fetched, scheduled, processed, or delivered without the core domain models. The Source entity (with kind + fetchConfig), the Change entity (with three separate date fields and an explicit status enum), and the published_changes outbox schema must be established first. Seeding sources across all three layers early forces the adapter interface to be general and exercises heterogeneity before it becomes a surprise.

**Delivers:** Core domain models, database schema with Alembic migrations, source registry seeded with national/district/state examples, tenant_id column present but null on all tenant-scoped tables.

**Addresses:** Source registry (P1), audit trail schema, multi-tenancy readiness.

**Avoids:** Single-date-field anti-pattern (Pitfall 5), single-tenant schema baked in.

**Research flag:** Standard patterns; no additional research needed. Schema design follows directly from ARCHITECTURE.md entity definitions.

### Phase 2: Ingestion Pipeline (Fetchers, Normalizer, Snapshot Store)

**Rationale:** Ingestion is the prerequisite for everything downstream. Normalization quality is the highest-leverage engineering decision in the product; poor normalization produces both silent failures and diff noise simultaneously. The FETCH_FAILED tri-state and per-source fingerprints must be built in here; retrofitting them later risks data integrity.

**Delivers:** ~4 fetcher adapters (HTML, PDF, RSS, notice-list) behind a common interface; Normalizer with boilerplate stripping and content hashing; Snapshot Store (append-only); FETCH_FAILED tri-state; per-source expected-content fingerprints; staleness alarm logic; PDF type detection (text-layer vs. scanned) with OCR routing.

**Uses:** httpx, selectolax, feedparser, pypdfium2, pdfplumber (tabular sources only).

**Addresses:** Multi-source ingestion, content snapshot/archive, source health monitoring (all P1).

**Avoids:** Silent scraper failure (Pitfall 1), PDF extraction failures (Pitfall 7), rate limiting and ToS violations (Pitfall 8).

**Research flag:** Needs phase-level research. Specific court URLs and feed structures for the initial tranche need live validation. PDF extraction quality on district court PDFs requires hands-on testing. PACER ToS compliance strategy needs a documented decision before any PACER sources are onboarded.

### Phase 3: Adaptive Polling Scheduler

**Rationale:** Replace manual triggers with cadence-driven polling. The scheduler is the operational heartbeat. Daily-default cadence ships without the effective-date feedback loop (which comes in Phase 6); intensification is wired in later.

**Delivers:** Procrastinate-based scheduler computing next_run_at per source; daily default and sub-daily cadence; durable task locks (one poll per source at a time); worker process separate from the API process.

**Uses:** Procrastinate 3.x on the shared Postgres instance.

**Addresses:** Adaptive polling cadence (P1; baseline; intensification in Phase 6).

**Avoids:** Unbounded polling (Pitfall 8), in-memory schedule loss.

**Research flag:** Standard patterns; Procrastinate is well-documented. No additional research needed.

### Phase 4: Change Detection

**Rationale:** Hash gate + textual diff. Normalization quality from Phase 2 determines whether this phase produces useful signal or queue-flooding noise. Must come before the LLM pipeline because the diff output is the primary LLM input.

**Delivers:** Hash comparison against last snapshot (cheap exit on no change); textual diff on mismatches; Change records created with status=detected; noise metric tracked (% of detected changes ultimately rejected as non-substantive).

**Addresses:** Substantive change detection (P1).

**Avoids:** Diff noise flooding the review queue (Pitfall 2), byte/DOM diff without normalization.

**Research flag:** Standard patterns; hash-gate-then-diff is well-documented with reference implementations. No additional research needed.

### Phase 5: LLM Processing Pipeline and Tiered Router

**Rationale:** The first phase that produces human-readable value. LLM classification, summarization, extraction, and the tiered router ship together because the router logic depends entirely on the classifier output schema. These are inseparable.

**Delivers:** LLM pipeline (classify into 3-axis taxonomy, plain-language summary, structured extraction with type validation, confidence score); tiered router (fees/forms/exemption amounts + high confidence: auto-publish; all rule/order text and low confidence: review queue); LLM output versioned with model ID and prompt version; extraction validators; prompt regression test set against real past bankruptcy rule changes.

**Uses:** Anthropic SDK 0.103.x direct; Message Batches API for bulk diffs.

**Addresses:** AI classification, AI plain-language summary, AI structured extraction, tiered routing (all P1).

**Avoids:** LLM hallucination on legal text (Pitfall 3), auto-publish tier publishing wrong changes (Pitfall 4), agent framework overhead.

**Research flag:** Needs phase-level research. Prompt design for bankruptcy-specific taxonomy classification, grounding strategies for legal text, and the extraction schema for fees/exemption amounts/form numbers should be researched during planning. Plan for taxonomy iteration through the Phase 6 review queue.

### Phase 6: Review Queue and Effective-Date Activation

**Rationale:** The human accuracy safeguard and the effective-date scheduler are grouped because both deal with post-verification change handling. The review queue determines whether a change is approved; the effective-date scheduler determines when an approved change becomes active. Polling intensification is also wired here (depends on effective-date model existing).

**Delivers:** Web review queue UI (React SPA) with verbatim diff prominent, AI summary secondary, field-level confirmation for fees/dates/form numbers, severity-prioritized ordering, approve/reject/edit with immutable audit capture, review quality metrics; effective-date scheduler (PENDING-to-ACTIVE with its own monitoring/alerting); polling scheduler intensification wired to upcoming effective dates; rollback capability for auto-published changes.

**Uses:** React 19 + Vite 6 + shadcn/ui + TanStack Query + react-diff-viewer-continued.

**Addresses:** Review queue, effective-date model, pending-to-active scheduler, audit trail (all P1); reviewer fatigue (Pitfall 10), effective-date errors (Pitfall 5), no provenance (Pitfall 9).

**Avoids:** Reviewer rubber-stamping (Pitfall 10; verbatim diff prominent, field-level confirmation, review quality metrics tracked).

**Research flag:** Standard patterns for the queue UI. The effective-date scheduler handling of relative date phrases needs a design decision: resolver or escalation path.

### Phase 7: Delivery API and Integration Handoff

**Rationale:** The delivery API comes last because it consumes the verified output of everything upstream. The outbox pattern ensures internal schema can evolve freely while the API contract stays stable. This is the integration contract with the other product.

**Delivers:** published_changes outbox table (written transactionally when a change becomes active); read-only FastAPI delivery endpoints (filterable by jurisdiction/layer/type/severity/status, since-cursor pagination, explicit pending-effective vs. active status); API versioning; retraction/correction signal (new versioned record supersedes; never silent overwrite); OpenAPI schema for the consuming product; integration test suite for the full pipeline.

**Addresses:** Pull read API (P1); downstream integration contract.

**Avoids:** Shared database with the other product, downstream consumer silently receiving a corrected change.

**Research flag:** Standard patterns; transactional outbox and cursor pagination are well-documented. The API schema for the 3-axis taxonomy and pending/active status should be reviewed with the consuming product team before finalizing.

### Phase Ordering Rationale

- The dependency graph from FEATURES.md drives the sequencing: snapshot store before diff before LLM before routing before review before delivery. Every phase unblocks the next.
- Data model first is non-negotiable: the three-date schema and FETCH_FAILED tri-state must be in place before any real data is collected; retrofitting them creates data integrity risk.
- Ingestion (Phase 2) and scheduler (Phase 3) are separated so fetcher adapter quality can be validated against live sources before automation.
- LLM pipeline and tiered router ship together (Phase 5) because the router logic is a direct function of the classifier output schema.
- Review queue and effective-date scheduler are grouped (Phase 6) because both deal with post-verification change handling; shipping the queue without the activation scheduler leaves the system incomplete for any future-dated change.
- Delivery API last (Phase 7) ensures the other product integrates against a stable, complete pipeline.

### Research Flags

**Phases needing deeper research during planning:**
- **Phase 2 (Ingestion):** Source-specific; actual URLs, feed structures, and PDF layouts of the initial court tranche need live validation. PACER ToS compliance needs a documented strategy. PDF extraction quality on district court PDFs needs hands-on testing.
- **Phase 5 (LLM Pipeline):** Prompt design for legal text and the bankruptcy-specific taxonomy. Grounding strategies, the extraction schema for fees/exemption amounts/form numbers, and classification prompt design all benefit from dedicated research.
- **Phase 6 (Effective-Date Scheduler):** Relative date resolution for bankruptcy-specific date expressions needs a design decision: resolver logic or escalation path.

**Phases with standard patterns (skip research-phase):**
- **Phase 1 (Data Model):** Follows directly from ARCHITECTURE.md entity definitions.
- **Phase 3 (Scheduler):** Procrastinate is well-documented; daily/sub-daily cadence is straightforward.
- **Phase 4 (Change Detection):** Hash-gate-then-diff is a well-established pattern with reference implementations.
- **Phase 7 (Delivery API):** Transactional outbox and cursor pagination are well-documented patterns.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Core stack verified via official PyPI and GitHub sources; version compatibility confirmed; PyMuPDF AGPL license risk verified from primary source |
| Features | MEDIUM-HIGH | Commercial RCM feature patterns well-documented and consistent across vendors; bankruptcy-domain specifics (NCLC, court sources) HIGH; some workflow internals inferred from vendor marketing |
| Architecture | HIGH | Pipeline-of-stages, hash-gate, outbox, confidence-based HITL routing are well-established patterns with reference implementations; bankruptcy-source specifics MEDIUM (verified conceptually, not source-by-source) |
| Pitfalls | HIGH | Scraping and LLM pitfalls corroborated by Free Law Project experience, academic legal-hallucination studies, PACER policy, and web-scraping post-mortems; bankruptcy procedural details MEDIUM |

**Overall confidence:** HIGH for the build approach; MEDIUM for source-specific details that need live validation.

### Gaps to Address

- **Court source topology per district:** The specific pages, feeds, and document types each of the ~90 districts publishes are not yet mapped. Resolves during Phase 2 source onboarding, but the initial tranche needs hands-on audit before Phase 2 planning.
- **PACER access strategy:** Whether and how to use PACER (billing model, ToS constraints, off-peak requirements) needs a documented decision before any PACER sources are registered.
- **Effective-date relative phrase resolution:** Phrases like "30 days after entry" and "upon approval by the Judicial Conference" are common in bankruptcy orders. The resolver or escalation strategy needs design in Phase 6.
- **Prompt calibration and taxonomy iteration:** The 3-axis taxonomy is designed but unvalidated against real court documents. Expect iteration through Phase 5 and Phase 6; keep taxonomy in LLM prompt + enum (not a trained model) for cheap iteration.
- **Initial district source tranche selection:** Which districts to start with (high-volume courts vs. geographically representative) is an open decision to be made before Phase 2.

## Sources

### Primary (HIGH confidence)

- /anthropics/anthropic-sdk-python (Context7) -- Anthropic Python SDK official reference
- https://pypi.org/project/fastapi/ -- FastAPI 0.136.x version and API
- https://pypi.org/project/anthropic/ -- anthropic 0.103.x version
- https://github.com/procrastinate-org/procrastinate -- Procrastinate task queue
- https://pypi.org/project/pypdfium2/ -- Apache-2.0 / BSD-3-Clause licensing confirmed
- https://pymupdf.readthedocs.io/en/latest/about.html -- PyMuPDF AGPL licensing confirmed
- https://academic.oup.com/jla/article/16/1/64/7699227 -- LLM legal hallucination rates (58-88%)
- https://arxiv.org/pdf/2509.25498 -- LLM interpretive overconfidence as dominant failure mode
- https://pacer.uscourts.gov/help/faqs/are-there-any-limits-pacer-usage -- PACER usage limits and off-peak policy
- https://free.law/projects/juriscraper -- Free Law Project Juriscraper (court-scraping maintenance reality)
- https://dev.to/apify_forge/how-website-change-detection-actually-works-hashes-diffs-and-snapshots-1aeb -- hash-gate-then-diff pattern
- https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html -- transactional outbox pattern
- https://github.com/dgtlmoon/changedetection.io -- reference implementation of fetch/snapshot/diff
- https://library.nclc.org/article/april-1-increase-federal-bankruptcy-exemptions-other-dollar-amounts-0 -- federal bankruptcy dollar amount adjustment cadence (3-year cycle, April 1)

### Secondary (MEDIUM confidence)

- https://www.centraleyes.com/best-regulatory-change-management-software/ -- commercial RCM feature landscape
- https://www.metricstream.com/products/regulatory-change-management.htm -- MetricStream RCM feature set
- https://www.diligent.com/resources/blog/regulatory-change-management-software -- Diligent RCM feature set
- https://visualping.io/blog/regulatory-compliance-monitoring -- web change-detection feature patterns
- https://use-apify.com/blog/web-scraping-architecture-patterns -- scraping architecture patterns
- https://medium.com/alan/lessons-from-running-an-llm-document-processing-pipeline-in-production-33d87f99cdb1 -- LLM pipeline production lessons
- https://www.zenml.io/llmops-database/multilingual-document-processing-pipeline-with-human-in-the-loop-validation -- confidence-threshold HITL routing
- https://www.milanjovanovic.tech/blog/implementing-the-outbox-pattern -- outbox implementation
- https://judoscale.com/blog/choose-python-task-queue -- Python task queue comparison
- https://www.nutrient.io/blog/best-python-pdf-libraries/ -- 2026 Python PDF library comparison
- https://groupbwt.com/blog/is-web-scraping-legal/ -- web scraping ToS/legal compliance

### Tertiary (LOW confidence)

- https://dev.to/syedahmershah/react-is-overkill-why-python-htmx-is-dominating-in-2026-17ib -- internal-tool UI tradeoffs (used to validate React SPA decision)

---
*Research completed: 2026-05-20*
*Ready for roadmap: yes*
