# Phase 3: PDF Ingestion & District Coverage - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-22
**Phase:** 3-PDF Ingestion & District Coverage
**Areas discussed:** District tranche, OCR strategy, PDF pilot demo, State exemption sources, Document taxonomy within districts

---

## District Tranche

### How the ~3-district tranche is chosen

| Option | Description | Selected |
|--------|-------------|----------|
| Big corporate venues | Delaware + S.D.N.Y. + S.D. Texas — highest filing volume / rule activity | |
| Adapter-variety trio | 3 districts spanning ingestion formats | |
| I'll name the districts | User names specific districts | |
| Lock criteria, defer to research | Decide criteria now, researcher picks the 3 districts | ✓ |

**User's choice:** Lock criteria, defer to research.

### What the selection criteria prioritize

| Option | Description | Selected |
|--------|-------------|----------|
| Adapter-format variety | Span ingestion formats to stress-test the adapter pattern | ✓ |
| Clean PDF publishing | Favor well-structured text-layer PDFs | ✓ |
| Rule-change activity | Favor districts that amend rules often | ✓ |
| Filing volume | Favor high-volume districts | ✓ |
| Fixture cleanliness / determinism (free text) | Favor sources that reproduce as deterministic fixtures | ✓ |

**User's choice:** All four options + added "Fixture cleanliness / determinism".

### What kind of format variety the tranche spans

| Option | Description | Selected |
|--------|-------------|----------|
| PDF-internal variety | All 3 districts PDF-centric; span text-layer / scanned / table-heavy sub-types | ✓ |
| Cross-channel variety | Span HTML / PDF / feed across the 3 districts | |
| Both — PDF-internal primary | PDF sub-type variety primary; document extra channels if present | |

**User's choice:** PDF-internal variety.

### Whether the tranche spans 3 distinct states

| Option | Description | Selected |
|--------|-------------|----------|
| 3 distinct states | Force districts into 3 different states | |
| Don't constrain it | State spread incidental | |
| Distinct states, soft preference | Distinct states a tie-breaker only; PDF/activity criteria win | ✓ |

**User's choice:** Distinct states, soft preference.

---

## OCR Strategy

### Does Phase 3 run OCR, or detect-and-escalate

| Option | Description | Selected |
|--------|-------------|----------|
| Run real OCR now | Build a working OCR step | |
| Detect & escalate, OCR stub | Detect image-only PDFs, escalate; OCR engine is a deferred stub | ✓ |
| Real OCR, one engine, narrow | Run real OCR but scoped tight | |

**User's choice:** Detect & escalate, OCR stub.

### How an image-only PDF outcome is recorded

| Option | Description | Selected |
|--------|-------------|----------|
| Distinct 'needs OCR' signal | A dedicated outcome/health value separate from FETCH_FAILED | |
| FETCH_FAILED + reason | Reuse FETCH_FAILED with a reason code | ✓ |
| Plain FETCH_FAILED | Flat FETCH_FAILED, no tagging | |

**User's choice:** FETCH_FAILED + reason.

### Which engine the seam is shaped for

| Option | Description | Selected |
|--------|-------------|----------|
| Leave engine-agnostic | Generic seam, no engine preference recorded | ✓ |
| Lean Claude vision | Note Claude vision as intended engine | |
| Lean Tesseract/ocrmypdf | Note local Tesseract as intended engine | |

**User's choice:** Leave engine-agnostic.

### Distinguishing a scanned PDF from a broken text-layer PDF

| Option | Description | Selected |
|--------|-------------|----------|
| Distinguish the two | Image-only vs broken-text-layer get different reason codes | ✓ |
| One near-empty rule | Single FETCH_FAILED reason regardless of cause | |
| Claude's discretion | Defer the detection heuristic | |

**User's choice:** Distinguish the two.

---

## PDF Pilot Demo

### Which district document type is the pilot

| Option | Description | Selected |
|--------|-------------|----------|
| General order | A general order PDF — changes most often | |
| Local rules | The local bankruptcy rules PDF — amends rarely | |
| Standing order | A standing order PDF — middle ground | |
| Pilot doc by research | Researcher picks the type with a verifiable real change | ✓ |

**User's choice:** Pilot doc by research.

### How the changed/unchanged fixture pair is built

| Option | Description | Selected |
|--------|-------------|----------|
| Two real versions, prefer | Prefer a real superseded-vs-replacement pair | |
| Real + hand-modified copy | One real PDF + a controlled hand-modified copy | |
| Decide in research | Lock the constraints, researcher chooses the construction | ✓ |

**User's choice:** Decide in research.

### Whether a PDF-sourced change looks different to the reviewer

| Option | Description | Selected |
|--------|-------------|----------|
| Flag PDF provenance | Surface a PDF-extraction signal on the review item | ✓ |
| Identical to other channels | PDF change appears like a feed/HTML change | |
| Link the source PDF | No badge, but link the original source PDF | |

**User's choice:** Flag PDF provenance.

---

## State Exemption Sources

### How ingestion method is decided for state exemption statutes

| Option | Description | Selected |
|--------|-------------|----------|
| Per-source, reuse adapters | Decide per state; reuse HTML/PDF adapters | |
| Force one method | Standardize on a single method | |
| Decide in research | Lock adapter-reuse constraint; researcher determines per-state method | ✓ |

**User's choice:** Decide in research.

### How PDF tables (exemption amounts) are handled

| Option | Description | Selected |
|--------|-------------|----------|
| pdfplumber, selectively | Add pdfplumber only for genuinely tabular content | ✓ |
| Text-only, defer tables | Text extraction only; defer table parsing to Phase 5 | |
| Decide in research | Defer the pdfplumber-vs-text-flatten choice | |

**User's choice:** pdfplumber, selectively.

### What 'covers state exemption rules' means for Phase 3 scope

| Option | Description | Selected |
|--------|-------------|----------|
| Ingest + detect text only | Detect statute text changes; defer structured amount parsing | ✓ |
| Also parse amounts now | Additionally extract dollar amounts as structured fields | |

**User's choice:** Ingest + detect text only.

### How an exemption-statute source maps to Source registry rows

| Option | Description | Selected |
|--------|-------------|----------|
| Decide in research | One or several rows per state; researcher determines from real statutes | ✓ |
| One row per state | Exactly one Source row per state | |
| One row per statute section | A row per distinct exemption code section | |

**User's choice:** Decide in research.

---

## Document Taxonomy Within Districts

### How the registry/detection model handles local rules vs general orders

| Option | Description | Selected |
|--------|-------------|----------|
| Two source patterns | A 'document' source and an 'index/listing' source, detected differently | ✓ |
| Every doc is its own Source | Each order its own Source row; uniform document model | |
| Everything is a listing | All district sources index-style | |
| Decide in research | Defer the registry/detection model design | |

**User's choice:** Two source patterns.

### Where district document type sits in the Source registry

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse layer, row per type | (district × document-type) per Source row; no schema change | |
| New document_type column | Add a dedicated document_type column | |
| Decide in planning | Lock that it's a registry value; planner chooses | ✓ |

**User's choice:** Decide in planning.

### Where the document-vs-index/listing pattern distinction lives

| Option | Description | Selected |
|--------|-------------|----------|
| Explicit source field | A dedicated source_pattern field on the Source row | |
| Implied by adapter | Implicit in the adapter_ref | |
| Decide in planning | Lock that both patterns are first-class; planner chooses | ✓ |

**User's choice:** Decide in planning.

### What happens on a listing source's first poll

| Option | Description | Selected |
|--------|-------------|----------|
| Baseline, no backlog flood | Record existing entries as baseline; zero Change records | ✓ |
| Ingest full backlog | Treat every existing order as a detected Change | |
| Baseline + bounded recent | Baseline the backlog, ingest a bounded recent window | |

**User's choice:** Baseline, no backlog flood.

---

## Claude's Discretion

- The actual 3 districts, the pilot document type, the fixture-pair construction, the per-state ingestion method, and the per-state Source-row set — delegated to the phase researcher against the locked constraints (D-01, D-09, D-10, D-12, D-15).
- Registry/schema shape — delegated to the planner: how district document type sits in the registry (reuse `layer` vs new `document_type` column), and where the document-vs-listing pattern distinction lives (explicit `source_pattern` field vs adapter-encoded). Locked constraints: registry values not code, both patterns first-class, VARCHAR+CHECK over native ENUM.
- Tuning thresholds — near-empty extraction threshold, normalization aggressiveness, binary-PDF snapshot storage/retention.

## Deferred Ideas

- A working OCR engine (engine choice driven by what real scanned sources look like).
- Structured extraction of exemption dollar amounts / fees / form numbers — Phase 5 (AI-04).
- Adaptive polling cadence — Phase 4 (INGEST-06).
- Full ~90-district and full 50-state coverage — v2 (COV-01/COV-02).
- PACER / login-gated court sources — remain excluded from v1.
