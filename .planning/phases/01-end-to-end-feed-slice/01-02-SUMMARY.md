---
phase: 01-end-to-end-feed-slice
plan: 02
subsystem: ingest
tags: [python, httpx, selectolax, sqlalchemy, postgres, frbp, snapshot, seed]

# Dependency graph
requires:
  - phase: 01-end-to-end-feed-slice/01-01
    provides: Source, Snapshot, Change ORM models; async DB engine and session factory

provides:
  - FRBP rulemaking page adapter (FrbpSourceAdapter) with tri-state fetch outcome
  - FRBP relevance filter (is_frbp_relevant) and deterministic normalization (normalize)
  - Append-only snapshot store (store_snapshot) with bounded-retry concurrent-safe versioning
  - Idempotent source seed (seed()) for the one national FRBP rulemaking source
  - Fixture pair (v1 real capture + v2 modified copy) for fixture-replay change detection

affects:
  - 01-end-to-end-feed-slice/01-03  # run_ingest uses fetch_source + store_snapshot
  - 01-end-to-end-feed-slice/01-04  # AI summarizer receives Change rows from ingestion
  - 01-end-to-end-feed-slice/01-05  # pull API serves verified Change rows

# Tech tracking
tech-stack:
  added:
    - httpx 0.28.x (async HTTP client with conditional GET)
    - selectolax (fast C-backed HTML parser for amendment-list extraction)
    - respx (HTTP mock for deterministic offline tests)
  patterns:
    - SourceAdapter Protocol seam (src/brm/ingest/adapter.py) — all source adapters implement this
    - Tri-state FetchOutcome (CHANGED / UNCHANGED / FETCH_FAILED) — every code path resolves to exactly one outcome
    - Append-only snapshot versioning with UNIQUE(source_id, version) + IntegrityError retry
    - Identity-keyed normalization (sort by effective_date) prevents reorder false positives
    - Pure detect/ functions (no I/O) applied identically to fixture and live content (D-04)

key-files:
  created:
    - tests/fixtures/frbp_source_v1.captured  # real live capture (Task 1)
    - tests/fixtures/frbp_source_v2.captured  # modified copy with Dec 2028 entry added
    - src/brm/detect/__init__.py
    - src/brm/detect/relevance.py  # is_frbp_relevant() pure predicate
    - src/brm/detect/normalize.py  # normalize() pure function
    - src/brm/ingest/__init__.py
    - src/brm/ingest/outcome.py    # FetchOutcome + FetchResult
    - src/brm/ingest/adapter.py    # SourceAdapter Protocol
    - src/brm/ingest/rss.py        # FrbpSourceAdapter + parse_entries + fetch_source
    - src/brm/ingest/snapshot_store.py  # store_snapshot append-only
    - src/brm/seed.py              # idempotent seed()
    - tests/test_rss_adapter.py    # 21 tests
    - tests/test_snapshot_store.py # 5 tests
  modified:
    - tests/conftest.py  # ruff auto-fix (unused import cleanup)

key-decisions:
  - "D-02 resolved: FRBP source is the HTML rulemaking page, NOT the generic news/rss feed (per live curl verification)"
  - "Thin HTML parse in FrbpSourceAdapter uses selectolax; not the Phase 2 general scraping framework"
  - "field--name-body and field__item are the same div on the live page; parse_entries handles both cases (same-element and nested)"
  - "Normalization sort key: (effective_date, sorted_rule_families, sorted_doc_hrefs) for fully deterministic output"
  - "store_snapshot uses bounded retry (max 3) on IntegrityError to handle concurrent insert races"

patterns-established:
  - "Pattern: SourceAdapter Protocol seam in adapter.py; one adapter per source type behind this interface"
  - "Pattern: tri-state FetchOutcome — every fetch resolves to CHANGED / UNCHANGED / FETCH_FAILED with no silent paths"
  - "Pattern: pure detect/ functions (relevance.py, normalize.py) applied identically to fixture and live content"
  - "Pattern: fixture replay pair (v1 real + v2 modified) as deterministic regression test for change detection"

requirements-completed: [SRC-01, SRC-02, INGEST-01, INGEST-04, INGEST-05]

# Metrics
duration: 8min
completed: 2026-05-22
---

# Phase 1 Plan 02: FRBP Rulemaking Ingestion Adapter Summary

**FRBP rulemaking HTML adapter with tri-state fetch outcome, identity-keyed normalization, append-only snapshot store, and idempotent source seed for https://www.uscourts.gov/forms-rules/pending-rules-and-forms-amendments**

## Performance

- **Duration:** 8 min
- **Started:** 2026-05-22T07:57:39Z
- **Completed:** 2026-05-22T08:05:53Z
- **Tasks:** 3 (Tasks 2, 3, 4 — Task 1 was the blocking human-verify checkpoint completed prior)
- **Files modified:** 13

## Accomplishments

- Built and tested a complete ingestion slice for the FRBP rulemaking page: fixture pair, relevance filter, normalization, tri-state fetcher, snapshot store, and seed
- All 26 new tests pass (21 adapter + 5 snapshot/seed); full suite 55 tests green
- The `SourceAdapter` seam is established — Phase 2/3 HTML and PDF adapters plug in without disturbing this adapter

## Task Commits

1. **Task 2: Fixture v2 + relevance filter + normalization** - `5514816` (feat)
2. **Task 3: SourceAdapter seam + tri-state FRBP fetcher** - `67c8e4b` (feat)
3. **Task 4: Snapshot store + FRBP source seed** - `e7c7a25` (feat)

## Files Created/Modified

- `tests/fixtures/frbp_source_v2.captured` — v1 copy with Dec 1, 2028 Bankruptcy Rule 4002 entry added
- `src/brm/detect/__init__.py` — package marker
- `src/brm/detect/relevance.py` — `is_frbp_relevant(entry) -> bool` pure predicate
- `src/brm/detect/normalize.py` — `normalize(entries) -> str` pure function with identity-keyed sort
- `src/brm/ingest/__init__.py` — package marker
- `src/brm/ingest/outcome.py` — `FetchOutcome` enum + `FetchResult` dataclass
- `src/brm/ingest/adapter.py` — `SourceAdapter` Protocol (ingestion seam)
- `src/brm/ingest/rss.py` — `FrbpSourceAdapter`, `parse_entries`, `fetch_source`
- `src/brm/ingest/snapshot_store.py` — `store_snapshot` append-only with bounded retry
- `src/brm/seed.py` — `seed()` idempotent source seed
- `tests/test_rss_adapter.py` — 21 tests for relevance, normalization, and tri-state fetch
- `tests/test_snapshot_store.py` — 5 tests for snapshot versioning, append-only, and seed

## Decisions Made

- **D-02 resolved (confirmed in Task 1 prior):** The FRBP source is the rulemaking HTML page, not the generic news/rss feed. All adapter code targets this URL.
- **Thin HTML parse strategy:** `parse_entries()` in `rss.py` targets `div.field--name-body` to extract h2/ul/p structure. This is a per-source strategy for this one source, NOT the Phase 2 general HTML scraping framework.
- **Live fixture quirk discovered:** On the real page, `field--name-body` and `field__item` are the SAME div element (both classes on one node). The parser handles both the same-element case (live page) and the nested case (test HTML).
- **Normalization tie-breaker:** Sort key is `(effective_date, sorted_rule_families, sorted_doc_hrefs)` to guarantee fully deterministic output even when two entries share the same date.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `div.field--name-body div.field__item` CSS selector not matching live fixture**
- **Found during:** Task 2 (normalize tests — parse returning empty)
- **Issue:** The CSS selector `div.field--name-body div.field__item` assumed parent-child nesting, but on the live page these are the SAME div element (both classes on one node). The descendant selector returned no match.
- **Fix:** Changed container selection to find `div.field--name-body` directly, then fall back to `div.field__item` child if the outer container has no direct h2 children.
- **Files modified:** `src/brm/ingest/rss.py`
- **Verification:** `test_normalize_v1_v2_differ` and `test_normalize_v1_is_nonempty` pass with real fixture content.
- **Committed in:** 67c8e4b (Task 3 commit)

**2. [Rule 1 - Bug] Normalization sort not fully deterministic for entries with same effective_date**
- **Found during:** Task 2 (`test_normalize_same_identity_different_doc_links` failing)
- **Issue:** Using only `effective_date` as sort key left ties unresolved; Python's stable sort preserved input order, causing `normalize([a,b]) != normalize([b,a])` for entries with equal dates.
- **Fix:** Added `sorted(rule_families)` and `sorted(doc_hrefs)` as tie-breaker sort keys.
- **Files modified:** `src/brm/detect/normalize.py`
- **Verification:** `test_normalize_same_identity_different_doc_links` passes.
- **Committed in:** 5514816 (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 - bugs)
**Impact on plan:** Both fixes necessary for correct behavior. No scope creep.

## Phase-1 Limitation Notes

### Snapshot Retention

Phase 1 is append-only with no snapshot pruning — this is acceptable because there is exactly one source with approximately annual real changes, so volume is trivial. This is a **known, deliberate Phase-1 limitation**: at the eventual 140+ sources a retention/compression/content-addressing strategy will be required. This is flagged as roadmap work for Phase 4+ scaling. Do NOT build retention in Phase 1.

### `tenant_id` Column

The `tenant_id` column on the `Source` row seeded by `seed.py` is intentionally `None` and un-scoped in Phase 1 — there is no per-tenant auth yet. CLAUDE.md explicitly mandates the column as day-one multi-tenancy insurance (a cheap insurance column added to all tenant-scoped tables from day one). Its emptiness is a known, deliberate decision, not a defect. Per-tenant auth and query-layer scoping are Phase 2+ work (CLAUDE.md "Add a `tenant_id` column to all tenant-scoped tables from day one").

## Issues Encountered

None beyond the two auto-fixed parser bugs above.

## User Setup Required

None — no external service configuration required for this plan. Tests run fully offline via respx mocking.

## Next Phase Readiness

- `fetch_source(source)` and `store_snapshot(session, source, content, hash)` are ready for plan 01-03 (`run_ingest`)
- `seed()` inserts the one FRBP source; plan 01-03 can call `fetch_source` against it
- The `SourceAdapter` seam is established for Phase 2 HTML/PDF adapters
- Fixture pair (v1 + v2) enables deterministic regression testing throughout the phase

---
*Phase: 01-end-to-end-feed-slice*
*Completed: 2026-05-22*
