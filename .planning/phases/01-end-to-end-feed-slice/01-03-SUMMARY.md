---
phase: 01-end-to-end-feed-slice
plan: "03"
subsystem: detect
tags: [change-detection, hash-gate, diff, pipeline, fixture-replay]
dependency_graph:
  requires: [01-02]
  provides: [detect/diff.py, detect/detector.py, pipeline.py, test_fixture_replay.py]
  affects: [01-04]
tech_stack:
  added: []
  patterns:
    - Hash-Gate + Textual Diff (RESEARCH Pattern 4)
    - Fixture Replay With No Production Branch (RESEARCH Pattern 7)
key_files:
  created:
    - src/brm/detect/diff.py
    - src/brm/detect/detector.py
    - src/brm/pipeline.py
    - tests/test_detect.py
    - tests/test_fixture_replay.py
  modified: []
decisions:
  - "First-fetch establishes a silent baseline — prior_snapshot=None returns None with no Change row (review finding #10)"
  - "Hash-gate (DETECT-02): equal SHA-256 hashes terminate the pipeline before any downstream work"
  - "FETCH_FAILED is NOT silently treated as no-change; source.health_status set to 'failed' (T-03-01)"
  - "No if-fixture branch anywhere in src/ — D-04 enforced; test_identical_code_path is a behavioral proof, not a grep"
metrics:
  duration: "~30 minutes"
  completed: "2026-05-22"
  tasks_completed: 2
  tasks_total: 2
---

# Phase 01 Plan 03: Change Detection and Pipeline Orchestrator Summary

**One-liner:** SHA-256 hash-gate detector with difflib unified diff wired into a single run_ingest orchestrator proven fixture-and-live-identical by behavioral assertion.

## What Was Built

### Task 1: Hash-gate detector and unified-diff helper

**`src/brm/detect/diff.py`**
- `content_hash(normalized: str) -> str` — SHA-256 hex digest of normalized content (64-char lowercase hex)
- `textual_diff(old: str, new: str) -> str` — stdlib `difflib.unified_diff` with `fromfile="previous"` / `tofile="current"` headers; returns empty string when content is identical

**`src/brm/detect/detector.py`**
- `async def detect_change(session, source, prior_snapshot, current_snapshot) -> Change | None`
- FIRST-FETCH RULE (review finding #10): `prior_snapshot is None` → return `None`, no Change row
- HASH-GATE (DETECT-02): `prior_snapshot.content_hash == current_snapshot.content_hash` → return `None`
- On hash difference: compute `textual_diff`, INSERT `Change` with `status=STATUS_DETECTED`, `detected_at=datetime.now(UTC)`, `diff_text`, `prior_snapshot_id`, `current_snapshot_id`, `source_id`

**`tests/test_detect.py`** — 13 tests:
- `test_first_fetch_baseline`, `test_hash_gate_blocks`, `test_diff_creates_change`, `test_change_references_snapshots`, `test_change_detected_at_is_set`
- `TestContentHash`: determinism, 64-char hex, different inputs differ, empty string
- `TestTextualDiff`: format headers, removed lines, added lines, identical content

### Task 2: run_ingest pipeline orchestrator and fixture-replay proof

**`src/brm/pipeline.py`**
- `async def run_ingest(session, source, adapter) -> Change | None`
- `FETCH_FAILED` → `source.health_status = "failed"`, `last_checked_at` set, return `None` (explicit, not silent — T-03-01)
- `UNCHANGED` → `source.health_status = "healthy"`, `last_checked_at` set, conditional-GET headers updated, return `None`
- `CHANGED` → `store_snapshot` → query prior snapshot via `ORDER BY version DESC OFFSET 1` → `detect_change` → update all source bookkeeping fields, return Change (or None for baseline)
- No `if fixture:` branch anywhere — D-04

**`tests/test_fixture_replay.py`** — 5 tests:
- `test_fixture_replay_baseline_then_change`: v1→v2 replay confirms silent baseline then detected Change
- `test_fixture_replay_hash_gate`: v1→v1 replay confirms zero Changes (hash-gate / UNCHANGED)
- `test_fixture_replay_fetch_failed`: timeout → None returned, health_status="failed", no Snapshot
- `test_health_status_updated_on_success`: health_status never remains "unknown" after successful poll
- `test_identical_code_path`: behavioral D-04 proof — two independent sources fed identical bytes produce byte-identical `diff_text` and `content_hash` (replaces cargo-cult grep-based policing per review Major Concern)

## Test Results

- Task 1: `uv run pytest tests/test_detect.py -x -q` → 13 passed
- Task 2: `uv run pytest tests/test_fixture_replay.py -x -q` → 5 passed
- Full suite: `uv run pytest -x -q` → **73 passed** (55 prior + 18 new)

## Deviations from Plan

None — plan executed exactly as written.

The test `test_fixture_replay_baseline_then_change` had a minor self-inflicted syntax error during development (an overly-clever `__import__` construct instead of a direct import) that was caught immediately by pytest and corrected before any commit. This was a development-time mistake, not a plan deviation.

## Known Stubs

None — all five acceptance criteria for both tasks are met with real implementation. No placeholder values, hardcoded empty data, or TODO stubs exist in any created file.

## Threat Flags

No new security-relevant surface was introduced beyond what the plan's `<threat_model>` covers. The three threats in the register (T-03-01, T-03-02, T-03-03) are all mitigated:
- T-03-01: FETCH_FAILED handled explicitly, not silently as no-change
- T-03-02: `test_identical_code_path` behavioral assertion proves no production-only branch
- T-03-03: Accepted — `difflib` is stdlib, bounded by snapshot size, negligible at Phase 1 volume

## Self-Check: PASSED

Files created:
- `src/brm/detect/diff.py` — FOUND
- `src/brm/detect/detector.py` — FOUND
- `src/brm/pipeline.py` — FOUND
- `tests/test_detect.py` — FOUND
- `tests/test_fixture_replay.py` — FOUND

Commits verified:
- `e12bb5e` feat(01-03): hash-gate detector and unified-diff helper — FOUND
- `f4b7ed5` feat(01-03): run_ingest pipeline orchestrator and fixture-replay proof — FOUND
