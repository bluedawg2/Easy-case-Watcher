---
quick_id: 260522-2kq
plan: quick-260522-2kq-01
status: complete
date: 2026-05-22
tasks_total: 2
tasks_completed: 2
---

# Quick Task 260522-2kq — Summary

**Task:** Fix Windows psycopg async event loop incompatibility — set
`WindowsSelectorEventLoopPolicy` at process startup so async psycopg connections
work on Windows.

## What shipped

A Windows-guarded `WindowsSelectorEventLoopPolicy` startup guard at the top of
`src/brm/__init__.py`. It runs at package import — before any async entry point
(`brm.seed`, `brm.run_pipeline`, the Uvicorn dev server, the future Procrastinate
worker) creates an event loop — so psycopg 3's async driver no longer crashes with
`psycopg.InterfaceError: Psycopg cannot use the 'ProactorEventLoop'` on Windows.
The guard is a verified no-op on Linux/macOS, so production containers are
unaffected.

## Root cause

On Windows, asyncio defaults to `ProactorEventLoop` (since Python 3.8). The async
psycopg driver (SQLAlchemy `postgresql+psycopg` dialect) only works on a
`SelectorEventLoop`. `brm/seed.py`'s plain `asyncio.run(seed())` spun up the
default Proactor loop, failing at first DB connection checkout. `alembic upgrade
head` worked because Alembic's async env.py installs its own selector loop; no
other async entry point did.

## Tasks

| # | Task | Result |
|---|------|--------|
| 1 | Add `sys.platform == "win32"` guard calling `asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())` at top of `brm/__init__.py` | Done — commit `8dbba70` |
| 2 | End-to-end verification (no code change) | Done — see notes below |

## Commits

- `8dbba70` — fix(quick-260522-2kq-01): guard Windows event loop policy at package import

## Design notes

- **Location: `src/brm/__init__.py`** — chosen over `db.py` because every async
  entry point imports a `brm.*` module, so the package `__init__.py` always runs
  first, at import time, before any event loop is created. A future non-DB async
  entry point might not import `db.py`; the package `__init__` is the durable
  single home.
- **No per-call-site patches.** `alembic/env.py` keeps its own existing
  `loop_factory` patch (out of scope).
- **`tests/conftest.py` untouched.** Its session-scoped `event_loop_policy`
  fixture already solves the pytest path; both it and `WindowsSelectorEventLoopPolicy`
  yield selector loops, so no conflict.

## Verification

- `uv run python -m brm.seed` — exit 0, **no `psycopg.InterfaceError`**. Fix
  proven end-to-end against local Postgres.
- `uv run pytest -q` — **100 passed, 0 failed**.

The executor's in-worktree verification run hit two pre-existing
worktree-environment artifacts (missing `.env`, missing uncommitted
`tests/fixtures/frbp_source_v1.captured`) unrelated to the fix; both were resolved
by re-verifying on the main tree, which has the `.env` and the fixture.
