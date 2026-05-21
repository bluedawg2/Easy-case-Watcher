# Architecture Research

**Domain:** Scheduled regulatory-change monitoring service (ingest → LLM-process → human-review → API-deliver)
**Researched:** 2026-05-20
**Confidence:** HIGH on overall structure and patterns (well-established in monitoring/CDC/HITL literature); MEDIUM on bankruptcy-source specifics (source landscape verified conceptually, not source-by-source).

## Standard Architecture

This system is a **pipeline of independent stages connected by durable state**, not a request/response app. Each stage advances a record through a lifecycle and is independently retryable. The dominant industry patterns it combines: website change-detection (hash → snapshot → diff), confidence-based human-in-the-loop routing, a job scheduler with adaptive cadence, and the transactional-outbox pattern for decoupled downstream delivery.

### System Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                        CONTROL PLANE                                  │
│  ┌──────────────────┐         ┌────────────────────────────────────┐  │
│  │  Source Registry │         │   Adaptive Polling Scheduler       │  │
│  │  (~140+ sources, │◄────────┤  daily / sub-daily / intensified   │  │
│  │   config + state)│         │  (cadence driven by feed + dates)  │  │
│  └──────────────────┘         └─────────────────┬──────────────────┘  │
└────────────────────────────────────────────────┼─────────────────────┘
                                                  │ enqueues fetch jobs
┌─────────────────────────────────────────────────▼─────────────────────┐
│                        INGESTION PLANE                                │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐               │
│  │ Fetcher: │  │ Fetcher: │  │ Fetcher: │  │ Fetcher: │   per-source  │
│  │ HTML     │  │ PDF      │  │ RSS/feed │  │ notice   │   ADAPTERS    │
│  │ scraper  │  │ scraper  │  │          │  │ list     │               │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘               │
│       └─────────────┴─────┬───────┴─────────────┘                     │
│                  ┌────────▼─────────┐                                 │
│                  │  Normalizer      │ raw bytes → clean canonical text │
│                  │  + content hash  │                                 │
│                  └────────┬─────────┘                                 │
└───────────────────────────┼───────────────────────────────────────────┘
                            │ hash differs from last snapshot?
┌───────────────────────────▼───────────────────────────────────────────┐
│                        PROCESSING PLANE                               │
│  ┌──────────────┐   ┌──────────────┐   ┌───────────────────────────┐  │
│  │ Snapshot     │──►│ Diff /       │──►│  LLM Processing Pipeline  │  │
│  │ Store        │   │ Change       │   │  diff-classify-summarize- │  │
│  │ (versioned)  │   │ Detection    │   │  extract                  │  │
│  └──────────────┘   └──────────────┘   └────────────┬──────────────┘  │
│                                                     │ creates Change  │
│                            ┌────────────────────────▼──────────────┐  │
│                            │   Tiered Router                       │  │
│                            │   fees/forms ──► auto-publish path     │  │
│                            │   rule/order text ──► review queue     │  │
│                            └───────┬───────────────────┬───────────┘  │
└────────────────────────────────────┼───────────────────┼──────────────┘
                                     │                   │
              ┌──────────────────────▼──────┐   ┌─────────▼────────────┐
              │  Review Queue + Web UI      │   │  Effective-Date      │
              │  (approve / reject /        │   │  Scheduler           │
              │   edit AI summary)          │   │  pending → active on │
              │                             │   │  effective date      │
              └──────────────┬──────────────┘   └─────────┬────────────┘
                             │ approved                   │ activated
┌────────────────────────────▼────────────────────────────▼─────────────┐
│                        DELIVERY PLANE                                 │
│  ┌─────────────────────┐      ┌────────────────────────────────────┐  │
│  │  Published Changes  │─────►│  Delivery API (read-only, pull)     │  │
│  │  Store (outbox /    │      │  GET /changes?since=...&status=...  │  │
│  │  change feed)       │      │  (webhook fan-out: later)           │  │
│  └─────────────────────┘      └────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
                                            │
                                            ▼
                                  "The other product" (no shared DB)
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| **Source Registry** | Single source of truth for the ~140+ monitored sources: identity, jurisdiction layer, fetch config, cadence policy, last-checked / last-changed state, health | Database table(s) + typed config; one row per source. Config-as-data, never code branches |
| **Adaptive Polling Scheduler** | Decides *when* each source is fetched next; enqueues fetch jobs. Daily default, sub-daily for feed-backed sources, intensified near known effective dates | Cron/interval worker computing `next_run_at` per source; durable job queue |
| **Fetchers (per-source adapters)** | Retrieve raw content for one source *kind* (HTML page, PDF, RSS, notice list). Handle auth, retries, rate limits, polite crawling | Adapter pattern: a common `Fetcher` interface; concrete adapters per content kind, parameterized per source |
| **Normalizer** | Convert raw bytes (HTML/PDF) into clean canonical text; strip volatile noise (timestamps, nav, ads); compute a stable content hash | HTML→text extraction, PDF text extraction, boilerplate removal, SHA-256 over normalized text |
| **Snapshot Store** | Immutable, versioned history of every distinct content version per source | Append-only table keyed by `(source_id, captured_at)`; blob storage for raw + normalized text |
| **Diff / Change Detection** | Compare new snapshot vs last snapshot; only runs when hash differs; produce a structured textual diff | Text diff (token/section level); cheap hash gate first, expensive diff second |
| **LLM Processing Pipeline** | Per detected diff: identify what substantively changed, classify into taxonomy, write plain-language summary, extract structured fields (fees/dates/form numbers), assign confidence | Sequenced Claude calls (or one structured call) producing a `Change` record; structured/JSON output |
| **Tiered Router** | Route each `Change` by type: fees/forms → auto-publish; rule/order text → human review | Pure decision function on `Change.type` + confidence threshold |
| **Review Queue + Web UI** | Human reviewers approve / reject / edit pending rule-text changes with the AI summary and diff visible | Web app over a `review_items` queue; status transitions, reviewer assignment, audit trail |
| **Effective-Date Scheduler** | Hold future-dated changes as `pending`; activate them exactly on the effective date; feed upcoming effective dates back to the polling scheduler | Time-driven worker scanning `Change` rows where `effective_date <= now AND status = pending` |
| **Published Changes Store** | Canonical, decoupled record of verified+active changes ready for downstream consumption — the delivery contract, not the internal model | Outbox-style table with a monotonic cursor (`sequence`/`updated_at`) |
| **Delivery API** | Read-only pull API the other product calls to retrieve verified changes; webhook fan-out deferred | Stateless HTTP service over Published Changes Store; cursor pagination |

## Recommended Project Structure

```
src/
├── registry/              # Source Registry
│   ├── source.model.ts    # Source entity + lifecycle state
│   ├── source.repo.ts     # CRUD + state queries
│   └── seeds/             # ~140+ source definitions as data (national/district/state)
├── scheduler/             # Adaptive Polling Scheduler
│   ├── cadence.ts         # next_run_at calculation (daily/sub-daily/intensified)
│   └── poller.ts          # enqueues fetch jobs
├── ingestion/
│   ├── fetchers/          # Per-kind adapters behind a common interface
│   │   ├── fetcher.ts     # Fetcher interface
│   │   ├── html.ts
│   │   ├── pdf.ts
│   │   ├── rss.ts
│   │   └── notice-list.ts
│   └── normalizer.ts      # raw → canonical text + content hash
├── snapshots/             # Snapshot Store
│   ├── snapshot.model.ts
│   └── snapshot.repo.ts
├── detection/             # Diff / Change Detection
│   └── diff.ts            # hash gate + textual diff
├── processing/            # LLM Processing Pipeline
│   ├── pipeline.ts        # orchestrates diff→classify→summarize→extract
│   ├── prompts/           # versioned prompt templates
│   └── taxonomy.ts        # change-type / jurisdiction / severity enums
├── routing/               # Tiered Router
│   └── router.ts
├── review/                # Review Queue + Web UI backend
│   ├── review.model.ts
│   ├── review.repo.ts
│   └── web/               # review UI (or separate app)
├── effective-dates/       # Effective-Date Scheduler
│   └── activator.ts
├── delivery/              # Published Changes Store + Delivery API
│   ├── published.model.ts # the external contract type — versioned separately
│   ├── outbox.ts
│   └── api/               # read-only HTTP endpoints
├── domain/                # Shared core entities: Change, Jurisdiction
│   ├── change.model.ts
│   └── jurisdiction.ts
└── jobs/                  # Durable job queue + worker bootstrap
```

### Structure Rationale

- **`registry/seeds/` holds sources as data:** ~140+ heterogeneous sources must never become 140+ code paths. Adding a court = adding a config row, not deploying code.
- **`ingestion/fetchers/` is adapter-per-*kind*, not per-*source*:** there are only ~4 content kinds (HTML, PDF, RSS, notice list) even though there are 140+ sources. Source-specific quirks live in config the adapter reads.
- **`domain/` isolates the `Change` and `Jurisdiction` core types** so every plane shares one vocabulary, while `delivery/published.model.ts` is a *separate, deliberately versioned* type — the external API contract evolves independently of internals.
- **Each plane is a folder with its own repo:** stages communicate through persisted state, so each folder owns one set of tables and one job type. This keeps stages independently retryable and testable.

## Architectural Patterns

### Pattern 1: Pipeline-of-Stages over Durable State (not in-memory orchestration)

**What:** Each record (snapshot, diff, change) carries an explicit status. A stage picks up records in the prior status, does its work, and advances the status. State lives in the database between every stage.

**When to use:** Multi-step processing where steps are slow, fail independently, and must be re-runnable — exactly LLM calls + scraping + human review.

**Trade-offs:** More tables and explicit status columns vs. a monolithic function; in exchange you get crash-safety, observability ("how many changes are stuck in `processing`?"), and the ability to reprocess one stage without redoing the whole pipeline.

```typescript
// A Change advances through an explicit lifecycle, persisted at every step.
type ChangeStatus =
  | 'detected'      // diff found, not yet LLM-processed
  | 'processed'     // LLM enriched it
  | 'auto_published'// fees/forms — skipped review
  | 'in_review'     // routed to human queue
  | 'approved'      // reviewer accepted
  | 'rejected'      // reviewer discarded
  | 'pending'       // approved/auto but effective_date in the future
  | 'active';       // effective and exposed via the API
```

### Pattern 2: Hash-Gate Before Expensive Work

**What:** After normalization, compare the content hash to the last snapshot's hash. If equal → stop (no change). Only on mismatch do you store a new snapshot, run a diff, and call the LLM.

**When to use:** Always, when polling many sources frequently. The vast majority of polls find no change.

**Trade-offs:** Requires careful normalization so volatile noise (page timestamps, session tokens, rotating ads) doesn't cause false-positive hash mismatches → wasted LLM spend. Normalization quality is the single biggest cost lever.

```typescript
const normalized = normalize(rawBytes, source.kind);
const hash = sha256(normalized);
if (hash === source.lastContentHash) return; // no change — cheap exit
await snapshots.append(source.id, normalized, hash);
await jobs.enqueue('diff', { sourceId: source.id });
```

### Pattern 3: Confidence-Based Tiered Routing (Human-in-the-Loop)

**What:** The LLM attaches a change `type` and a `confidence` score. The router auto-publishes only low-stakes, high-confidence types (fees/forms); everything else, and anything low-confidence, goes to the human review queue.

**When to use:** When wrong/missed output has real-world cost (legal consequences here) but full manual review of everything is too slow.

**Trade-offs:** Auto-publish is faster but trusts the model on a narrow slice; a too-aggressive auto-publish tier is the main accuracy risk. Keep the auto tier deliberately small and add confidence floors even within it.

### Pattern 4: Transactional Outbox for Downstream Decoupling

**What:** When a change becomes `active`, write a row to a `published_changes` outbox table in the same transaction. The Delivery API serves *only* from that table. The downstream product pulls by cursor; never touches internal tables.

**When to use:** Whenever two systems must integrate without a shared database (an explicit project constraint).

**Trade-offs:** One extra table and a projection step vs. exposing internal models directly. The payoff: internal schema can change freely, the API contract is stable, and the same outbox row is the natural trigger for webhook fan-out later — at-least-once delivery, so consumers must dedupe by change id.

### Pattern 5: Adaptive Cadence as Computed State

**What:** The scheduler doesn't hardcode intervals. Each source has a base cadence (daily, or sub-daily if feed-backed). Known upcoming effective dates raise an "intensified" multiplier on the relevant source for a window around the date. `next_run_at` is recomputed after every poll.

**When to use:** Heterogeneous sources with uneven update frequency and time-sensitive events.

**Trade-offs:** A feedback loop (Effective-Date Scheduler → Polling Scheduler) adds coupling between two control-plane components; keep it one-directional (effective dates *inform* cadence, cadence never edits dates).

## Data Flow

### Primary Flow: Raw Fetch → Verified, Published Change

```
Scheduler decides source is due
        ↓
Fetcher adapter retrieves raw content (HTML / PDF / RSS / notice)
        ↓
Normalizer → canonical text + content hash
        ↓
Hash == last? ──yes──► STOP (record poll, recompute next_run_at)
        │ no
        ▼
Append new Snapshot (immutable, versioned)
        ↓
Diff vs previous snapshot → structured textual diff
        ↓
LLM Pipeline: detect substance → classify (type/jurisdiction/severity)
              → plain-language summary → extract fees/dates/forms
              → emit Change record (status=processed, + confidence)
        ↓
Tiered Router on Change.type
   ├─ fees / forms (high confidence) ──► status=auto_published
   └─ rule / order text, or low confidence ──► status=in_review
                                                   ↓
                                       Review UI: human approves/rejects
                                                   ↓ approved
        ┌──────────────────────────────────────────┘
        ▼
effective_date in future? ──yes──► status=pending  (Effective-Date Scheduler holds it;
        │ no                                        feeds the date to Polling Scheduler
        ▼                                           to intensify monitoring)
status=active  ──► write row to Published Changes outbox
        ↓
Delivery API serves it on next pull (GET /changes?since=cursor)
```

### Control Feedback Loop

```
Effective-Date Scheduler  ──(upcoming effective dates)──►  Polling Scheduler
        │                                                        │
        └──(activates pending changes on the date)                └──(intensifies cadence
            ──► Published Changes outbox                              for affected sources
                                                                      around that date)
```

### Modeling a "Source" and a "Change" (the scaling primitives)

These two entities are what let the system absorb 140+ heterogeneous jurisdictions without per-jurisdiction code.

**Source** — config + state, one row per monitored thing:

```typescript
interface Source {
  id: string;
  name: string;                       // "U.S. Bankruptcy Court, N.D. Cal. — Local Rules"
  layer: 'national' | 'district' | 'state';
  jurisdiction: string;               // "Title 11" | "CAND" | "TX"
  kind: 'html' | 'pdf' | 'rss' | 'notice_list';   // selects the fetcher adapter
  fetchConfig: Record<string, unknown>;           // URL, selectors, PDF page hints — adapter reads this
  baseCadence: 'daily' | 'subdaily';              // subdaily implies feed-backed
  // mutable state:
  lastCheckedAt: string | null;
  lastChangedAt: string | null;
  lastContentHash: string | null;
  nextRunAt: string;
  intensifyUntil: string | null;      // set by Effective-Date Scheduler
  health: 'ok' | 'degraded' | 'failing';
}
```
Heterogeneity is absorbed by `kind` (which adapter) + `fetchConfig` (the per-source quirks). New court = new row.

**Change** — the unit that flows through processing, review, and delivery:

```typescript
interface Change {
  id: string;
  sourceId: string;
  snapshotId: string;                 // the snapshot that triggered it
  // detection:
  diffSummary: string;                // structured textual diff
  // LLM enrichment:
  type: 'fee' | 'form' | 'rule_text' | 'order' | 'exemption_amount';
  jurisdiction: string;
  severity: 'minor' | 'moderate' | 'major';
  plainSummary: string;               // editable by reviewer
  extracted: Record<string, unknown>; // fees, form numbers, dollar amounts
  confidence: number;                 // drives routing
  // timing — first-class, tracked separately:
  detectedDate: string;               // when WE found it
  effectiveDate: string | null;       // when it takes legal effect
  // lifecycle:
  status: ChangeStatus;
  reviewedBy: string | null;
  reviewedAt: string | null;
}
```
`detectedDate` vs `effectiveDate` are deliberately separate fields, never conflated — the gap between them is what the Effective-Date Scheduler manages and what makes `pending` a real state.

**Multi-tenancy readiness:** add a nullable `tenantId` (or `audienceId`) to `Source`, `Change`, and `published_changes` now, defaulted to the internal tenant. It is far cheaper to carry an unused column than to retrofit a tenant key into every table and the API later. Do *not* build tenant management, auth scoping, or per-tenant config UI now — just don't bake in single-tenant assumptions in the schema.

## Scaling Considerations

This system scales on **number of sources × poll frequency**, and on **LLM throughput/cost** — not on end-user count (the only consumer is one downstream product, plus a handful of reviewers).

| Scale | Architecture Adjustments |
|-------|--------------------------|
| ~140 sources, internal-only (now) | Single app, single database, an in-process or lightweight durable job queue (e.g., DB-backed or Redis). One worker process. Modular monolith — all planes in one deployable. |
| ~500 sources / first external tenants | Separate the worker pool from the Delivery API process (different scaling profiles — workers are LLM-bound, API is light). Add per-source rate limiting and circuit breakers. Partition the job queue by plane. |
| Many tenants / thousands of sources | Horizontal worker scaling per plane; cache Delivery API responses; consider read replica for the Published Changes Store; move snapshot blobs fully to object storage. |

### Scaling Priorities

1. **First bottleneck — LLM cost & rate limits, not infrastructure.** Mitigated by the hash gate (Pattern 2) and tight normalization. Watch false-positive hash mismatches; each one is a wasted LLM call. Batch where possible.
2. **Second bottleneck — fetch politeness / source blocking.** 140+ sources, many fragile government sites. Per-source rate limits, backoff, and a `health` field with alerting prevent a scraper from getting the system IP-banned.
3. **Third bottleneck — review queue throughput (human).** If reviewers can't keep up, the auto-publish tier is too small or summaries are low quality. This is an operational signal, not an infra fix — measure queue age.

## Anti-Patterns

### Anti-Pattern 1: One scraper module per court

**What people do:** Write a bespoke fetcher/parser for each of the ~90 districts.
**Why it's wrong:** 90+ code paths to maintain; every site tweak is a deploy; no consistency. The project explicitly has "~140+ heterogeneous sources" — that count must live in *data*.
**Do this instead:** ~4 adapters keyed on `Source.kind`; all per-source variation in `Source.fetchConfig`. Adding a court is a registry row.

### Anti-Pattern 2: Sharing the database with the downstream product

**What people do:** Let "the other product" read the monitor's internal tables directly for convenience.
**Why it's wrong:** Explicitly out of scope per PROJECT.md; couples two deploy cycles, lets internal schema changes break the consumer, and exposes pre-verification (`in_review`, `pending`) data.
**Do this instead:** Transactional outbox + read-only Delivery API (Pattern 4). The `published_changes` table *is* the contract.

### Anti-Pattern 3: Conflating detected date with effective date

**What people do:** Store one `date` field and publish a change as soon as it's found.
**Why it's wrong:** Bankruptcy rule changes are routinely announced ahead of effect; publishing on detection makes the downstream product act on rules not yet in force.
**Do this instead:** Two fields; `pending` is a real lifecycle state; the Effective-Date Scheduler activates on the date. The same date intensifies monitoring.

### Anti-Pattern 4: In-memory pipeline orchestration

**What people do:** One long function: fetch → diff → call LLM → route, all in memory.
**Why it's wrong:** An LLM timeout or crash mid-pipeline loses work; no visibility into where changes are stuck; can't reprocess one stage.
**Do this instead:** Pipeline-of-stages over durable state (Pattern 1) — explicit status column, each stage independently retryable.

### Anti-Pattern 5: Auto-publishing too much

**What people do:** Expand the auto-publish tier to cut review load.
**Why it's wrong:** Legal stakes are high (PROJECT.md constraint); a misclassified rule-text change published unreviewed is the worst failure mode.
**Do this instead:** Keep the auto tier narrow (fees/forms only) and gate even that on a confidence floor; route anything ambiguous to humans.

### Anti-Pattern 6: Mutating snapshots

**What people do:** Update a "current content" row in place each poll.
**Why it's wrong:** Destroys the history that diffing and audit depend on; can't reprocess or explain a past change.
**Do this instead:** Append-only Snapshot Store; the latest row is "current" by `captured_at`.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Court websites (HTML) | Scheduled HTTP fetch via HTML adapter | Fragile gov sites; polite rate limits, retries, layout-shift tolerance in normalizer |
| Court documents (PDF) | Fetch + PDF text extraction in Normalizer | Scanned PDFs may need OCR — flag as a deeper-research item; text-layer PDFs are simpler |
| Official feeds (RSS / notice lists) | Feed poll via RSS / notice-list adapter | Feed-backed sources get `subdaily` cadence; feeds give cheap change signals |
| Claude API (LLM) | Structured calls from Processing Pipeline | Rate-limit aware; versioned prompts; structured/JSON output for the `Change` record |
| The other product (downstream) | Read-only pull of Delivery API | No shared DB; cursor pagination; webhook push deferred to a later milestone |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Scheduler ↔ Fetchers | Durable job queue | Scheduler enqueues; workers consume — decouples timing from execution |
| Stage ↔ Stage (ingest→detect→process→route) | Persisted status on records + jobs | No in-memory handoff; each stage is independently retryable |
| Processing ↔ Review UI | Shared `review_items` / `Change` tables | Same internal DB — these are one product |
| Effective-Date Scheduler ↔ Polling Scheduler | One-directional: dates inform cadence | Avoid a bidirectional loop; cadence never edits dates |
| Monitor ↔ Delivery API | Published Changes outbox table only | Hard internal boundary mirroring the external no-shared-DB rule |

## Suggested Build Order

Dependency-driven. Each step produces something demonstrable and unblocks the next.

1. **Source Registry + domain models (`Source`, `Change`).** Nothing can be fetched, scheduled, or processed without the source model. Seed a handful of sources across all three layers (one national, one district, one state) to exercise heterogeneity early.
2. **Fetchers + Normalizer + Snapshot Store.** Get raw content in, normalized, hashed, and versioned. End state: snapshots accumulate for seeded sources. (Scheduler can be a manual trigger here.)
3. **Adaptive Polling Scheduler.** Replace manual triggers with cadence-driven polling. Now the system runs unattended for static daily sources. (Intensified cadence comes later, after effective dates exist.)
4. **Diff / Change Detection.** Hash gate + textual diff. End state: real `detected` changes appear when seeded sources change.
5. **LLM Processing Pipeline.** Diff → classify → summarize → extract → `Change` with confidence. The first point the product produces human-readable value.
6. **Tiered Router + Review Queue + Web UI.** Auto-publish path for fees/forms; review path for rule text. End state: a human can approve/reject changes.
7. **Effective-Date Scheduler.** `pending` → `active` activation; wire the feedback loop that intensifies polling near effective dates (closes the loop opened in step 3).
8. **Published Changes outbox + Delivery API.** Project verified+active changes to the outbox; expose the read-only pull API. End state: the other product can integrate.
9. **(Later milestone) Webhook fan-out** off the same outbox; multi-tenant scoping activated on the already-present `tenantId` columns.

Rationale: ingestion must exist before detection; detection before LLM enrichment; enrichment before routing/review; review before effective-date activation (only verified changes should activate); delivery last because it consumes the output of everything upstream. Steps 1–4 give an unattended change-*detector*; steps 5–8 turn it into a verified change-*delivery* service.

## Sources

- [Web Scraping Architecture Patterns: From Prototype to Production (2026) — Apify](https://use-apify.com/blog/web-scraping-architecture-patterns) — adapter/abstraction layers, microservice stage separation, scraper→staging→transform flow (MEDIUM)
- [Enterprise Web Scraping Architecture Explained — X-Byte](https://www.xbyte.io/enterprise-web-scraping-architecture-explained/) — adaptive scheduling, distributed monitoring (MEDIUM)
- [How Website Change Detection Actually Works (Hashes, Diffs, Snapshots) — DEV/Apify](https://dev.to/apify_forge/how-website-change-detection-actually-works-hashes-diffs-and-snapshots-1aeb) — hash-gate-then-diff, snapshot history, diff-driven classification (HIGH)
- [changedetection.io — GitHub](https://github.com/dgtlmoon/changedetection.io) — reference implementation of fetch/snapshot/diff with a per-type processor plugin model (HIGH)
- [A2I: Multilingual Document Processing Pipeline with Human-in-the-Loop — ZenML LLMOps DB](https://www.zenml.io/llmops-database/multilingual-document-processing-pipeline-with-human-in-the-loop-validation) — confidence-threshold routing to a human review queue (MEDIUM)
- [Lessons from Running an LLM Document Processing Pipeline in Production — Alan / Medium](https://medium.com/alan/lessons-from-running-an-llm-document-processing-pipeline-in-production-33d87f99cdb1) — staged pipeline with status tracking, confidence-based fallback (MEDIUM)
- [Transactional outbox pattern — AWS Prescriptive Guidance](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html) — outbox for decoupled, reliable downstream delivery (HIGH)
- [Implementing the Outbox Pattern — Milan Jovanović](https://www.milanjovanovic.tech/blog/implementing-the-outbox-pattern) — outbox table + relay, at-least-once delivery, contract decoupling (MEDIUM)
- [Adapter — Refactoring.guru](https://refactoring.guru/design-patterns/adapter) — adapter pattern for incompatible-interface sources (HIGH)
- [Regulatory Compliance Monitoring: A 2026 Guide — Visualping](https://visualping.io/blog/regulatory-compliance-monitoring) — regulatory change-tracking workflow, text-compare for legal/policy docs (MEDIUM)

---
*Architecture research for: U.S. bankruptcy regulatory-change monitoring service*
*Researched: 2026-05-20*
