# Phase 1: End-to-End Feed Slice - Context

**Gathered:** 2026-05-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Prove the whole pipeline with **one feed-backed national source**. A single RSS source flows end-to-end: source registry → fetch (tri-state outcome + versioned snapshot) → hash-gated change detection + textual diff → AI plain-language summary → human review queue (approve/edit/reject) → pull delivery API for verified changes.

This phase establishes the vertical slice. It does NOT widen source coverage (HTML scraping, PDF, more districts/states) or deepen individual stages (adaptive cadence, full 3-axis taxonomy, structured extraction, effective-date scheduler, temporal API) — those are Phases 2–8.

</domain>

<decisions>
## Implementation Decisions

### Seed Source
- **D-01:** The slice is seeded with the **Federal Rules of Bankruptcy Procedure (FRBP)** rule family — not the Bankruptcy Code (Title 11) or Official Forms. Rationale: the uscourts.gov rulemaking area is the most genuinely feed-shaped national source, and rule-text changes are exactly the human-review tier this slice is built to prove. (Code changes rarely and is hard to point a feed at; Form changes are the auto-publish tier and less representative.)
- **D-02:** The exact FRBP feed URL/endpoint is a research task — researcher should identify the most reliable real RSS/Atom feed for FRBP rulemaking on uscourts.gov (e.g. a "Pending Rules & Forms Amendments" / rulemaking news feed). The *layer choice* (FRBP) is locked; the *specific feed* is for research to confirm.

### Slice Validation Strategy
- **D-03:** The slice is proven via **fixture replay**: capture a real FRBP feed snapshot, then a modified copy, and run change detection against the pair. This is deterministic, demoable at any time (FRBP amendments land ~once a year, typically effective Dec 1, so the live feed will be quiet during the build), and doubles as the regression-test fixture.
- **D-04:** Live polling against the real feed still runs **in parallel** with the fixture path — fixtures are for demonstrating/testing the change path, not a replacement for real ingestion. Detection logic must run identically on fixture and live snapshots (no production-only code branch, no synthetic-injection backdoor).

### AI Summary Shape
- **D-05:** The AI summary is **structured fields**, not a free-form prose paragraph. Required structure:
  - A one-line **headline**.
  - A 1–3-sentence block answering **"What changed / Where / To whom / For what cases"**.
- **D-06:** Depth is **concise** — 1–3 sentences. The reviewer reads the verbatim diff for detail; the summary is the gist only. Keeps cost, latency, and hallucination surface low.
- **D-07:** Prompt no-go constraints (hard guardrails in the summary prompt):
  - Do NOT speculate about practical impact beyond the explicit text of the rule.
  - Do NOT phrase output as advice (no "this is what you should do" framing).
- **D-08:** Every summary carries the **"informational / not legal advice"** label (requirement AI-06).
- **D-09:** The structured summary is stored as JSONB. The review UI renders the headline in the queue list with the detail block expandable per row (queue scannability + detail on demand).

### Reviewer Actions
- **D-10:** The review queue supports **approve / edit / reject** — all three (full ROUTE-04). Reject marks a detected change as not-a-real-change / noise (e.g. feed re-publish, boilerplate) so it never reaches the pull API and does not sit pending forever.
- **D-11:** "Edit" in this slice means correcting the **AI summary** (the only AI output in Phase 1 — classification and structured extraction arrive in Phase 5).
- **D-12:** The **effective date** is entered by the reviewer during review. The field is nullable until then; the reviewer (reading the diff/source) is the authoritative source of truth for it in Phase 1. This satisfies EFF-01 (detected date vs effective date as separate fields) honestly given that AI extraction is not until Phase 5.

### Claude's Discretion
- The specific FRBP feed URL (per D-02) — researcher selects the most reliable real feed.
- Review UI access model (open internal tool vs login-gated) and reviewer-identity capture were NOT discussed — planner/researcher may choose a sensible minimal default for an internal-only v1 tool; full reviewer attribution / audit trail is explicitly Phase 8 (AUDIT-02). Do not over-build auth here.
- API response shape, snapshot retention policy, and diff-rendering library details — standard approaches per the locked stack in CLAUDE.md.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project scope & requirements
- `.planning/PROJECT.md` — project definition, core value, constraints (API-first, no shared DB, architect-for-productization, accuracy/human-review).
- `.planning/REQUIREMENTS.md` — v1 requirements; Phase 1 covers SRC-01, SRC-02, INGEST-01, INGEST-04, INGEST-05, DETECT-01, DETECT-02, AI-01, AI-03, AI-06, ROUTE-03, ROUTE-04, EFF-01, EFF-02, API-01, API-07.
- `.planning/ROADMAP.md` § "Phase 1: End-to-End Feed Slice" — goal, success criteria, and the 5 pre-defined plan slices (01-01 … 01-05).

### Technology stack (locked — do not re-litigate)
- `CLAUDE.md` — full recommended stack and rationale. Phase 1 relevant: Python 3.12, FastAPI, Uvicorn, PostgreSQL 16, SQLAlchemy 2.x + Alembic, Pydantic 2.x, Anthropic Python SDK (direct, no agent framework), httpx, feedparser (RSS), `difflib` (cheap diff pre-filter), React + Vite + TypeScript + shadcn/ui + TanStack Query + `react-diff-viewer-continued` for the review UI, uv + Ruff + pytest. Multi-tenancy seam: nullable `tenant_id` column on tenant-scoped tables from day one.

*No external ADRs or design specs exist yet — requirements and decisions are fully captured in PROJECT.md, REQUIREMENTS.md, ROADMAP.md, CLAUDE.md, and the decisions above.*

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- None — this is the first phase of a greenfield project. No application code exists yet (`C:\data\cc` contains only `.planning/`, `.claude/`, and `CLAUDE.md`).

### Established Patterns
- None established yet. Phase 1 *sets* the foundational patterns: domain models, the source-adapter interface, the snapshot store, and the change-detection gate. Phase 1 plan 01-01 explicitly creates the core schema (Source, Change with three date fields + status enum, Snapshot) and Alembic migrations.

### Integration Points
- The pull delivery API (FastAPI) is the ONLY integration seam with "the other product" — no shared database (API-07). Phase 1 establishes this API contract.

</code_context>

<specifics>
## Specific Ideas

- AI summary should read as a **compact change-spec contract** the prompt enforces: one-line headline + a "What changed / Where / To whom / For what cases" block (D-05), with explicit no-speculation / no-advice constraints baked into the prompt (D-07).
- The UI pattern the user pictured: structured-field data, rendered as **headlines in the queue with expandable detail sections** — scannability plus detail on demand (D-09).
- Noted as a fast Phase-1 upgrade *once the baseline works* (not required): the AI summary prompt could also surface any date phrase it noticed as a **non-authoritative hint** to the reviewer, to speed up effective-date entry. Baseline remains reviewer-entered (D-12).

</specifics>

<deferred>
## Deferred Ideas

- **AI date-hint for effective date** — surfacing an AI-noticed date phrase as a non-authoritative reviewer hint. Acknowledged as a quick win to layer on *after* the Phase 1 baseline (reviewer-entered effective date) works. Not in the Phase 1 commitment; revisit at the end of Phase 1 or in Phase 5 (AI extraction).
- Review UI access/auth model and full reviewer-identity attribution — deliberately not discussed; full audit trail with reviewer identity is Phase 8 (AUDIT-02).

None of the discussion strayed outside the Phase 1 domain — these are sequencing notes, not scope creep.

</deferred>

---

*Phase: 1-End-to-End Feed Slice*
*Context gathered: 2026-05-20*
