# Phase 3: PDF Ingestion & District Coverage - Context

**Gathered:** 2026-05-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Widen ingestion to **PDF source documents** and onboard the first **~3 federal bankruptcy court districts** plus their **launch-state exemption sources**.

This phase adds: a PDF fetcher adapter behind the existing `SourceAdapter` seam — text-layer-vs-scanned detection, OCR routing (engine stubbed), and extraction validation; PDF-specific text normalization (de-hyphenation, line-number/header stripping, ligatures, tabular data) so extracted text diffs cleanly; the initial ~3-district source tranche covering local rules, standing orders, and general orders with every known publication channel documented; and state exemption-statute sources for the launch states those districts sit in. It closes by flowing a real PDF-based district rule change end-to-end into the review queue (criterion 5).

This phase does NOT add: a working OCR engine (image-only PDFs are reliably *detected and escalated* — actual OCR is a deferred stub behind an engine-agnostic seam), adaptive/cadence-driven polling (Phase 4 — INGEST-06), the full 3-axis AI taxonomy or structured extraction of dollar amounts/fees/form numbers (Phase 5 — AI-02/AI-04), effective-date scheduling (Phase 6), or any new ingestion adapter for state sources (they reuse the Phase 2 HTML and Phase 3 PDF adapters).

Covers **INGEST-03** (PDF extraction), **SRC-03** (~3-district tranche), **SRC-04** (launch-state exemption rules).

</domain>

<decisions>
## Implementation Decisions

### District Tranche Selection
- **D-01:** The *specific* 3 districts are a **research task** — the selection *criteria* are locked here; researcher picks the actual districts against live court sites. This resolves the STATE.md open decision ("initial district source tranche selection is an open decision to be made before Phase 3") by locking criteria rather than naming districts blind.
- **D-02:** Selection criteria, all weighted: **adapter-format variety, clean PDF publishing, rule-change activity, filing volume, and fixture cleanliness/determinism** (the chosen sources must reproduce as deterministic, replayable fixtures).
- **D-03:** "Format variety" means **PDF-internal variety**, not cross-channel — all 3 districts are PDF-centric, chosen to span PDF *sub-types*: a clean text-layer PDF, a scanned/image-only PDF (exercises the OCR-detection/escalation path), and a table-heavy PDF. Variety lives inside the PDF pipeline, which is what this phase is built to prove. (Cross-channel variety was rejected — Phase 1 already proved the feed adapter, Phase 2 the HTML adapter.)
- **D-04:** Three **distinct states is a soft tie-breaker only** — when two candidate districts score equally on the PDF/activity criteria, prefer the one that adds a new state (widens SRC-04 proof). The PDF/activity criteria win outright; state spread never overrides them.

### OCR Strategy
- **D-05:** Phase 3 is **detect-and-escalate, not run-OCR.** The adapter *reliably detects* image-only PDFs and routes them to operator escalation; the OCR engine itself is a **deferred stub**. Criterion 1's "routing image-only PDFs to OCR" is satisfied as *routing*, not *extraction*. (Running real OCR now was rejected — keeps the OCR-accuracy risk and dependency out of this phase.)
- **D-06:** A detected image-only PDF is recorded using the **existing FETCH_FAILED tri-state outcome** (Phase 1/2) stamped with a **reason code** (e.g. `image_only_pdf`). No new outcome enum — the reason field carries the nuance, the locked tri-state contract is preserved.
- **D-07:** The OCR seam is **engine-agnostic** — a generic "image PDF → text" interface, with **no engine preference recorded**. Tesseract/ocrmypdf vs Claude vision vs cloud OCR is decided when OCR is actually built, informed by what the scanned district sources look like.
- **D-08:** The adapter **distinguishes a scanned PDF from a broken text-layer PDF** — both extract as near-empty, but: near-empty + image-based page structure → an `image_only_pdf` reason (awaiting OCR, *expected*); near-empty + the PDF *does* carry a text layer → a genuine extraction-failure reason (a *bug* to fix). Same FETCH_FAILED outcome, different reason codes — operators triage them differently.

### PDF Pilot Demo (criterion 5)
- **D-09:** The pilot document **type** is a **research task** — the pilot is a district PDF from one of the tranche districts; researcher picks whichever document type (general order / local rules / standing order) has a *verifiable real change* to demonstrate against. General orders were noted as the likeliest to have recent activity, but the choice follows the evidence.
- **D-10:** The changed/unchanged **PDF fixture pair construction is a research task** — locked constraint: a deterministic PDF fixture pair MUST exist and MUST replay through the same adapter as live ingestion (no production-only branch — carries forward Phase 1 D-04 / Phase 2 D-17). Researcher chooses a real superseded-vs-replacement version pair vs a hand-modified copy based on what the chosen source actually offers.
- **D-11:** A PDF-sourced change carries a **PDF-provenance flag on the review-queue item** — a small signal that the change came from PDF extraction (and whether OCR was involved), so the reviewer reads the diff with extra care. Reuses Phase 1's queue UI with one additive field/badge; serves the high-stakes accuracy constraint.

### State Exemption Sources (SRC-04)
- **D-12:** State exemption sources **reuse existing adapters** — the Phase 2 HTML adapter for legislative HTML pages, the Phase 3 PDF adapter for statute PDFs. **No new adapter code.** The actual ingestion method per launch state is a research task once the real statute pages are inspected.
- **D-13:** **pdfplumber is added selectively** — only for sources whose content is genuinely tabular (so a one-cell exemption-amount change diffs cleanly instead of producing reflowed-text noise). **pypdfium2 stays the default** for prose PDFs. This matches CLAUDE.md ("pdfplumber — add only for specific sources … not the default").
- **D-14:** Phase 3's exemption scope is **ingest + detect text changes only** — detect when the statute text changes, *including* when a dollar amount inside it changes, as a text diff. Parsing the amount out as a structured value is **Phase 5 (AI-04)** — not pulled forward.
- **D-15:** Exemption-statute **Source-row granularity is a research task** — a launch state may need one or several Source rows (states scatter exemptions across multiple code sections). Researcher determines the row set per state from the real statutes; onboarding stays a registry/config operation regardless (SRC-06).

### Document Taxonomy Within Districts
- **D-16:** District sources follow **two distinct source patterns**: a **"document" source** (local rules — one canonical PDF, diffed for amendments) and an **"index/listing" source** (general/standing orders — detect newly-appeared entries on a court index page, then ingest each new order PDF). Detection treats the two patterns differently — this matches how courts actually publish. (A uniform "every doc is its own Source" model and a uniform "everything is a listing" model were both rejected.)
- **D-17:** When an **index/listing source is first onboarded**, the first poll **records all existing index entries as the starting baseline — zero Change records, nothing into the review queue.** Only orders appearing *after* onboarding become Changes. Mirrors Phase 1's first-fetch-is-baseline rule; prevents a historical-backlog flood of the review queue.
- **D-18:** A brand-new general/standing order (no prior version) becomes a `detected` Change with a full-text "addition" diff and flows through the existing Phase 1 detect → AI-summary → review-queue pipeline unchanged.

### Claude's Discretion
- **District/PDF/state research tasks (D-01, D-09, D-10, D-12, D-15):** the actual 3 districts, the pilot document type, the fixture-pair construction, the per-state ingestion method, and the per-state Source-row set — all delegated to the phase researcher against the locked constraints.
- **Registry/schema shape — delegated to the planner:** (a) how district document type sits in the registry — reuse the existing freeform `layer` field with one Source row per (district × document-type), or add a dedicated `document_type` column; (b) where the document-vs-listing pattern distinction lives — an explicit `source_pattern` field on the Source row, or implicit in the `adapter_ref`. Locked constraints: document type and source pattern must be **registry values, not code** (onboarding stays config-only per SRC-06), and both patterns are first-class. The Phase 1 precedent (VARCHAR + CHECK over native PG ENUM, so taxonomy values can be added without `ALTER TYPE` migrations) applies to any new classifying column.
- **Tuning thresholds:** the near-empty extraction threshold (chars/page, image-coverage ratio) for distinguishing scanned from broken text-layer PDFs (D-08), the normalization aggressiveness for de-hyphenation/line-number/header stripping, and snapshot storage/retention for binary PDF artifacts — sensible defaults, per-source-overridable config where cheap.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project scope & requirements
- `.planning/PROJECT.md` — project definition, core value, constraints (API-first, no shared DB, architect-for-productization, accuracy/human-review).
- `.planning/REQUIREMENTS.md` — v1 requirements; Phase 3 covers **INGEST-03** (PDF text extraction), **SRC-03** (~3-district tranche — local rules, standing orders, general orders), **SRC-04** (launch-state exemption rules).
- `.planning/ROADMAP.md` § "Phase 3: PDF Ingestion & District Coverage" — goal, the 5 success criteria, and the 4 pre-defined plan slices (03-01 PDF fetcher adapter, 03-02 PDF normalization, 03-03 district tranche onboarding, 03-04 launch-state exemption onboarding).
- `.planning/STATE.md` — Blockers/Concerns: "initial district source tranche selection is an open decision to be made before Phase 3" (resolved by D-01/D-02 — criteria locked, selection delegated to research); "Phase 2/3 need phase-level research: actual court URLs, feed structures, and PDF layouts" (this phase's research scope).

### Prior phase context (build directly on these)
- `.planning/phases/01-end-to-end-feed-slice/01-CONTEXT.md` — Phase 1 decisions carried forward: the `SourceAdapter` seam, tri-state fetch outcome, fixture-replay validation with no production-only branch (D-03/D-04 → D-10 here), the detect → AI-summary → review-queue pipeline that Phase 3's PDF changes reuse unchanged (D-18), and the first-fetch-is-baseline rule that D-17 mirrors for listing sources.
- `.planning/phases/02-html-scraping-source-health/02-CONTEXT.md` — Phase 2 decisions carried forward: the per-source compliance record (robots.txt / ToS / crawl-delay — applies to district PDF sites too), public-unauthenticated-sources-only / PACER excluded (D-04 there), JSONB extraction-config on the Source row + config-only onboarding (SRC-06), the "empty extraction → FETCH_FAILED, never UNCHANGED" rule (D-07 there) that Phase 3 success criterion 2 is the PDF version of, and the HTML adapter that Phase 3 state exemption sources reuse (D-12 here).

### Technology stack (locked — do not re-litigate)
- `CLAUDE.md` — full recommended stack. Phase 3 relevant: Python 3.12, **pypdfium2** (default PDF text extraction — Apache-2.0/BSD-3, resale-license-clean; PyMuPDF's AGPL is explicitly forbidden), **pdfplumber** (table-aware extraction — *selective* use only, per D-13), **httpx** (async fetch — PDFs included), `difflib` (cheap diff pre-filter), PostgreSQL 16 + JSONB, SQLAlchemy 2.x + Alembic (migration for any new Source columns), **Sentry** (error monitoring — load-bearing for the "silently broken scraper / near-empty PDF" pitfall), polite-scraping guidance (per-domain rate limiting, descriptive User-Agent — court sites are government infrastructure). CLAUDE.md locks **no OCR engine** — consistent with D-05/D-07's deferred, engine-agnostic stub.

*No external ADRs or design specs exist — requirements and decisions are fully captured in PROJECT.md, REQUIREMENTS.md, ROADMAP.md, STATE.md, CLAUDE.md, 01-CONTEXT.md, 02-CONTEXT.md, and the decisions above.*

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/brm/models/source.py` — the `Source` registry model. `ingestion_method` already accepts `"pdf"` (documented in the model docstring); `feed_url`, `adapter_ref`, `last_etag`/`last_modified_http`/`last_content_hash`, and the `health_status` CHECK constraint all carry forward. Phase 3 extends this model via an Alembic migration for any district-document-type / source-pattern field (planner's discretion per D-16 discretion note) and any PDF-extraction config (JSONB, following the Phase 2 extraction-config pattern).
- `src/brm/lifecycle.py` — `ALLOWED_TRANSITIONS` change-lifecycle state machine and `HEALTH_STATUSES = {"unknown", "healthy", "failed"}`. Phase 3 reuses the lifecycle unchanged; PDF-sourced changes flow `detected → processed → in_review → verified` exactly like feed/HTML changes (D-18).
- `src/brm/models/` — `Source`, `Snapshot`, `Change` domain models. The append-only `Snapshot` store holds the captured PDF artifact / extracted text; the `Change` model carries the PDF-provenance flag (D-11).
- `src/brm/config.py` — `pydantic-settings` config singleton; new PDF tunables (near-empty thresholds, normalization toggles) and any per-source-overridable defaults live here or in the per-source JSONB config.

### Established Patterns
- **`SourceAdapter` seam** (Phase 1 plan 01-02) — the PDF fetcher is a *new adapter behind this existing seam*, not a new fetch layer. State exemption sources reuse the existing HTML/PDF adapters (D-12).
- **Tri-state fetch outcome** (CHANGED / UNCHANGED / FETCH_FAILED) — Phase 3 reuses it unchanged; image-only PDFs and near-empty extractions resolve to FETCH_FAILED with a *reason code* (D-06, D-08), not a new outcome value.
- **VARCHAR + CHECK over native PG ENUM** (Phase 1, recorded in STATE.md decisions) — any new classifying column (document type, source pattern) follows this so taxonomy values can be added in later phases without `ALTER TYPE` migrations.
- **Fixture-replay testing with no production-only branch** (Phase 1 D-03/D-04, Phase 2 D-17) — Phase 3 reuses this exactly (D-10); PDF detection/extraction must run identically on fixtures and live snapshots.
- **First-fetch-is-baseline** — Phase 1 establishes that the first snapshot is a baseline with no diff; D-17 applies the same rule to an index/listing source's first poll.

### Integration Points
- The PDF adapter plugs into the existing `SourceAdapter` interface; the shared fetch→detect pipeline orchestrator (Phase 1 plan 01-03) routes PDF sources through the same detection/diff → AI-summary → review-queue path as feed and HTML sources (D-18).
- The review-queue UI (Phase 1 plan 01-05) gains one additive field/badge for the PDF-provenance flag (D-11) — no structural change to the queue.
- Image-only-PDF escalation surfaces through the Phase 2 source-health read view + Sentry (the `image_only_pdf` reason code is a triage signal there).

</code_context>

<specifics>
## Specific Ideas

- The phase's organizing principle: **prove the PDF pipeline, not OCR.** Variety is deliberately PDF-*internal* (D-03) — text-layer / scanned / table-heavy — so the tranche stress-tests PDF extraction itself rather than re-testing the already-proven feed and HTML adapters.
- A scanned PDF is **not a failure** — it is "can't process *yet*." D-06/D-08 keep that distinction explicit via reason codes so an `image_only_pdf` source (legitimately awaiting OCR) is never confused with a genuinely broken extraction. The OCR seam (D-07) is the clean activation point when OCR is built.
- The two-source-pattern model (D-16) was surfaced explicitly so the planner does not collapse "diff one canonical local-rules PDF" and "detect new general orders on an index" into a single detection rule — they are structurally different and a court index of general orders behaves like a listing/feed, not a document.
- The pilot source (D-09) is deliberately chosen for a *verifiable real change* so criterion 5 is a genuine end-to-end demo, not a contrived one — consistent with the Phase 1 (FRBP feed) and Phase 2 (overlapping rulemaking page) pilot-selection philosophy.

</specifics>

<deferred>
## Deferred Ideas

- **A working OCR engine** — Phase 3 detects and escalates image-only PDFs behind an engine-agnostic seam (D-05/D-07); building the actual OCR engine (Tesseract/ocrmypdf vs Claude vision vs cloud OCR) is a later-milestone task driven by what the real scanned district sources look like.
- **Structured extraction of exemption dollar amounts / fees / form numbers** — Phase 3 detects exemption changes as *text* diffs (D-14); parsing amounts into validated structured fields is Phase 5 (AI-04).
- **Adaptive polling cadence** — Phase 3 onboards district/state sources but does not schedule them; cadence-driven unattended polling is Phase 4 (INGEST-06).
- **Full ~90-district and full 50-state coverage** — Phase 3 is the initial ~3-district tranche and its launch states only; broad coverage is v2 (COV-01/COV-02 in REQUIREMENTS.md).
- **PACER / login-gated court sources** — remain excluded from v1 (Phase 2 D-04); if a district publishes only behind PACER, that document type is out of scope for the v1 tranche.

None of the discussion strayed outside the Phase 3 domain — these are sequencing notes, not scope creep.

</deferred>

---

*Phase: 3-PDF Ingestion & District Coverage*
*Context gathered: 2026-05-22*
