---
phase: 3
slug: pdf-ingestion-district-coverage
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-22
updated: 2026-05-22
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x + pytest-asyncio (+ respx for HTTP mocking) |
| **Config file** | pyproject.toml + tests/conftest.py (SAVEPOINT-rollback `db_session`, `mock_http` respx fixture, PDF fixture loader, Windows SelectorEventLoop patch) |
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

Per-task `<automated>` commands are taken verbatim from each plan's `<verify>` blocks. Test files created in Wave 0 (the scaffolds, fixture loaders, and fixtures) are noted in the Wave-0 column.

| Task ID | Plan | Wave | Requirement | Type | Automated Command | Wave-0 Dependency |
|---------|------|------|-------------|------|-------------------|-------------------|
| 3-01-T1 | 01 | 1 | INGEST-03 | checkpoint:human-verify (package legitimacy gate) | `uv run python -c "import pypdfium2; import pdfplumber; from pypdfium2.raw import FPDF_PAGEOBJ_IMAGE; print('ok')"` | none — install gate |
| 3-01-T2 | 01 | 1 | INGEST-03 | auto/tdd — schema + FetchResult.reason_code | `uv run alembic upgrade head && uv run pytest tests/test_models.py -q` | `tests/test_models.py` exists (Phase 1) |
| 3-01-T3 | 01 | 1 | INGEST-03 / D-08 / D-13 | auto/tdd — extract_pdf_text + classifier | `uv run pytest tests/test_pdf_adapter.py -q` | **creates** `tests/test_pdf_adapter.py` scaffold + `tests/conftest.py` PDF fixture loader + `tests/fixtures/pdf/.gitkeep` |
| 3-01-T4 | 01 | 1 | INGEST-03 / D-08 | checkpoint:human-action — fixture capture | `uv run python -c "...; print('fixtures ok')"` (clean/scanned/broken extraction assertions) | **creates** `tests/fixtures/pdf/{clean_text_layer,scanned_image_only,broken_text_layer,tabular}.pdf` + `SOURCES.md` |
| 3-02-T1 | 02 | 2 | INGEST-03 (crit 2) | auto/tdd — pdf_normalize | `uv run pytest tests/test_pdf_normalize.py -q` | **creates** `tests/test_pdf_normalize.py` |
| 3-02-T2 | 02 | 2 | INGEST-03 / D-06 / D-08 | auto/tdd — PdfSourceAdapter document mode + tri-state | `uv run pytest tests/test_pdf_adapter.py -q` | extends `tests/test_pdf_adapter.py` (scaffold from 3-01-T3) |
| 3-02-T3 | 02 | 2 | INGEST-03 | auto — clean PDF end-to-end through run_ingest | `uv run pytest tests/test_pdf_adapter.py -q && uv run pytest -q` | extends `tests/test_pdf_adapter.py` |
| 3-03-T1 | 03 | 3 | INGEST-03 / SRC-03 / D-11 / D-16/17/18 | auto/tdd — index/listing mode + run_pdf_ingest dispatch | `uv run pytest tests/test_pdf_adapter.py -q` | extends `tests/test_pdf_adapter.py` |
| 3-03-T2 | 03 | 3 | SRC-03 | auto — district + CACB-LBR seed rows | `uv run pytest tests/test_source_onboarding.py -q` | **creates** `tests/test_source_onboarding.py` (full assertions added in 3-03-T3b) |
| 3-03-T3a | 03 | 3 | INGEST-03 (crit 5) / D-10 | checkpoint:human-action — Oregon LBR fixture pair | `uv run python -c "...; print('lbr pair ok')"` (pair exists, differs, SOURCES.md present) | **creates** `tests/fixtures/pdf/{oregon_lbr_prior,oregon_lbr_current}.pdf` |
| 3-03-T3b | 03 | 3 | INGEST-03 (crit 5) / SRC-03/06 / D-10 | auto — criterion-5 replay + onboarding proof | `uv run pytest tests/test_pdf_fixture_replay.py tests/test_source_onboarding.py -q && uv run pytest -q` | **creates** `tests/test_pdf_fixture_replay.py`; extends `tests/test_source_onboarding.py` |
| 3-04-T1 | 04 | 4 | SRC-04 | auto — launch-state exemption seed rows | `uv run pytest tests/test_source_onboarding.py -q` | extends `tests/test_source_onboarding.py` (idempotent-seeding proof only) |
| 3-04-T2 | 04 | 4 | SRC-04 / D-13 / D-14 | auto — tabular extraction + exemption text-change detection | `uv run pytest tests/test_source_onboarding.py -q && uv run pytest -q` | extends `tests/test_source_onboarding.py`; reuses `tests/fixtures/pdf/tabular.pdf` + new exemption pair |

*Status legend: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky — execution fills task status during the run.*

---

## Wave 0 Requirements

Wave 0 = the test scaffolds, shared fixture loaders, and captured fixtures that later-wave tasks depend on. All Wave 0 artifacts are created by explicit tasks in Wave 1 / Wave 2:

- [x] `tests/test_pdf_adapter.py` scaffold — created by **3-01 Task 3** (`FIXTURES_DIR`, `load_pdf` helper, the five extraction tests).
- [x] `tests/conftest.py` shared PDF fixture loader — created by **3-01 Task 3** (`load_pdf_fixture` helper/fixture reading `tests/fixtures/pdf/<name>`).
- [x] `tests/fixtures/pdf/` directory + `.gitkeep` — created by **3-01 Task 3**.
- [x] PDF fixture files for text-layer / scanned / broken / table-heavy sub-types — captured by **3-01 Task 4** (`checkpoint:human-action`).
- [x] `tests/test_pdf_normalize.py` — created by **3-02 Task 1**.
- [x] `tests/test_source_onboarding.py` — created by **3-03 Task 2**, full pattern-routing assertions added by **3-03 Task 3b**.
- [x] `tests/test_pdf_fixture_replay.py` — created by **3-03 Task 3b**.
- [x] Deterministic changed/unchanged Oregon LBR PDF fixture pair (D-10) — captured by **3-03 Task 3a** (`checkpoint:human-action`).

Every later-wave task that references one of these files is preceded by the task that creates it (same wave or earlier). No task has a `MISSING` automated verify.

---

## Manual-Only Verifications

| Behavior | Requirement | Status | Resolution |
|----------|-------------|--------|------------|
| Real PDF-based district rule change flows end-to-end into the review queue (criterion 5) | INGEST-03 | **Automated** | Converted to a fixture-replay test — `tests/test_pdf_fixture_replay.py` (3-03 Task 3b) runs the Oregon LBR superseded/replacement pair through `run_pdf_ingest` and asserts a baseline then a `detected` Change with `pdf_provenance`. The criterion-5 fixture pair is captured by the `checkpoint:human-action` task 3-03 Task 3a (a human captures the live PDFs or, per RESEARCH Assumption A1 / D-10, decides on the hand-modified-copy fallback). |

No remaining manual-only verifications — every phase success criterion has an automated test command in the map above.

---

## Validation Sign-Off

- [x] All tasks have an `<automated>` verify command (the two `checkpoint:human-action` fixture-capture tasks each have an automated post-capture assertion command; no task is `MISSING`)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify — every task in every wave runs a pytest or python assertion command
- [x] Wave 0 covers all created-by-this-phase test files and fixtures; every consumer task is preceded by its creator task
- [x] No watch-mode flags — all commands are single-shot `uv run pytest`/`uv run python -c`
- [x] Feedback latency < 30s — full suite ~30s
- [x] `nyquist_compliant: true` set in frontmatter
- [x] `wave_0_complete: true` set in frontmatter — all Wave 0 scaffolding is assigned to explicit Wave 1/2 tasks (3-01 T3/T4, 3-02 T1, 3-03 T2/T3a/T3b)

**Approval:** approved — validation map populated from plan `<verify>` blocks; Nyquist-compliant.
