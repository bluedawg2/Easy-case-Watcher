# Phase 3: PDF Ingestion & District Coverage - Research

**Researched:** 2026-05-22
**Domain:** PDF text extraction, scanned-vs-text-layer detection, court-source onboarding
**Confidence:** HIGH (stack, PDF technique, source patterns), MEDIUM (specific live PDF sub-types — see Open Questions)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**District Tranche Selection**
- **D-01:** The *specific* 3 districts are a research task — selection *criteria* are locked; researcher picks actual districts against live court sites.
- **D-02:** Selection criteria, all weighted: adapter-format variety, clean PDF publishing, rule-change activity, filing volume, fixture cleanliness/determinism (sources must reproduce as deterministic, replayable fixtures).
- **D-03:** "Format variety" = **PDF-internal variety** — the 3 districts span PDF sub-types: a clean text-layer PDF, a scanned/image-only PDF, a table-heavy PDF. Cross-channel variety rejected.
- **D-04:** Three distinct states is a **soft tie-breaker only** — PDF/activity criteria win outright; state spread never overrides them.

**OCR Strategy**
- **D-05:** Phase 3 is **detect-and-escalate, not run-OCR.** Adapter reliably detects image-only PDFs and routes to operator escalation; the OCR engine itself is a deferred stub.
- **D-06:** A detected image-only PDF uses the **existing FETCH_FAILED tri-state outcome** stamped with a reason code (e.g. `image_only_pdf`). No new outcome enum.
- **D-07:** The OCR seam is **engine-agnostic** — generic "image PDF → text" interface, no engine preference recorded.
- **D-08:** The adapter **distinguishes a scanned PDF from a broken text-layer PDF** — both extract near-empty, but: near-empty + image page structure → `image_only_pdf` (expected); near-empty + PDF *does* carry a text layer → genuine extraction-failure reason (a bug). Same FETCH_FAILED outcome, different reason codes.

**PDF Pilot Demo (criterion 5)**
- **D-09:** The pilot document **type** is a research task — a district PDF with a *verifiable real change*. General orders noted as likeliest to have recent activity; choice follows the evidence.
- **D-10:** The changed/unchanged **PDF fixture pair construction is a research task** — locked constraint: a deterministic PDF fixture pair MUST exist and MUST replay through the same adapter as live ingestion (no production-only branch — carries Phase 1 D-04 / Phase 2 D-17).
- **D-11:** A PDF-sourced change carries a **PDF-provenance flag on the review-queue item** (and whether OCR was involved). Reuses Phase 1's queue UI with one additive field/badge.

**State Exemption Sources (SRC-04)**
- **D-12:** State exemption sources **reuse existing adapters** — Phase 2 HTML adapter for legislative HTML pages, Phase 3 PDF adapter for statute PDFs. **No new adapter code.** Per-state ingestion method is a research task.
- **D-13:** **pdfplumber added selectively** — only for genuinely tabular content. **pypdfium2 stays the default** for prose PDFs.
- **D-14:** Phase 3 exemption scope is **ingest + detect text changes only** — detect when statute text changes (including a dollar amount inside it) as a text diff. Parsing the amount as structured value is Phase 5 (AI-04).
- **D-15:** Exemption-statute **Source-row granularity is a research task** — one or several Source rows per state. Onboarding stays a registry/config operation regardless (SRC-06).

**Document Taxonomy Within Districts**
- **D-16:** District sources follow **two distinct source patterns**: a **"document" source** (local rules — one canonical PDF, diffed for amendments) and an **"index/listing" source** (general/standing orders — detect newly-appeared entries on a court index page, then ingest each new order PDF). Detection treats the two differently.
- **D-17:** When an **index/listing source is first onboarded**, the first poll **records all existing index entries as the starting baseline — zero Change records, nothing into the review queue.** Only orders appearing after onboarding become Changes.
- **D-18:** A brand-new general/standing order (no prior version) becomes a `detected` Change with a full-text "addition" diff and flows through the existing Phase 1 detect → AI-summary → review-queue pipeline unchanged.

### Claude's Discretion
- **District/PDF/state research tasks (D-01, D-09, D-10, D-12, D-15)** — delegated to the phase researcher (this document) against locked constraints.
- **Registry/schema shape — delegated to the planner:** (a) district document type — reuse freeform `layer` field per (district × document-type) Source row, OR add a dedicated `document_type` column; (b) document-vs-listing pattern distinction — explicit `source_pattern` field, OR implicit in `adapter_ref`. Locked constraints: document type and source pattern must be **registry values, not code**; both patterns first-class; Phase 1 precedent (VARCHAR + CHECK over native PG ENUM) applies to any new classifying column.
- **Tuning thresholds:** near-empty extraction threshold (chars/page, image-coverage ratio), normalization aggressiveness, snapshot storage/retention for binary PDF artifacts — sensible defaults, per-source-overridable config where cheap.

### Deferred Ideas (OUT OF SCOPE)
- A working OCR engine (Tesseract/ocrmypdf vs Claude vision vs cloud OCR) — Phase 3 detects and escalates only.
- Structured extraction of exemption dollar amounts / fees / form numbers — Phase 5 (AI-04).
- Adaptive polling cadence — Phase 4 (INGEST-06).
- Full ~90-district and full 50-state coverage — v2 (COV-01/COV-02).
- PACER / login-gated court sources — excluded from v1 (Phase 2 D-04).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INGEST-03 | System ingests and extracts text from PDF source documents | PDF fetcher adapter behind `SourceAdapter` seam (Standard Stack + Architecture Patterns); pypdfium2 text-layer extraction; text-layer-vs-scanned detection via char-count + image-object inspection (Pattern 3, D-08); near-empty → FETCH_FAILED with reason code (Pattern 4) |
| SRC-03 | v1 covers ~3 federal bankruptcy court districts — local rules, standing orders, general orders | District tranche recommendation (Open Question 1 + Architecture Patterns: two source patterns); document-source vs index/listing-source pattern (D-16/D-17/D-18) |
| SRC-04 | v1 covers state exemption rules for launch states | Per-state ingestion method + Source-row granularity (Open Question 2); CA leginfo HTML, OR statute HTML, TX statute PDF, CA EJ-156 table-heavy PDF |
</phase_requirements>

## Summary

Phase 3 widens ingestion to PDF source documents and onboards the first ~3 federal bankruptcy court districts plus their launch-state exemption sources. The stack is fully locked by CLAUDE.md — **pypdfium2** (Apache-2.0/BSD-3-Clause, resale-license-clean) for default prose text extraction, **pdfplumber** added selectively for genuinely tabular content, **httpx** for fetching PDF bytes, `difflib` for the cheap diff pre-filter. No new libraries are needed; no OCR engine is installed (D-05). The work is mostly *integration* of well-understood tools into the existing `SourceAdapter` seam, plus the genuinely substantive design decisions around scanned-PDF detection and the two district source patterns.

The single highest-risk technical task is **reliably distinguishing a scanned/image-only PDF from a PDF with a broken text layer** (D-08). Both extract as near-empty text, but they mean opposite things: a scanned PDF is "can't process *yet*" (expected, awaiting OCR), a broken text layer is a bug. pypdfium2 exposes exactly the primitives needed — `textpage.count_chars()` / `get_text_range()` for the text-layer measurement, and `page.get_objects()` filtered on `FPDF_PAGEOBJ_IMAGE` for image-coverage measurement. The detection rule is a two-axis classification: low char-count **AND** high image-area coverage → `image_only_pdf`; low char-count **AND** low image coverage → `extraction_failed` (a real bug). This is the load-bearing logic of plan 03-01.

For the district tranche, live-site investigation identified strong candidates spanning all three required PDF sub-types. **Primary recommendation:** District of Oregon (clean text-layer local-rules PDF *plus* a published prior version — a real superseded-vs-replacement pair for criterion 5's fixture, D-10), Central District of California (text-layer general-orders index/listing source — exercises the D-16 listing pattern, and CA is a high-volume filing state), and Western District of Texas (standing-orders index — adds a third state and a candidate scanned/signed-order PDF). Launch states are therefore Oregon, California, Texas, each with a well-defined official exemption-statute source. The scanned/image-only PDF sub-type (D-03) is the one item that needs live confirmation during execution — see Open Questions.

**Primary recommendation:** Build one `PdfSourceAdapter` behind the existing seam. It (1) fetches PDF bytes via httpx, (2) extracts text with pypdfium2 — pdfplumber only when the Source's JSONB config flags `tabular: true`, (3) runs the two-axis scanned-vs-broken classification on near-empty extractions, mapping both to FETCH_FAILED with distinct reason codes, (4) normalizes extracted text (de-hyphenation, line-number/header stripping, ligatures) before hashing/diffing. Onboard Oregon as the "document" pattern and CACB as the "index/listing" pattern; use Oregon's published clean+prior LBR pair as the deterministic criterion-5 fixture.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Fetch PDF bytes over HTTP | Ingestion (`PdfSourceAdapter`) | — | Same tier as RSS/HTML adapters; behind `SourceAdapter` seam |
| PDF text extraction (prose) | Ingestion (pypdfium2) | — | Pure-CPU transformation inside the adapter |
| PDF table extraction (selective) | Ingestion (pdfplumber) | — | Per-source JSONB-flagged; adapter chooses extractor |
| Scanned-vs-broken classification | Ingestion (PDF adapter) | Source-health read view (Phase 2) | Detection is in-adapter; the `image_only_pdf` reason surfaces in the health view |
| Text normalization | Detection (`detect/normalize.py`) | — | Pure function; runs before hash/diff, same as Phase 1/2 |
| Change detection / diff | Detection (`detect/detector.py`) | — | Unchanged from Phase 1 — PDF text diffs like any other text |
| Index/listing "new entry" detection | Ingestion (PDF adapter, listing mode) | Detection | Listing-page parse identifies new order entries; each new order then diffs as an addition |
| District / state source registry rows | Persistence (Postgres `source` table) | — | Config-only onboarding (SRC-06); registry values not code |
| OCR (engine) | — (deferred) | — | Out of scope — engine-agnostic stub seam only (D-05/D-07) |
| Review-queue PDF-provenance badge | API + Frontend (Phase 1 UI) | — | One additive field on `Change`, one badge in the SPA |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pypdfium2 | 5.8.0 | Default PDF text extraction + page-object inspection | `[CITED: CLAUDE.md]` Apache-2.0/BSD-3-Clause — resale-license-clean (PyMuPDF's AGPL forbidden). `[VERIFIED: PyPI]` 5.8.0 current. `[CITED: github.com/pypdfium2-team/pypdfium2]` exposes `get_textpage`, `count_chars`, `get_text_range`, `get_objects` — exactly the primitives D-08 needs |
| pdfplumber | 0.11.9 | Table-aware extraction — *selective* use only (D-13) | `[CITED: CLAUDE.md]` "add only for specific sources … not the default". `[VERIFIED: PyPI]` 0.11.9 current. Used only when a Source's JSONB config flags tabular content (e.g. CA EJ-156) |
| httpx | 0.28.1 | Async HTTP client — fetches PDF bytes | `[CITED: CLAUDE.md]` already the project fetcher. `[VERIFIED: PyPI]` 0.28.1 current. Already in use (`src/brm/ingest/rss.py`). PDF fetch differs only in reading `response.content` as bytes, not parsing HTML |
| difflib (stdlib) | stdlib | Cheap deterministic diff pre-filter / unified diff | `[CITED: CLAUDE.md]` Already used (`src/brm/detect/diff.py`) — PDF-extracted text diffs identically to HTML/feed text |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| SQLAlchemy + Alembic | 2.0.x / 1.13.x | ORM + migration for any new `Source`/`Change` columns | `[CITED: CLAUDE.md]` Already in use. A hand-written migration adds the district document-type / source-pattern column(s) (planner's discretion) and the `Change` PDF-provenance field |
| selectolax | 0.3.x | HTML parsing — for index/listing court pages and legislative HTML | `[CITED: CLAUDE.md]` Already used (`src/brm/ingest/rss.py`). The index/listing source pattern (D-16) parses an HTML court index page to find new order entries — this is HTML parsing, reusing the Phase 2 adapter |
| respx | current | HTTP mocking for fixture-replay tests | `[CITED: CLAUDE.md]` Already used (`tests/conftest.py` `mock_http`). PDF fixtures replay as `httpx.Response(200, content=pdf_bytes)` — identical mechanism to HTML fixtures |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pypdfium2 | PyMuPDF (fitz) | **FORBIDDEN by CLAUDE.md** — AGPL-3.0 poisons the resale path. Do not use under any circumstance |
| pypdfium2 | pypdf (pure-Python) | Slower, weaker positional data, no page-object/image inspection API. pypdfium2's `get_objects()` is needed for D-08 image-coverage detection — pypdf cannot do it cleanly |
| pdfplumber everywhere | pdfplumber as default | Rejected by D-13/CLAUDE.md — slower, and table-flow extraction produces reflowed-text *noise* on prose PDFs, which would create spurious diffs. Prose → pypdfium2, tables → pdfplumber |
| Real OCR now | Tesseract / ocrmypdf / Claude vision | Rejected by D-05 — Phase 3 detects-and-escalates. Installing an OCR engine is out of scope; the seam is engine-agnostic (D-07) |

**Installation:**
```bash
uv add pypdfium2 pdfplumber
# httpx, selectolax, difflib, SQLAlchemy, Alembic, respx already present
```

## Package Legitimacy Audit

> slopcheck 0.6.1 is installed but its CLI invocation form could not be confirmed in this session (Python 3.14 environment; `slopcheck install` and `slopcheck <pkg>` both returned no parseable output). Per the graceful-degradation rule, registry verification was done directly via `pip index versions`, and packages are documented with their provenance below.

| Package | Registry | Age | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-------------|-----------|-------------|
| pypdfium2 | PyPI | mature (v5.x; v0.1.0 dates to 2021) | github.com/pypdfium2-team/pypdfium2 | not run (CLI unconfirmed) | Approved — `[VERIFIED: PyPI]` 5.8.0; `[CITED: CLAUDE.md]` as locked stack; official PDFium-team binding |
| pdfplumber | PyPI | mature (v0.x since 2017, jsvine) | github.com/jsvine/pdfplumber | not run (CLI unconfirmed) | Approved — `[VERIFIED: PyPI]` 0.11.9; `[CITED: CLAUDE.md]` as locked stack |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

Both packages are explicitly named in CLAUDE.md's locked stack and confirmed present on PyPI with long histories and well-known source repos. No new/unknown packages are introduced by this phase. No `postinstall`-equivalent risk (Python wheels; pypdfium2 ships a self-contained binary wheel, no system PDF libs). Treat both as `[VERIFIED: PyPI + CLAUDE.md]`; slopcheck was unavailable so the planner may optionally still gate the `uv add` behind a `checkpoint:human-verify` — but the risk here is minimal given CLAUDE.md provenance.

## Architecture Patterns

### System Architecture Diagram

```
                         run_ingest (pipeline.py — UNCHANGED shared orchestrator)
                                          │
                                          ▼
                              adapter.fetch(source)
                                          │
        ┌─────────────────────────────────┼──────────────────────────────┐
        ▼                                 ▼                              ▼
  FrbpSourceAdapter (P1)          HtmlAdapter (P2)               PdfSourceAdapter (P3 — NEW)
  RSS/HTML rulemaking            generic HTML scrape                      │
                                                    ┌─────────────────────┴───────────────┐
                                                    ▼                                     ▼
                                          source_pattern = "document"        source_pattern = "index_listing"
                                          (local rules — 1 canonical PDF)    (general/standing orders index)
                                                    │                                     │
                                          httpx GET pdf_url                  httpx GET index_html_url
                                                    │                          selectolax parse → order entries
                                                    │                                     │
                                                    │                          NEW entry vs baseline set?
                                                    │                          ├─ no  → UNCHANGED
                                                    │                          └─ yes → httpx GET each new order PDF
                                                    │                                     │
                                                    └──────────────┬──────────────────────┘
                                                                   ▼
                                                   pypdfium2 extract text
                                                   (pdfplumber if JSONB config tabular=true)
                                                                   │
                                          ┌────────────────────────┼────────────────────────┐
                                          ▼                        ▼                        ▼
                                  text extracted OK        near-empty + images       near-empty + text layer
                                          │                 → FETCH_FAILED            → FETCH_FAILED
                                          │                   reason=image_only_pdf     reason=extraction_failed
                                          ▼                        │                        │
                              normalize() de-hyphenate,            └──── surfaces in ────────┘
                              strip line-numbers/headers,           Phase-2 source-health view
                              fold ligatures                        + Sentry alert
                                          │
                                   SHA-256 hash → CHANGED / UNCHANGED
                                          │
                                          ▼
                          store_snapshot → detect_change → Change(status=detected)
                          [Change carries PDF-provenance flag — D-11]
                                          │
                                          ▼
                          AI summary → review queue (Phase 1 pipeline — UNCHANGED, D-18)
```

### Recommended Project Structure
```
src/brm/
├── ingest/
│   ├── adapter.py          # SourceAdapter Protocol — UNCHANGED
│   ├── rss.py              # FrbpSourceAdapter — UNCHANGED
│   ├── html.py             # HtmlAdapter (Phase 2)
│   ├── pdf.py              # NEW — PdfSourceAdapter (document + listing modes)
│   ├── pdf_extract.py      # NEW — pypdfium2/pdfplumber extraction + scanned detection
│   └── outcome.py          # FetchResult — extend with optional reason_code field
├── detect/
│   └── normalize.py        # extend — add pdf_normalize() (de-hyphenation etc.)
├── models/
│   ├── source.py           # migration — add document_type / source_pattern column(s)
│   └── change.py           # migration — add pdf_provenance flag column
└── config.py               # add PDF tunables (near-empty thresholds, normalize toggles)
tests/
├── fixtures/
│   ├── pdf/                # NEW — captured PDF fixtures (clean, scanned, table-heavy, change pair)
│   └── ...
└── test_pdf_adapter.py     # NEW — fixture-replay covering every PDF path
```

### Pattern 1: PDF fetcher as a new adapter behind the existing seam
**What:** `PdfSourceAdapter` is a new class implementing the existing `SourceAdapter` Protocol (`async def fetch(self, source) -> FetchResult`). It is NOT a new fetch layer. `run_ingest` in `pipeline.py` is unchanged — it already routes any adapter through fetch → store_snapshot → detect_change.
**When to use:** Every PDF source. The adapter is selected per-Source by `adapter_ref` exactly as the FRBP adapter is today.
**Example:**
```python
# Source: established pattern in src/brm/ingest/rss.py (FrbpSourceAdapter)
class PdfSourceAdapter:
    """SourceAdapter for PDF document sources and PDF-order index/listing sources."""
    async def fetch(self, source: "Source") -> FetchResult:
        # source.source_pattern decides "document" vs "index_listing" mode.
        # Both modes converge on pypdfium2 extraction → normalize → hash → tri-state.
        ...
```

### Pattern 2: Two district source patterns — "document" vs "index/listing" (D-16)
**What:** A "document" source is one canonical PDF (local rules) — fetch it, extract, diff against the prior snapshot. An "index/listing" source is an HTML court index page (general/standing orders) — parse it for order entries, compare the entry set against the stored baseline; each *newly appeared* order is then fetched as its own PDF and diffed as a full-text "addition" (D-18).
**When to use:** Document mode = local rules. Index/listing mode = general orders, standing orders.
**Key sub-rules:**
- **First poll of a listing source = silent baseline (D-17):** record all existing index entries, zero Changes, nothing into the review queue. Mirrors Phase 1's first-fetch rule (already implemented in `detect/detector.py` — `prior_snapshot is None → return None`).
- A brand-new order with no prior version → `detected` Change with a full-text addition diff (D-18), flowing through the unchanged Phase 1 pipeline.
**Example:**
```python
# index/listing mode — conceptual
entries = parse_order_index(index_html)           # selectolax — like rss.py parse_entries
new_orders = entries_set - baseline_entries_set   # set difference against stored baseline
# first poll: baseline empty → store entries as baseline, return UNCHANGED (silent)
# subsequent: each new order → fetch its PDF → extract → Change(addition)
```

### Pattern 3: Two-axis scanned-vs-broken classification (D-08)
**What:** Near-empty text extraction is ambiguous. Resolve it with two independent measurements per page, then a combined rule.
- **Text-layer measurement:** `textpage.count_chars()` (or length of `get_text_range()`), summed/averaged across pages → chars-per-page.
- **Image-coverage measurement:** iterate `page.get_objects()`, sum the bounding-box area of objects whose `type == FPDF_PAGEOBJ_IMAGE`, divide by page area → image-area ratio.
- **Rule:** low chars-per-page **AND** high image-area ratio → `image_only_pdf` (expected — awaiting OCR). Low chars-per-page **AND** low image-area ratio → `extraction_failed` (a real bug). Adequate chars-per-page → normal extraction.
**When to use:** Always, on every PDF extraction, before deciding the FetchOutcome.
**Example:**
```python
# Source: github.com/pypdfium2-team/pypdfium2 API (count_chars, get_objects, FPDF_PAGEOBJ_IMAGE)
import pypdfium2 as pdfium
pdf = pdfium.PdfDocument(pdf_bytes)
total_chars = 0
image_area = 0.0
page_area = 0.0
for page in pdf:
    tp = page.get_textpage()
    total_chars += tp.count_chars()
    w, h = page.get_size()
    page_area += w * h
    for obj in page.get_objects():
        if obj.type == pdfium.raw.FPDF_PAGEOBJ_IMAGE:
            l, b, r, t = obj.get_pos()
            image_area += abs(r - l) * abs(t - b)
chars_per_page = total_chars / len(pdf)
image_ratio = image_area / page_area if page_area else 0.0
# classify: see rule above. Thresholds are config-tunable (Claude's discretion).
```

### Pattern 4: Near-empty PDF → FETCH_FAILED with a reason code (criterion 2, D-06)
**What:** A non-trivial PDF that extracts as near-empty must NEVER resolve to UNCHANGED — it is FETCH_FAILED (the PDF version of the Phase 2 D-07 "empty extraction" rule). `FetchResult` gains an optional `reason_code` field (`image_only_pdf` | `extraction_failed`); the outcome stays FETCH_FAILED. No new outcome enum (the existing tri-state contract is preserved).
**When to use:** Any near-empty extraction.

### Pattern 5: PDF fixture-replay with no production-only branch (D-10)
**What:** Captured PDF bytes replay through respx exactly as HTML fixtures do today (`httpx.Response(200, content=pdf_bytes)`). Detection/extraction logic runs identically on fixtures and live snapshots — no `if fixture:` branch (carries Phase 1 D-04, proven behaviorally by `test_identical_code_path`).
**Criterion-5 fixture pair (D-10):** Use the District of Oregon's **real** superseded-vs-replacement LBR pair — the prior-year clean PDF and the current clean PDF are both published (see Open Question 1). This is a genuine version pair, not a hand-modified copy, satisfying D-10's preferred construction.

### Anti-Patterns to Avoid
- **Treating a scanned PDF as a content change or as UNCHANGED:** it is FETCH_FAILED + reason code. A scanned PDF that silently passes as "no change" is exactly the silent-failure mode Phase 2 was built to kill.
- **Using pdfplumber for prose PDFs:** its table/flow logic reflows prose and produces diff noise. Prose → pypdfium2; pdfplumber only on JSONB-flagged tabular sources.
- **Collapsing the two district source patterns into one detection rule:** a general-orders index behaves like a feed/listing, not a document. D-16 surfaced this explicitly so the planner keeps them separate.
- **Branching pipeline code on `source.ingestion_method == "pdf"`:** the adapter is selected by `adapter_ref`; `run_ingest`, `detect_change`, `store_snapshot` must stay PDF-agnostic.
- **Per-source transform/regex code for normalization:** normalization rules are a fixed vocabulary toggled by config (Phase 2 D-05 precedent) — onboarding stays config-only (SRC-06).
- **Installing an OCR engine:** out of scope (D-05). The OCR seam is a stub interface only.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| PDF text extraction | A PDF byte-stream / content-stream parser | pypdfium2 `get_textpage()` | PDF is a notoriously complex format — encodings, fonts, content operators, compression. PDFium is Google's battle-tested renderer |
| Scanned-PDF detection | Pixel-analysis / heuristic image detection | pypdfium2 `get_objects()` + `FPDF_PAGEOBJ_IMAGE` | pypdfium2 already exposes the page object model — image objects are first-class. Reinventing this means re-implementing PDF object parsing |
| Table extraction | Column-coordinate clustering of text spans | pdfplumber `extract_table()` | pdfplumber's table detection (line/edge + word-clustering strategies) is a mature, tuned subsystem. Hand-rolling produces brittle, source-specific code that violates SRC-06 |
| Unified diff of extracted text | Custom diff algorithm | `difflib` (already in `detect/diff.py`) | Already proven in Phase 1. PDF text is just text once extracted |
| HTTP conditional fetch / retry | New fetch logic for PDFs | Existing httpx pattern in `rss.py` | ETag/If-Modified-Since, timeout, error→FETCH_FAILED already implemented and tested |

**Key insight:** Phase 3 is overwhelmingly *integration*, not invention. The only genuinely novel logic is the two-axis scanned-vs-broken classifier (Pattern 3) and the index/listing source pattern (Pattern 2) — and even those are compositions of primitives the locked stack already provides. Every "hard" sub-problem (PDF parsing, table detection, diffing, conditional HTTP) is owned by a library.

## Common Pitfalls

### Pitfall 1: Scanned PDF silently read as "no change"
**What goes wrong:** A scanned/image-only PDF extracts as empty text; if the adapter hashes empty text and compares to a prior empty hash, it resolves UNCHANGED — a silent miss of every change in that document.
**Why it happens:** Treating extraction output uniformly without checking whether extraction *succeeded*.
**How to avoid:** Pattern 4 — near-empty extraction is always FETCH_FAILED with a reason code, never UNCHANGED. This is criterion 2 and the PDF analogue of Phase 2 D-07.
**Warning signs:** A PDF source with `health_status=healthy` that has never produced a snapshot; a PDF source whose snapshots all hash to the empty-content hash.

### Pitfall 2: Misclassifying a broken text layer as a scanned PDF (or vice versa)
**What goes wrong:** A PDF with a corrupt/encrypted text layer is labeled `image_only_pdf` and parked "awaiting OCR" forever — but OCR will never fix it because it is a bug. Or a genuine scan is labeled `extraction_failed` and an operator wastes time hunting a non-existent bug.
**Why it happens:** Using char-count alone — both cases have near-zero chars.
**How to avoid:** The two-axis rule (Pattern 3) — char-count MUST be combined with image-area coverage. The image-coverage axis is what disambiguates.
**Warning signs:** `image_only_pdf` sources that contain no large image objects; `extraction_failed` sources that are visually obvious scans.

### Pitfall 3: PDF text-extraction diff noise from line-wrapping, hyphenation, ligatures
**What goes wrong:** Two semantically identical PDF versions produce a noisy diff because text reflows differently — a word hyphenated across a line break (`bank-\nruptcy`), running line numbers, repeated page headers/footers, or ligature glyphs (`ﬁ`, `ﬂ`) extracted as single code points.
**Why it happens:** Raw PDF text extraction preserves layout artifacts that are not content.
**How to avoid:** `pdf_normalize()` before hashing/diffing (plan 03-02): de-hyphenate (join `word-\nword` → `wordword` when the break is mid-word), strip leading line-numbers and repeated page headers/footers, fold Unicode ligatures via NFKC normalization (`unicodedata.normalize("NFKC", text)` maps `ﬁ`→`fi`), collapse whitespace. This mirrors the Phase 1 `normalize()` discipline. Aggressiveness is config-tunable (Claude's discretion).
**Warning signs:** Diffs dominated by `-`/`+` pairs that differ only in whitespace, hyphenation, or page-furniture.

### Pitfall 4: Court PDF URL drift breaking the document-source pattern
**What goes wrong:** A court re-uploads a local-rules PDF at a new URL (filename embeds a date, e.g. `LBR.120125 clean.pdf`); the configured `feed_url` 404s; the source silently goes stale.
**Why it happens:** Court sites version PDFs by changing the filename.
**How to avoid:** A non-200 already resolves to FETCH_FAILED in the existing fetcher; Phase 2's staleness alarm (D-14, no successful fetch in N days) catches it. For document-pattern sources, prefer a *stable landing-page* URL where one exists and let the adapter resolve the current PDF link, rather than hard-coding a dated PDF URL — but this is a per-source onboarding judgment (config, not code).
**Warning signs:** A PDF source with a sudden run of FETCH_FAILED 404s.

### Pitfall 5: Listing source floods the review queue on first poll
**What goes wrong:** First poll of a general-orders index treats every existing historical order as "new" → dozens of spurious Changes into the review queue.
**Why it happens:** No baseline established before diffing the entry set.
**How to avoid:** D-17 — first poll records all existing index entries as the baseline, zero Changes. This is the Phase 1 first-fetch rule applied to the entry *set*. Already the established pattern (`detector.py`).
**Warning signs:** A burst of `detected` Changes all created at the same timestamp right after a listing source is onboarded.

### Pitfall 6: PDF byte-snapshot storage bloat
**What goes wrong:** Storing every raw PDF binary in the `snapshot.content` Text column bloats the DB; a court local-rules PDF can be megabytes.
**Why it happens:** The Snapshot model's `content` is `Text` — designed for normalized text, not binary.
**How to avoid:** Store the **normalized extracted text** in `snapshot.content` (consistent with Phase 1/2 — the snapshot is the diffed content). Binary PDF artifact retention is Claude's-discretion: keep it minimal or out-of-DB; the snapshot's job is the diff baseline, not byte archival. The planner picks a retention default.
**Warning signs:** `snapshot` table size growing far faster than text-only sources would imply.

## Runtime State Inventory

> Phase 3 is greenfield additive feature work (new adapter, new source rows), not a rename/refactor/migration. This section is included for completeness; no string-rename runtime state applies.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — no existing PDF data to migrate. New `source` rows and `snapshot`/`change` rows are created fresh by onboarding. | None |
| Live service config | None — no external service holds Phase-3 state. Court/legislative sites are external read-only sources. | None |
| OS-registered state | None — no scheduler yet (Procrastinate is Phase 4). | None |
| Secrets/env vars | None new — court/legislative sites are public, unauthenticated (Phase 2 D-04). No API keys. `ANTHROPIC_API_KEY` already configured (Phase 1). | None |
| Build artifacts | `uv add pypdfium2 pdfplumber` updates `pyproject.toml` / `uv.lock` — run `uv sync` after. pypdfium2 ships a self-contained binary wheel (no system PDF libs). | `uv sync` after add |

**Schema additions are forward-only Alembic migrations** (hand-written per the Phase 1 precedent — autogenerate omits CheckConstraints): a district `document_type` / `source_pattern` column on `source` (planner's discretion on shape) and a `pdf_provenance` flag on `change`. Both follow VARCHAR + CHECK (not native PG ENUM) so values can be extended in later phases without `ALTER TYPE`.

## Code Examples

### Extracting prose text with pypdfium2
```python
# Source: github.com/pypdfium2-team/pypdfium2 README
import pypdfium2 as pdfium

pdf = pdfium.PdfDocument(pdf_bytes)          # accepts bytes, path, or file object
pages_text = []
for page in pdf:
    textpage = page.get_textpage()
    pages_text.append(textpage.get_text_bounded())   # whole-page text
full_text = "\n".join(pages_text)
```

### Selective table extraction with pdfplumber (JSONB-flagged sources only)
```python
# Source: pdfplumber README (github.com/jsvine/pdfplumber)
import pdfplumber, io

with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
    rows = []
    for page in pdf.pages:
        for table in page.extract_tables():
            rows.extend(table)            # list[list[str|None]] — render to a stable text form for diffing
```

### Ligature / hyphenation normalization sketch (plan 03-02)
```python
# Source: Python stdlib unicodedata + difflib precedent in src/brm/detect/normalize.py
import re, unicodedata

def pdf_normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)              # folds ligatures: ﬁ→fi, ﬂ→fl
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)             # de-hyphenate mid-word line breaks
    text = re.sub(r"^\s*\d+\s+", "", text, flags=re.M)       # strip leading line numbers
    text = re.sub(r"[ \t]+", " ", text)                      # collapse intra-line whitespace
    return text.strip()
# Repeated page header/footer stripping: detect lines recurring on >N pages, drop them.
# Aggressiveness toggles live in config / per-source JSONB (Claude's discretion).
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| PyPDF2 (unmaintained) | pypdf (merged successor) / pypdfium2 | PyPDF2 merged into pypdf ~2022 | Use pypdfium2 per CLAUDE.md — do not reference PyPDF2 |
| PyMuPDF as the "fast" default | pypdfium2 for license-clean projects | Ongoing — AGPL awareness | CLAUDE.md forbids PyMuPDF here; pypdfium2 is the resale-safe choice |
| Hand-rolled scanned-PDF heuristics | Page-object model inspection (`get_objects` + image-object filter) | pypdfium2 exposes PDFium's object API | D-08 detection is a clean library-supported operation, not a heuristic |

**Deprecated/outdated:**
- PyPDF2 — unmaintained; superseded by pypdf. Neither is the project default (pypdfium2 is).
- PyMuPDF / `fitz` — explicitly forbidden by CLAUDE.md for license reasons. Do not use.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The District of Oregon's prior-year LBR clean PDF remains downloadable (a real superseded-vs-replacement pair exists for the D-10 fixture) | Open Question 1, Pattern 5 | If the prior version is removed, fall back to a hand-modified copy of the current PDF (D-10's permitted alternative) — still replays through the same adapter |
| A2 | At least one of the recommended districts publishes a genuinely **scanned/image-only** order PDF (signed standing/general orders are often scanned) | Open Question 1, D-03 | If all three districts publish only born-digital PDFs, the scanned sub-type must be sourced from a 4th district or a deliberately scanned fixture — see Open Question 1 |
| A3 | `leginfo.legislature.ca.gov` statute pages are static HTML with a stable text region (the Phase 2 HTML adapter can scrape them) | Open Question 2 | If JavaScript-rendered, the HTML adapter fails; would need re-evaluation. WebFetch indicated a legacy static page — low risk |
| A4 | `statutes.capitol.texas.gov` exposes a stable per-chapter PDF (`PR.41.pdf`, `PR.42.pdf`) suitable for the PDF document-source pattern | Open Question 2 | If only the HTML `GetStatute.aspx` view is reliable, use the HTML adapter instead — D-12 explicitly allows either |
| A5 | pypdfium2 `obj.type == FPDF_PAGEOBJ_IMAGE` reliably surfaces scanned-page images across court-PDF producers | Pattern 3 | If some scanners embed images as form XObjects nested differently, image-area measurement may under-count — mitigate by also treating "near-zero chars + near-zero detectable objects of any kind" conservatively as `extraction_failed` and let an operator triage |
| A6 | The CA EJ-156 PDF is genuinely table-structured (a good pdfplumber `tabular:true` exemplar) | SRC-04, D-13 | If it is prose-with-numbers rather than ruled tables, pypdfium2 prose extraction suffices — pdfplumber simply is not flagged for it. Low risk; D-13 is selective by design |

## Open Questions

1. **Which 3 districts, and where does the scanned/image-only PDF come from? (D-01, D-03, D-09, D-10)**
   - **What we know:** Live-site investigation gives strong, verified candidates:
     - **District of Oregon (orb.uscourts.gov)** — *document pattern.* Publishes the current LBR clean PDF, a redline PDF, a summary-of-changes PDF, **and the prior-year (12/1/24) LBR PDF**. This is a real superseded-vs-replacement pair → ideal D-10 criterion-5 fixture. LBRs update annually (effective Dec 1) with public-comment cycles — verifiable rule-change activity. Strong text-layer clean-PDF candidate. `[VERIFIED: WebFetch orb.uscourts.gov/rules]`
     - **Central District of California (cacb.uscourts.gov)** — *index/listing pattern.* General Orders published as a dated table (Order # | Title | Date Posted) of individual PDFs, recent entries through 05/2026 (GO 26-01). CACB is among the highest-filing-volume bankruptcy districts. Also publishes a single canonical complete-LBR PDF. `[VERIFIED: WebFetch cacb.uscourts.gov/general-orders]`
     - **Western District of Texas (txwb.uscourts.gov)** — *index/listing pattern.* Standing Orders published as a dated table of individual PDFs (recent: 26-02 04/2026). Adds a third state. `[VERIFIED: WebFetch txwb.uscourts.gov/standing-orders-index]`
   - **What's unclear:** Which specific district provides the **scanned/image-only** PDF (D-03's required third sub-type). Signed standing/general orders are *often* scanned (a judge's wet-ink signature), but WebFetch could not confirm the byte-level format of any specific order PDF — only the listing structure. Born-digital signed PDFs are also common.
   - **Recommendation:** During plan 03-03 execution, download 5-10 candidate order PDFs from CACB and TXWB and run the Pattern-3 classifier on each to *empirically* find a real scanned one. A signed general/standing order is the most likely scanned candidate. If none of the three districts yields a genuine scan, either (a) add a 4th district known for scanned orders, or (b) for the criterion-1 scanned-detection proof, use a deliberately-scanned fixture (a real court order re-scanned) that still replays through the unchanged adapter — the *detection* path is what criterion 1 proves, and a fixture exercises it identically to a live scan. The pilot for criterion 5 (D-09) should be the **Oregon LBR document source** (real superseded/replacement pair already in hand) — general orders were noted as likeliest-active but Oregon's annual LBR cycle is equally verifiable and gives a cleaner deterministic pair.

2. **Per-state exemption ingestion method and Source-row granularity (D-12, D-15)**
   - **What we know — recommended per launch state:**
     - **Oregon:** Exemptions in ORS Chapter 18 (esp. ORS 18.345 personal property, ORS 18.395 homestead). Official source: `oregonlegislature.gov/bills_laws/ors/ors018.html` — an HTML page. → **HTML adapter** (D-12). Exemptions cluster in ORS 18 → likely **one Source row** for the relevant ORS-18 region (or a small handful if the homestead/personal-property sections sit on separate pages). `[CITED: oregonlegislature.gov]`
     - **California:** Exemptions in Code of Civil Procedure §§ 703.140 and 704.x. Official source: `leginfo.legislature.ca.gov` — confirmed static HTML, statute text in a stable "Code Text" region → **HTML adapter** (D-12). CCP scatters exemptions across several § 704 sections → likely **several Source rows** (one per key section, or per leginfo page). **Plus** the Judicial Council **EJ-156 PDF** (`courts.ca.gov/.../ej156.pdf`) carries the triennially-adjusted §703.140(b) dollar amounts as a **table** → a **PDF document source with JSONB `tabular:true`** (the pdfplumber exemplar for D-13). `[VERIFIED: WebFetch leginfo.legislature.ca.gov]` `[CITED: courts.ca.gov EJ-156]`
     - **Texas:** Exemptions in Property Code Chapters 41 (homestead/land) and 42 (personal property). Official source `statutes.capitol.texas.gov` exposes both a per-chapter **PDF** (`PR.41.pdf`, `PR.42.pdf`) and an HTML `GetStatute.aspx` view. → **PDF adapter** for the stable chapter PDFs (or HTML — D-12 permits either); likely **two Source rows** (Ch. 41 and Ch. 42). `[CITED: statutes.capitol.texas.gov]`
   - **What's unclear:** Exact Source-row count per state (one vs several) — depends on how each legislative site paginates the relevant sections; resolve during plan 03-04 by inspecting the live pages. Onboarding is config-only regardless (SRC-06), so the count is not architecturally load-bearing.
   - **Recommendation:** Onboard CA via the HTML adapter for §§703.140/704 *and* the EJ-156 PDF as a tabular PDF source (this conveniently also exercises D-13's pdfplumber path within SRC-04). Onboard OR via HTML. Onboard TX via the PDF adapter on the chapter PDFs. Per-source compliance record (robots.txt/ToS — Phase 2 D-03) must be filled for each — court and `.gov` legislative sites are public infrastructure; apply the polite-scraping ceiling (Phase 2 D-08).

3. **`FetchResult` reason-code field shape**
   - **What we know:** D-06/D-08 require a reason code on FETCH_FAILED without a new outcome enum. `FetchResult` currently has an `error` free-text field.
   - **What's unclear:** Whether to add a typed `reason_code` field or overload `error`.
   - **Recommendation:** Add an optional `reason_code: str | None` field to `FetchResult` (a small VARCHAR-style vocabulary: `image_only_pdf`, `extraction_failed`, plus existing implicit ones). It must be machine-readable for the source-health view triage — overloading free-text `error` would force string parsing. Planner decides; this is a minor dataclass extension.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| pypdfium2 | INGEST-03 PDF extraction | ✗ (not yet installed) | 5.8.0 on PyPI | None needed — `uv add`; ships self-contained binary wheel |
| pdfplumber | D-13 selective table extraction | ✗ (not yet installed) | 0.11.9 on PyPI | None needed — `uv add` |
| httpx | PDF fetch | ✓ | 0.28.1 | — |
| selectolax | index/listing HTML parse | ✓ | (in use) | — |
| PostgreSQL 16 | source/snapshot/change rows | ✓ (WSL native per user memory) | 16 | — |
| Court / legislative sites (orb, cacb, txwb, leginfo, oregonlegislature, capitol.texas.gov) | SRC-03/SRC-04 onboarding + live fetch | ✓ (public, unauthenticated) | — | Fixture-replay covers offline testing; live fetch needed only for capturing fixtures |

**Missing dependencies with no fallback:** none — the two missing packages install cleanly via `uv add`.
**Missing dependencies with fallback:** none blocking.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio (+ respx for HTTP mocking) |
| Config file | `tests/conftest.py` (SAVEPOINT-rollback `db_session`, `mock_http` respx fixture, Windows SelectorEventLoop patch) |
| Quick run command | `uv run pytest tests/test_pdf_adapter.py -x` |
| Full suite command | `uv run pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INGEST-03 | Clean text-layer PDF extracts → CHANGED with normalized text | unit/integration | `uv run pytest tests/test_pdf_adapter.py::test_text_layer_pdf_extracts -x` | ❌ Wave 0 |
| INGEST-03 / D-08 | Scanned PDF → FETCH_FAILED reason=`image_only_pdf` | unit | `uv run pytest tests/test_pdf_adapter.py::test_scanned_pdf_image_only -x` | ❌ Wave 0 |
| INGEST-03 / D-08 | Broken-text-layer PDF → FETCH_FAILED reason=`extraction_failed` | unit | `uv run pytest tests/test_pdf_adapter.py::test_broken_text_layer -x` | ❌ Wave 0 |
| INGEST-03 (crit 2) | Near-empty PDF → FETCH_FAILED, never UNCHANGED | unit | `uv run pytest tests/test_pdf_adapter.py::test_near_empty_not_unchanged -x` | ❌ Wave 0 |
| INGEST-03 (crit 2) | Normalization removes hyphenation/line-numbers/ligature noise | unit | `uv run pytest tests/test_pdf_normalize.py -x` | ❌ Wave 0 |
| D-13 | Table-heavy PDF (EJ-156-style) extracts cleanly via pdfplumber | unit | `uv run pytest tests/test_pdf_adapter.py::test_tabular_pdf -x` | ❌ Wave 0 |
| SRC-03 / D-16 | Document-pattern source diffs canonical PDF; listing-pattern detects new entries | integration | `uv run pytest tests/test_pdf_adapter.py::test_document_vs_listing -x` | ❌ Wave 0 |
| SRC-03 / D-17 | Listing source first poll = silent baseline, zero Changes | integration | `uv run pytest tests/test_pdf_adapter.py::test_listing_first_poll_baseline -x` | ❌ Wave 0 |
| SRC-03 / D-18 | Brand-new order → `detected` Change, addition diff | integration | `uv run pytest tests/test_pdf_adapter.py::test_new_order_addition -x` | ❌ Wave 0 |
| SRC-03/04 | New PDF/state source onboards as config-only registry row, no code change | integration | `uv run pytest tests/test_source_onboarding.py -x` | ❌ Wave 0 |
| crit 5 / D-10 | Oregon LBR superseded→replacement pair replays through same adapter → review queue | integration | `uv run pytest tests/test_pdf_fixture_replay.py -x` | ❌ Wave 0 |
| D-11 | PDF-sourced Change carries the PDF-provenance flag | unit | `uv run pytest tests/test_pdf_adapter.py::test_pdf_provenance_flag -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_pdf_adapter.py tests/test_pdf_normalize.py -x`
- **Per wave merge:** `uv run pytest`
- **Phase gate:** Full suite green before `/gsd:verify-work`.

### Wave 0 Gaps
- [ ] `tests/test_pdf_adapter.py` — covers INGEST-03, D-08, D-13, D-16, D-17, D-18, D-11
- [ ] `tests/test_pdf_normalize.py` — covers de-hyphenation / line-number / ligature normalization
- [ ] `tests/test_pdf_fixture_replay.py` — covers criterion 5 / D-10 end-to-end
- [ ] `tests/test_source_onboarding.py` — covers config-only onboarding (SRC-06) for PDF + state sources
- [ ] `tests/fixtures/pdf/` — captured PDF fixtures: clean text-layer, scanned/image-only, broken-text-layer, table-heavy, and the Oregon superseded/replacement change pair
- [ ] Framework install: `uv add pypdfium2 pdfplumber` (the only new dependencies)

## Security Domain

> `security_enforcement` is not present in `.planning/config.json` → treat as enabled.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Phase 3 fetches public, unauthenticated court/legislative sources only (Phase 2 D-04). No credentials introduced |
| V3 Session Management | no | No new sessions; pull/review API auth is Phase 1 |
| V4 Access Control | no | No new access surface in this phase |
| V5 Input Validation | **yes** | PDF bytes from external court sites are untrusted input — see threat table |
| V6 Cryptography | no | No crypto introduced; SHA-256 content hashing is non-secret integrity, unchanged from Phase 1 |
| V12 Files & Resources | **yes** | PDF parsing of remote files — resource-exhaustion and malformed-file handling |

### Known Threat Patterns for the PDF-ingestion stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malformed / malicious PDF crashes or hangs the parser | Denial of Service | pypdfium2 wraps PDFium (Google's hardened renderer — far safer than pure-Python parsers); wrap extraction in try/except → on parse failure resolve FETCH_FAILED reason=`extraction_failed`, never crash the worker. Apply a fetch timeout (already in `rss.py`) and a max-PDF-size ceiling before parsing |
| Oversized PDF exhausts memory / disk | Denial of Service | Enforce a max content-length on the httpx fetch; reject (FETCH_FAILED) PDFs above a configurable size ceiling before loading into pypdfium2 |
| PDF with embedded JavaScript / external references | Tampering / Info Disclosure | Text extraction does not execute PDF JavaScript; pypdfium2 `get_textpage()` only reads text objects. Do not render or follow embedded actions |
| Decompression bomb (deeply nested / highly compressed streams) | Denial of Service | Size ceiling + page-count ceiling; PDFium has internal limits, but bound page iteration in the adapter as defense-in-depth |
| Server-Side Request Forgery via court-supplied PDF URLs | SSRF | Source `feed_url` values are operator-curated registry entries, not user input (SRC-06 onboarding is a controlled config operation) — arbitrary-URL monitoring is explicitly out of scope (REQUIREMENTS.md). For the index/listing pattern, validate that resolved order-PDF links stay on the same court host before fetching |

## Sources

### Primary (HIGH confidence)
- `CLAUDE.md` — locked stack: pypdfium2 default, pdfplumber selective, httpx, difflib, PostgreSQL 16, SQLAlchemy/Alembic, PyMuPDF forbidden, no OCR engine
- `github.com/pypdfium2-team/pypdfium2` — pypdfium2 API (`get_textpage`, `count_chars`, `get_text_range`, `get_objects`, `FPDF_PAGEOBJ_IMAGE`); Apache-2.0/BSD-3-Clause license — `[VERIFIED: WebFetch]`
- PyPI registry — pypdfium2 5.8.0, pdfplumber 0.11.9, httpx 0.28.1 all current — `[VERIFIED: pip index versions]`
- Existing codebase — `src/brm/ingest/adapter.py` (SourceAdapter Protocol), `rss.py` (adapter pattern + httpx fetch), `pipeline.py` (run_ingest shared orchestrator), `detect/detector.py` (first-fetch baseline + hash gate), `detect/normalize.py`, `models/{source,snapshot,change}.py`, `tests/conftest.py`, `tests/test_fixture_replay.py`
- `orb.uscourts.gov/rules` — Oregon LBR clean + redline + prior-year PDFs — `[VERIFIED: WebFetch]`
- `cacb.uscourts.gov/general-orders` and `/local-rules` — CACB general-orders dated index + canonical LBR PDF — `[VERIFIED: WebFetch]`
- `txwb.uscourts.gov/standing-orders-index` — Western Texas standing-orders dated index — `[VERIFIED: WebFetch]`
- `leginfo.legislature.ca.gov` — CCP 703.140 static HTML statute page with stable "Code Text" region — `[VERIFIED: WebFetch]`

### Secondary (MEDIUM confidence)
- `oregonlegislature.gov/bills_laws/ors/ors018.html` — Oregon ORS Chapter 18 (exemptions) official HTML — `[CITED]`
- `statutes.capitol.texas.gov` — Texas Property Code Ch. 41/42 PDF + HTML — `[CITED]`
- `courts.ca.gov/.../ej156.pdf` — California EJ-156 exemption-amounts PDF (table-structured, triennial adjustment effective 04/2025) — `[CITED]`

### Tertiary (LOW confidence)
- General web search on bankruptcy-court order publishing formats — used only to identify candidate districts; all candidates were then verified via WebFetch above

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — fully locked by CLAUDE.md, versions verified on PyPI, API confirmed against the official pypdfium2 repo
- Architecture: HIGH — Phase 3 reuses the proven Phase 1/2 `SourceAdapter` + `run_ingest` + fixture-replay patterns; the only novel logic (two-axis scanned detection, two source patterns) is composed of confirmed library primitives
- District/state sources: MEDIUM-HIGH — three districts and three states verified against live sites with PDF URLs and structures; the one open item is empirically confirming a genuine scanned/image-only PDF (Open Question 1) — deferred to plan-03-03 execution by design
- Pitfalls: HIGH — drawn directly from the carried-forward Phase 1/2 silent-failure discipline plus well-documented PDF-extraction artifacts

**Research date:** 2026-05-22
**Valid until:** 2026-06-21 (30 days — stable stack; court/legislative URLs may drift, re-verify PDF URLs at onboarding time)
