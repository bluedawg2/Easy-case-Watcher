# Requirements: Bankruptcy Rule Monitor

**Defined:** 2026-05-20
**Core Value:** The main bankruptcy product never operates on stale rules — every relevant jurisdiction rule change is detected, verified, and available before (or exactly when) it takes effect.

## v1 Requirements

Requirements for the initial release. Each maps to a roadmap phase.

### Source Registry & Coverage

- [x] **SRC-01**: A curated source registry holds one record per monitored source — jurisdiction, layer, authoritative URL/feed, ingestion method, parser/adapter reference, polling cadence, last-checked, last-changed, and health status
- [x] **SRC-02**: v1 covers the national layer — Bankruptcy Code (Title 11), Federal Rules of Bankruptcy Procedure, and Official Forms
- [ ] **SRC-03**: v1 covers an initial tranche of ~3 federal bankruptcy court districts — local rules, standing orders, and general orders
- [ ] **SRC-04**: v1 covers state exemption rules for the launch states only — the states that contain the v1 district tranche
- [ ] **SRC-05**: Source health monitoring distinguishes "checked, no change" from "checked, error" from "not checked," and alerts internally on staleness or layout drift
- [ ] **SRC-06**: A new source can be onboarded as a registry/config operation, without a code change

### Ingestion

- [x] **INGEST-01**: System ingests changes from RSS and official notice feeds
- [ ] **INGEST-02**: System ingests changes by scraping court-website HTML pages
- [ ] **INGEST-03**: System ingests and extracts text from PDF source documents
- [x] **INGEST-04**: Every fetch resolves to an explicit tri-state outcome — CHANGED, UNCHANGED, or FETCH_FAILED — so a silent failure is never read as "no change"
- [x] **INGEST-05**: Each successful fetch stores a versioned snapshot of the captured source content
- [ ] **INGEST-06**: Polling cadence is adaptive — daily by default, sub-daily for feed-backed sources, intensified around known upcoming effective dates
- [ ] **INGEST-07**: Polling respects a per-source politeness ceiling to avoid rate-limiting and IP blocks

### Change Detection

- [ ] **DETECT-01**: System detects substantive changes between the prior and current snapshot, ignoring boilerplate, navigation, and timestamps
- [ ] **DETECT-02**: A content-hash gate prevents unchanged content from triggering downstream processing
- [ ] **DETECT-03**: Duplicate detections of the same change (e.g., seen via both feed and scrape) are deduplicated

### AI Processing

- [ ] **AI-01**: AI identifies what substantively changed between old and new rule text
- [ ] **AI-02**: AI classifies each change against the taxonomy — layer/jurisdiction, change type, and severity
- [ ] **AI-03**: AI writes a plain-language summary of each change
- [ ] **AI-04**: AI extracts structured data from each change — fees, dollar amounts, dates, and form numbers
- [ ] **AI-05**: AI output carries a confidence score that drives routing decisions
- [ ] **AI-06**: Every AI-generated summary is labeled as informational and "not legal advice"

### Tiered Routing & Review

- [ ] **ROUTE-01**: Changes are routed by tier — fee/form/amount changes auto-publish; rule/order text changes route to human review
- [ ] **ROUTE-02**: Routing is confidence-gated — a low-confidence change in an auto-publish type is escalated to human review
- [ ] **ROUTE-03**: A web review queue presents each pending change with AI summary, highlighted diff, source link and snapshot, classification, confidence, extracted fields, and effective date
- [ ] **ROUTE-04**: A reviewer can approve, reject, or edit (correct the summary, classification, or extracted data) a pending change before approval
- [ ] **ROUTE-05**: An auto-published change can be corrected or retracted after publication

### Effective-Date Handling

- [x] **EFF-01**: Each change records detected date and effective date as separate fields
- [x] **EFF-02**: A change progresses through a lifecycle state machine — detected → classified → (review | auto-routed) → verified → active or pending-effective → superseded
- [ ] **EFF-03**: A verified change with a future effective date stays pending-effective and is not treated as in force
- [ ] **EFF-04**: A monitored scheduler automatically transitions a pending-effective change to active on its effective date
- [ ] **EFF-05**: A pending-effective change can be revised or withdrawn before it activates (postponement / withdrawal)
- [ ] **EFF-06**: System exposes an effective-date calendar of changes landing within the next N days

### Delivery API

- [ ] **API-01**: A pull-based read API exposes only verified changes to the other product
- [ ] **API-02**: API responses are filterable by jurisdiction, layer, change type, severity, status, and date ranges
- [ ] **API-03**: API supports incremental sync via a since-cursor ("what changed since timestamp T")
- [ ] **API-04**: API distinguishes active changes from verified-but-pending-effective changes
- [ ] **API-05**: API supports a temporal query — the rule state in force as of a given date (filing-date reasoning)
- [ ] **API-06**: The API contract is versioned, with stable taxonomy enums
- [ ] **API-07**: The monitor integrates with the other product via the API only — no shared database

### Audit, Lineage & Provenance

- [ ] **AUDIT-01**: Every change carries canonical source URL, effective date, and ingestion timestamp as first-class lineage fields
- [ ] **AUDIT-02**: An immutable audit trail records each change's lifecycle — detected, classified, reviewed-by, decision, published — with reviewer identity and timestamps
- [ ] **AUDIT-03**: Each AI-processed change records the model, prompt version, inputs, and confidence so the output is reproducible
- [ ] **AUDIT-04**: Rules, forms, and exemption items have stable, immutable internal IDs that persist across changes to official text or numbering
- [ ] **AUDIT-05**: Official forms track number, version, and supersession; a superseded item carries a soft-deprecation reference to its replacement

## v2 Requirements

Deferred to a future release. Tracked but not in the current roadmap.

### Coverage Expansion

- **COV-01**: Full ~90-district coverage, onboarded in tranches once the adapter pattern is proven
- **COV-02**: Full state exemption coverage across all 50 states

### Intelligence

- **INT-01**: Confidence-calibration tuning driven by accumulated reviewer corrections

### Delivery

- **DLV-01**: Webhook / push notification of new verified changes
- **DLV-02**: Multi-tenant, customer-facing product layer
- **DLV-03**: Customer-facing dashboards and reporting

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Shared database with the other product | Couples deployments, leaks schema, blocks productization — integrate via API only |
| Legal interpretation / advice ("what you must do") | Liability and accuracy exposure beyond summarization — the monitor reports facts only |
| "Intent graph" / user filing-goal modeling ("file a Chapter 7" paths) | Belongs to the consuming bankruptcy product — this monitor owns the temporal "rule graph" only |
| Real-time / minute-level polling of all sources | Court rules change days-to-months apart — wastes resources and risks IP blocks; effective dates give natural lead time |
| User-configurable arbitrary-URL monitoring | Sources are a curated, parser-backed catalog — arbitrary URLs break the coverage/quality guarantee |
| Internal-controls mapping / remediation task management | Built for compliance teams managing their own obligations — this is a fact source, not a workflow tool |
| Custom ML classifier trained from scratch | Cold-start with no labeled corpus, brittle — an LLM with a prompt-defined taxonomy iterates far more cheaply |
| Case-law / opinion monitoring | A different problem from rule/form/statute text — a possible v2+ adjacency, not v1 |

## Traceability

Which phases cover which requirements. Populated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| SRC-01 | Phase 1 | Complete |
| SRC-02 | Phase 1 | Complete |
| INGEST-01 | Phase 1 | Complete |
| INGEST-04 | Phase 1 | Complete |
| INGEST-05 | Phase 1 | Complete |
| DETECT-01 | Phase 1 | Pending |
| DETECT-02 | Phase 1 | Pending |
| AI-01 | Phase 1 | Pending |
| AI-03 | Phase 1 | Pending |
| AI-06 | Phase 1 | Pending |
| ROUTE-03 | Phase 1 | Pending |
| ROUTE-04 | Phase 1 | Pending |
| EFF-01 | Phase 1 | Complete |
| EFF-02 | Phase 1 | Complete |
| API-01 | Phase 1 | Pending |
| API-07 | Phase 1 | Pending |
| INGEST-02 | Phase 2 | Pending |
| INGEST-07 | Phase 2 | Pending |
| SRC-05 | Phase 2 | Pending |
| SRC-06 | Phase 2 | Pending |
| DETECT-03 | Phase 2 | Pending |
| INGEST-03 | Phase 3 | Pending |
| SRC-03 | Phase 3 | Pending |
| SRC-04 | Phase 3 | Pending |
| INGEST-06 | Phase 4 | Pending |
| AI-05 | Phase 4 | Pending |
| AI-02 | Phase 5 | Pending |
| AI-04 | Phase 5 | Pending |
| ROUTE-01 | Phase 5 | Pending |
| ROUTE-02 | Phase 5 | Pending |
| ROUTE-05 | Phase 5 | Pending |
| EFF-03 | Phase 6 | Pending |
| EFF-04 | Phase 6 | Pending |
| EFF-05 | Phase 6 | Pending |
| EFF-06 | Phase 6 | Pending |
| API-04 | Phase 6 | Pending |
| API-02 | Phase 7 | Pending |
| API-03 | Phase 7 | Pending |
| API-05 | Phase 7 | Pending |
| API-06 | Phase 7 | Pending |
| AUDIT-05 | Phase 7 | Pending |
| AUDIT-01 | Phase 8 | Pending |
| AUDIT-02 | Phase 8 | Pending |
| AUDIT-03 | Phase 8 | Pending |
| AUDIT-04 | Phase 8 | Pending |

**Coverage:**
- v1 requirements: 45 total
- Mapped to phases: 45 ✓
- Unmapped: 0

---
*Requirements defined: 2026-05-20*
*Last updated: 2026-05-20 after roadmap creation*
