---
phase: "01"
plan: "04"
subsystem: ai-summarization
tags: [anthropic-sdk, structured-output, pipeline, lifecycle]
dependency_graph:
  requires: [01-03]
  provides: [run_summarize, ChangeSummary, summarize]
  affects: [pipeline.py, FrbpSourceAdapter]
tech_stack:
  added:
    - "anthropic SDK client.messages.parse() with output_format= (GA path)"
    - "asyncio.to_thread + asyncio.wait_for for sync SDK in async pipeline"
  patterns:
    - "Pydantic BaseModel as structured output schema for LLM"
    - "Server-side disclaimer constant (NOT_LEGAL_ADVICE_LABEL) — not model output"
    - "Lifecycle guard (assert_transition) before AI call"
    - "Retry count encoded in summary_error text field"
key_files:
  created:
    - src/brm/schemas/__init__.py
    - src/brm/schemas/summary.py
    - src/brm/ai/__init__.py
    - src/brm/ai/summarize.py
    - src/brm/run_pipeline.py
    - tests/test_ai.py
    - tests/test_live_integration.py
  modified:
    - src/brm/pipeline.py
    - src/brm/ingest/rss.py
decisions:
  - "NOT_LEGAL_ADVICE_LABEL is a server constant applied by run_summarize, not a model output field — keeps AI output factual-only"
  - "IllegalTransitionError propagates from run_summarize (not caught) — callers must pass valid Change"
  - "asyncio.to_thread wraps synchronous summarize() call with 60s timeout via asyncio.wait_for"
  - "FrbpSourceAdapter gained optional feed_file param for fixture-replay without changing live code path"
  - "Test helper uses unique feed_url suffix per test call to avoid UNIQUE constraint collisions in shared transaction"
metrics:
  duration: "~15 min"
  completed: "2026-05-22"
  tasks_completed: 2
  files_created: 7
  files_modified: 2
---

# Phase 01 Plan 04: AI Summarizer + run_summarize Pipeline Step Summary

**One-liner:** Anthropic SDK structured-output summarizer (five-field ChangeSummary) wired into run_summarize pipeline step with lifecycle guard, retry tracking, and 60s timeout.

## What Was Built

### Task 2: ChangeSummary schema + summarize wrapper

- `src/brm/schemas/summary.py`: `ChangeSummary` Pydantic model with five fields (headline, what_changed, where, to_whom, for_what_cases). `NOT_LEGAL_ADVICE_LABEL` is a module-level constant — never a model output field.
- `src/brm/ai/summarize.py`: `summarize(diff_text)` function using `client.messages.parse(output_format=ChangeSummary)` returning `response.parsed_output`. `SYSTEM_PROMPT` enforces three guardrails: no speculation, no advice phrasing, 1-3 sentences per field.
- 4 unit tests: schema shape, no disclaimer field, guardrail phrases in SYSTEM_PROMPT, label constant sanity.

### Task 3: run_summarize, admin CLI, live-integration tests

- `src/brm/pipeline.py` extended with `run_summarize(session, change)`:
  - Raises `ValueError` if `diff_text` is empty.
  - Calls `assert_transition(change.status, STATUS_PROCESSED)` — `IllegalTransitionError` propagates to caller.
  - Parses existing `retry_count` from `summary_error` text using regex.
  - Wraps synchronous `summarize()` in `asyncio.to_thread` with a 60-second `asyncio.wait_for` timeout.
  - On success: sets `summary`, `not_legal_advice_label`, `model_id`, clears `summary_error`, status → `processed`.
  - On any exception: increments retry_count, stores error string, status → `summary_failed`.
  - Calls `session.flush()` before returning.
- `src/brm/ingest/rss.py`: Added `feed_file` param to `FrbpSourceAdapter.__init__` with `_fetch_from_file` helper that reads local HTML, runs same parse/normalize/hash path, applies UNCHANGED/CHANGED logic.
- `src/brm/run_pipeline.py`: Admin CLI (`python -m brm.run_pipeline [FEED_FILE]`) that seeds the FRBP source, runs `run_ingest`, then `run_summarize`, and prints results.
- `tests/test_live_integration.py`: Two opt-in live tests (`-m live`) for network fetch and schema validation. Uses `parse_entries` (the actual function name in rss.py).
- 5 additional unit tests: success path, invalid status, failure path, retry, JSONB round-trip.

## Test Results

- `uv run pytest tests/test_ai.py -x -q`: 9 passed (no ANTHROPIC_API_KEY required)
- `uv run pytest -x -q`: 84 passed (full suite green)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test helper wired FKs incorrectly**
- **Found during:** Task 3, first test run
- **Issue:** `_make_fake_change` created Source/Snapshot/Change with `None` FK values, then tried to set them after a flush — but the Change INSERT failed with `NotNullViolation` because `source_id` was `None` at flush time.
- **Fix:** Refactored `_make_fake_change` into an `async` function that flushes Source first (to get `src.id`), then Snapshot (to get `snap.id`), then creates Change with all FKs already populated. Added `feed_url_suffix` parameter to avoid UNIQUE constraint collisions across tests sharing the same transaction.
- **Files modified:** `tests/test_ai.py`

**2. [Rule 3 - Blocking] `_parse_frbp_html` vs `parse_entries` name**
- **Found during:** Task 3, writing `test_live_integration.py`
- **Issue:** Plan specified importing `_parse_frbp_html` but the actual function in `rss.py` is named `parse_entries` (public).
- **Fix:** Used `parse_entries` in the live-integration test.
- **Files modified:** `tests/test_live_integration.py`

**3. [Rule 3 - Blocking] `AsyncSessionLocal` vs `SessionLocal` in run_pipeline.py**
- **Found during:** Task 3, writing `run_pipeline.py`
- **Issue:** Plan specified `from brm.db import engine, Base, AsyncSessionLocal` but `db.py` exports `SessionLocal` (not `AsyncSessionLocal`).
- **Fix:** Used `SessionLocal` as exported.
- **Files modified:** `src/brm/run_pipeline.py`

## Known Stubs

None — all five ChangeSummary fields are populated by the model; the admin CLI and pipeline step are fully wired.

## Threat Flags

None — this plan adds no new network endpoints, auth paths, or file-access patterns beyond what was already planned.

## Self-Check: PASSED

Files exist:
- src/brm/schemas/summary.py: FOUND
- src/brm/ai/summarize.py: FOUND
- src/brm/pipeline.py (run_summarize added): FOUND
- src/brm/run_pipeline.py: FOUND
- tests/test_ai.py: FOUND
- tests/test_live_integration.py: FOUND

Commits: bb6e117 — FOUND
