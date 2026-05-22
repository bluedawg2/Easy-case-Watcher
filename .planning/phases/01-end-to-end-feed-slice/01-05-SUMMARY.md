---
phase: "01"
plan: "05"
subsystem: api
tags: [fastapi, auth, review-queue, pull-api, react, vite, tanstack-query]
dependency_graph:
  requires: [01-04]
  provides: [review-queue-api, pull-delivery-api, review-ui]
  affects: [main-product-pull-integration]
tech_stack:
  added:
    - FastAPI router (review-queue, pull-delivery)
    - API-key auth dependency (X-API-Key header)
    - httpx.AsyncClient + ASGITransport for async API testing
    - React 19 + Vite 8 + TypeScript 6 SPA
    - TanStack Query 5 for server-state management
    - react-diff-viewer-continued 4.2.2 (React 19 compatible)
    - Vitest 4 + Testing Library for frontend tests
  patterns:
    - SQLAlchemy lazy="raise" relationships with explicit selectinload / session.refresh
    - FOR UPDATE locking: lock row first, then refresh relationships separately
    - SAVEPOINT-rollback session injected via FastAPI dependency_overrides
    - since-cursor incremental pull pattern (updated_at > since, ordered by updated_at, id)
key_files:
  created:
    - src/brm/auth.py
    - src/brm/schemas/api.py
    - src/brm/api/__init__.py
    - src/brm/api/review.py
    - src/brm/api/pull.py
    - src/brm/main.py
    - tests/test_auth.py
    - tests/test_review_api.py
    - tests/test_pull_api.py
    - web/src/api.ts
    - web/src/App.tsx
    - web/src/ReviewQueue.tsx
    - web/src/ChangeDetail.tsx
    - web/src/ReviewQueue.test.tsx
    - web/src/main.tsx
    - web/src/test-setup.ts
    - web/vite.config.ts
    - web/package.json
  modified:
    - src/brm/models/change.py (added source/current_snapshot relationships)
decisions:
  - "FOR UPDATE + selectinload cannot be combined in one SQLAlchemy query — lock the row first, then session.refresh(change, ['source']) separately"
  - "react-diff-viewer-continued@4.2.2 is compatible with React 19 — no peer-dep errors, no React 18 pin needed"
  - "approve/reject lifecycle transitions require in_review status (not processed) — tests seed in_review changes accordingly (lifecycle-correct deviation from plan spec)"
metrics:
  duration: "~25 minutes"
  completed: "2026-05-22"
  tasks_completed: 3
  files_created: 19
  files_modified: 1
---

# Phase 01 Plan 05: Auth, Review API, Pull API, React SPA Summary

Implemented the full review interface: API-key authentication, the review-queue API for human reviewers, the pull-delivery API for the other product, and a React SPA for the queue UI.

## Task 1: API-key auth + review-queue API

**Built:** `src/brm/auth.py`, `src/brm/schemas/api.py`, `src/brm/api/review.py`, `src/brm/main.py`

- `require_api_key` FastAPI dependency validates `X-API-Key` header against `settings.api_key`
- Six review endpoints: `GET /review/queue`, `GET /review/{id}`, `POST /review/{id}/approve`, `POST /review/{id}/edit`, `POST /review/{id}/reject`, `POST /review/{id}/retry-summary`
- Added `source` and `current_snapshot` relationships to `Change` model with `lazy="raise"` — prevents silent N+1 queries, forces explicit eager loading
- `FOR UPDATE` locking pattern: lock the `Change` row first, then `session.refresh(change, ['source'])` separately (SQLAlchemy does not support `with_for_update()` combined with `selectinload` in a single query)
- `IllegalTransitionError` → HTTP 409 registered as app-level exception handler
- CORS middleware allows `http://localhost:5173` (Vite dev server)

## Task 2: Pull delivery API

**Built:** `src/brm/api/pull.py`

- `GET /changes?since=<ISO datetime>` returns verified changes ordered by `updated_at`, `id`
- `since` cursor uses strict `>` comparison for incremental polling
- Stable ordering by `(updated_at, id)` prevents cursor drift when multiple changes share the same timestamp

## Task 3: React + Vite review-queue SPA

**Built:** `web/src/` — `api.ts`, `App.tsx`, `ReviewQueue.tsx`, `ChangeDetail.tsx`, `ReviewQueue.test.tsx`, `main.tsx`, `test-setup.ts`, `vite.config.ts`, `package.json`

- Master/detail layout: 360px queue pane (left) + expandable detail pane (right)
- Reviewer name persisted to `localStorage`
- Status indicators: summary_failed (red dot), in_review (yellow), processed (green)
- Approve requires effective date (button disabled until date entered)
- Edit summary enters edit mode with field-by-field inputs; saves via `POST /review/{id}/edit`
- `summary_failed` changes show "Retry summary" button; approve/edit/reject hidden
- Dev-server proxy: `/review` and `/changes` forwarded to `localhost:8000`
- Vitest configured with jsdom environment and `@testing-library/jest-dom`

### React 19 + react-diff-viewer-continued@4.2.2 Compatibility

**Result: COMPATIBLE — no peer-dep errors, no React 18 pin needed.**

`react-diff-viewer-continued@4.2.2` installed cleanly alongside React 19.2.6 with zero peer-dependency warnings or errors. React 18 pin was not required.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed approve/reject test seeds to use in_review status**

- **Found during:** Task 1 test execution
- **Issue:** Plan specified seeding a `processed` change for approve and reject tests. The lifecycle only allows `in_review → verified` and `in_review → rejected` — `processed → verified` and `processed → rejected` are illegal transitions. Tests were returning 409.
- **Fix:** Changed `test_approve_records_dates`, `test_approve_missing_effective_date_returns_422`, and `test_reject` to seed `in_review` changes — which is the correct lifecycle state for these operations.
- **Files modified:** `tests/test_review_api.py`
- **Commit:** included in 668cb6d

## Final Test Counts

**Backend:** 100 tests passed (16 new: 3 auth + 8 review-queue + 5 pull-api; 84 pre-existing)

**Frontend:** 4 Vitest tests passed (ReviewQueue: queue rendering, row selection, approve button state, summary_failed UI)

## Known Stubs

None — all API calls and data flows are wired end-to-end. The UI reads from `/review/queue`, `/review/{id}`, and writes to approve/edit/reject/retry endpoints.

## Self-Check: PASSED

Key files created:
- src/brm/auth.py: exists
- src/brm/api/review.py: exists
- src/brm/api/pull.py: exists
- src/brm/main.py: exists
- web/src/ReviewQueue.tsx: exists
- web/src/ChangeDetail.tsx: exists

Commits verified:
- 668cb6d: plan 01-05: auth, review API, pull API with since-cursor
- b541ebf: plan 01-05: React review-queue SPA
