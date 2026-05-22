---
phase: 3
slug: pdf-ingestion-district-coverage
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-22
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x + pytest-asyncio |
| **Config file** | pyproject.toml (existing) |
| **Quick run command** | `uv run pytest -q` |
| **Full suite command** | `uv run pytest` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest -q`
- **After every plan wave:** Run `uv run pytest`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 3-01-XX | 01 | — | INGEST-03 | — | N/A | unit | `uv run pytest -q` | ❌ W0 | ⬜ pending |
| 3-02-XX | 02 | — | INGEST-03 | — | N/A | unit | `uv run pytest -q` | ❌ W0 | ⬜ pending |
| 3-03-XX | 03 | — | SRC-03 | — | N/A | unit | `uv run pytest -q` | ❌ W0 | ⬜ pending |
| 3-04-XX | 04 | — | SRC-04 | — | N/A | unit | `uv run pytest -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky — the planner fills in per-task rows during planning.*

---

## Wave 0 Requirements

- [ ] PDF fixture files for text-layer / scanned / table-heavy sub-types — shared fixtures
- [ ] Deterministic changed/unchanged PDF fixture pair (D-10) — pilot-source replay
- [ ] `tests/conftest.py` — shared PDF fixture loaders

*Planner refines this list against the four plan slices.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real PDF-based district rule change flows end-to-end into the review queue (criterion 5) | INGEST-03 | End-to-end pilot demo across ingestion + detection + review queue | Run the pilot fixture pair through `run_ingest`; confirm a Change record appears in the review queue with the PDF-provenance flag |

*Planner may convert this to an automated fixture-replay test if the pilot pair supports it.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
