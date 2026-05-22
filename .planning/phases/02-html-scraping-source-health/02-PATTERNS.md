# Phase 2: HTML Scraping & Source Health - Pattern Map

**Mapped:** 2026-05-22
**Files analyzed:** 17 new/modified files
**Analogs found:** 9 strong / 17

> **CRITICAL FINDING — read before planning.**
> RESEARCH.md repeatedly cites Phase 1 code that **does not exist yet**: `src/brm/ingest/adapter.py` (`SourceAdapter` Protocol), `src/brm/ingest/outcome.py` (`FetchOutcome`/`FetchResult`), `src/brm/ingest/rss.py` (`FrbpSourceAdapter`), `src/brm/ingest/snapshot_store.py`, `src/brm/detect/*`, `src/brm/pipeline.py` (`run_ingest`), and `src/brm/seed.py`.
>
> The actual Phase 1 delivery (commits `5378e1a` / `c5a3f03`) was **plan 01-01 only — the domain foundation**: `models/`, `lifecycle.py`, `config.py`, `db.py`, the `0001_initial_schema.py` migration, and `tests/`. Plans 01-02 through 01-05 (the adapter seam, RSS adapter, tri-state fetcher, `run_ingest`, the AI/API layers) were planned in 01-01's docstrings but **never implemented**. `src/brm/{ingest,detect,ai,api,schemas}/` are empty directories containing not even an `__init__.py`. `pyproject.toml` declares a `brm-run-pipeline = "brm.run_pipeline:main"` script entry point for a `run_pipeline.py` that does not exist.
>
> **Consequence for the planner:** Phase 2 cannot "extend the existing `SourceAdapter` seam" — it must *create* it. The `SourceAdapter` Protocol, `FetchOutcome`/`FetchResult` contract, `run_ingest` orchestrator, snapshot store, detector, and a CLI entrypoint are all **net-new in Phase 2**, not extensions. Phase 2's true scope is larger than CONTEXT.md/RESEARCH.md assume. The planner should either (a) absorb the missing Phase 1 ingest foundation into Phase 2's plan slices, or (b) flag the gap to the orchestrator. The "EXISTING — unchanged" labels in RESEARCH.md's project-structure tree are aspirational, not factual.
>
> Where RESEARCH.md says "reuse the Phase 1 X" and X does not exist, this map points the planner at the **closest real analog** (an ORM model, the lifecycle module, the migration, the test conftest) so new code still matches established Phase 1 conventions.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/brm/ingest/__init__.py` | package-init | n/a | `src/brm/models/__init__.py` | role-match |
| `src/brm/ingest/adapter.py` | interface/seam | request-response | *(none — net-new Protocol)* | no analog |
| `src/brm/ingest/outcome.py` | model (dataclass/enum) | transform | `src/brm/lifecycle.py` (constants + enum-set discipline) | role-match |
| `src/brm/ingest/html.py` | adapter (service) | request-response / streaming-fetch | *(none — net-new; RESEARCH Pattern 1)* | no analog |
| `src/brm/ingest/extract.py` | utility (pure) | transform | *(none — net-new; RESEARCH Code Examples)* | no analog |
| `src/brm/ingest/fingerprint.py` | utility (pure) | transform | `src/brm/lifecycle.py` (`assert_transition` pure-guard shape) | partial |
| `src/brm/ingest/failure_detect.py` | utility (pure) | transform | `src/brm/lifecycle.py` (pure module of constants + a classifier fn) | partial |
| `src/brm/ingest/snapshot_store.py` | service (DB write) | CRUD / append-only | `src/brm/models/snapshot.py` (the table it writes) | partial |
| `src/brm/detect/identity.py` | utility (pure) | transform | `src/brm/lifecycle.py` (pure module) | partial |
| `src/brm/detect/detector.py` | service (DB write) | event-driven / CRUD | *(none — net-new)* | no analog |
| `src/brm/health/staleness.py` | service (query) | batch / read | *(none — net-new; RESEARCH Pattern 6)* | no analog |
| `src/brm/health/alerts.py` | utility (wrapper) | event-driven | `src/brm/config.py` (graceful optional-config pattern) | partial |
| `src/brm/models/source.py` | model (ORM) — **MODIFIED** | CRUD | `src/brm/models/source.py` (itself — extend in place) | exact |
| `src/brm/models/change.py` | model (ORM) — **MODIFIED** | CRUD | `src/brm/models/change.py` (itself — extend in place) | exact |
| `src/brm/models/change_observation.py` | model (ORM) — **NEW** | CRUD | `src/brm/models/snapshot.py` | exact |
| `src/brm/lifecycle.py` | config/state-set — **MODIFIED** | n/a | `src/brm/lifecycle.py` (itself — `HEALTH_STATUSES`) | exact |
| `src/brm/config.py` | config — **MODIFIED** | n/a | `src/brm/config.py` (itself — add `sentry_dsn`) | exact |
| `alembic/versions/0002_*.py` | migration | schema | `alembic/versions/0001_initial_schema.py` | exact |
| `src/brm/pipeline.py` (or `run_pipeline.py`) | orchestrator + CLI | event-driven | *(none — net-new; RESEARCH Architecture Diagram)* | no analog |
| `src/brm/seed.py` | script/fixture | batch | `tests/test_models.py::make_source` (the only Source-construction example) | partial |
| `tests/test_*.py` (Phase 2 suites) | test | n/a | `tests/test_models.py`, `tests/test_lifecycle.py`, `tests/conftest.py` | exact |
| `tests/fixtures/html/*.html` | test fixture | n/a | *(none — no fixtures dir exists)* | no analog |

## Pattern Assignments

### `src/brm/models/source.py` (ORM model — MODIFIED)

**Analog:** itself — `src/brm/models/source.py` lines 1-86. Phase 2 *extends this file in place*; new columns must match the existing column-declaration style exactly.

**Column-declaration pattern to copy** (lines 49-78): `Mapped[...]` typed attributes with `mapped_column(...)`; nullable columns typed `Mapped[T | None]`; defaults given as **both** `default=` (Python-side) and `server_default=` (DB-side); timestamps use `default=datetime.utcnow, server_default="now()"`.

**CHECK-constraint pattern** (lines 42-47) — when `HEALTH_STATUSES` gains `"paused"`, this constraint **must** be updated in lockstep with the migration:
```python
__table_args__ = (
    CheckConstraint(
        "health_status IN ('unknown', 'healthy', 'failed')",   # → add 'paused'
        name="ck_source_health_status",
    ),
)
```

**New columns Phase 2 adds** (per RESEARCH Runtime State Inventory + Pattern 5) — declare each in the existing style:
- `extraction_config: Mapped[dict | None]` — `mapped_column(JSONB, nullable=True)` (D-06)
- `compliance_record: Mapped[dict | None]` — `mapped_column(JSONB, nullable=True)` (D-03)
- `structural_fingerprint: Mapped[dict | None]` — `mapped_column(JSONB, nullable=True)` (D-09)
- `min_interval_seconds: Mapped[int | None]` — `mapped_column(nullable=True)` (D-08)
- `consecutive_failure_count: Mapped[int]` — `mapped_column(nullable=False, default=0, server_default="0")` (D-12)
- `last_successful_fetch_at: Mapped[datetime | None]` — `mapped_column(nullable=True)` (D-14)

**JSONB import** — copy from `change.py` line 29: `from sqlalchemy.dialects.postgresql import JSONB`. `source.py` does not currently import it.

**Docstring discipline** — every column is documented in the class docstring's `Columns` block (lines 19-39). New columns must be added there; this is a hard Phase 1 convention.

---

### `src/brm/models/change.py` (ORM model — MODIFIED)

**Analog:** itself — `src/brm/models/change.py` lines 1-122. Phase 2 adds the `change_identity` column (D-15) and a unique index.

**Index pattern to copy** (lines 70-72):
```python
Index("idx_change_status", "status"),
Index("idx_change_updated_at", "updated_at"),
```
Phase 2 adds a **unique** index/constraint on `change_identity`. Match the `idx_*` naming; for the uniqueness use `UniqueConstraint("change_identity", name="uq_change_identity")` in `__table_args__` (see the `uq_snapshot_source_version` example in `snapshot.py` line 37). RESEARCH (Pattern 7) suggests a *partial* unique index if `change_identity` is nullable for backfill — if so, that must be hand-written in the migration (autogenerate omits partial indexes; see migration analog below).

**New column** — `change_identity: Mapped[str | None]` typed `mapped_column(String, nullable=True)` to allow backfill of existing rows (RESEARCH Runtime State Inventory).

---

### `src/brm/models/change_observation.py` (ORM model — NEW)

**Analog:** `src/brm/models/snapshot.py` lines 1-57 — the closest model: a small append-only child table with FKs and a uniqueness constraint.

**Full pattern to copy** — module docstring with a `Columns` block; `__tablename__`; `__table_args__` with `ForeignKeyConstraint`-equivalent via `ForeignKey(...)` on columns plus an `Index`; `Mapped[...]` columns; a `__repr__`.

**FK pattern to copy** (from `change.py` lines 76-82): `mapped_column(ForeignKey("change.id"), nullable=False)`.

**Append-only / uniqueness pattern** (from `snapshot.py` lines 35-40):
```python
__table_args__ = (
    UniqueConstraint("source_id", "version", name="uq_snapshot_source_version"),
    Index("idx_snapshot_source_id", "source_id"),
)
```
`change_observation` columns per RESEARCH Pattern 7: `id` PK, `change_id` FK→change.id, `source_id` FK→source.id, `snapshot_id` FK→snapshot.id, `channel` (String), `observed_at` (datetime). Consider `UniqueConstraint("change_id", "source_id", "channel")` to prevent a duplicate observation row.

**Register it** — add `ChangeObservation` to `src/brm/models/__init__.py` (lines 1-6 pattern) so Alembic's `env.py` (`import brm.models`, line 28) sees the table.

---

### `alembic/versions/0002_*.py` (migration — NEW)

**Analog:** `alembic/versions/0001_initial_schema.py` lines 1-192 — the only migration in the repo; an exact template.

**Hand-written discipline (load-bearing)** — the 0001 docstring (lines 1-16) states the rule explicitly: *Alembic autogenerate routinely omits CheckConstraints and composite Indexes* (review finding #19). Phase 2's migration **must be hand-written**, not autogenerated. This matters acutely for: the updated `ck_source_health_status` CHECK (adding `'paused'`), the new partial unique index on `change_identity`, and the `change_observation` FKs.

**Metadata header to copy** (lines 26-29):
```python
revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None
```

**`add_column` with server defaults** — existing `source` rows need backfill (RESEARCH Runtime State Inventory). Pattern: `op.add_column("source", sa.Column("consecutive_failure_count", sa.Integer(), nullable=False, server_default="0"))`. Nullable JSONB/datetime columns add cleanly.

**CHECK-constraint swap pattern** — to add `'paused'`: `op.drop_constraint("ck_source_health_status", "source", type_="check")` then `op.create_check_constraint("ck_source_health_status", "source", "health_status IN ('unknown','healthy','failed','paused')")`.

**`create_table` pattern for `change_observation`** — copy the `op.create_table("change", ...)` block (lines 109-167): `sa.Column(...)`, `sa.ForeignKeyConstraint([...],[...], name="fk_...")`, `sa.PrimaryKeyConstraint("id")`, `sa.UniqueConstraint(...)`.

**`downgrade()` discipline** (lines 185-191) — must reverse every operation in strict LIFO order: drop indexes, drop new table, drop columns, restore the old CHECK constraint.

---

### `src/brm/lifecycle.py` (state-set module — MODIFIED)

**Analog:** itself — `src/brm/lifecycle.py` lines 63-67.

**Pattern to extend** (line 67):
```python
HEALTH_STATUSES: set[str] = {"unknown", "healthy", "failed"}   # → add "paused"
```
`HEALTH_STATUSES` is a **plain set**, not governed by `ALLOWED_TRANSITIONS` (which governs the `Change` lifecycle only). Adding `"paused"` is a one-line change here — but it has three coupled edits the planner must keep in sync: (1) this set, (2) the `ck_source_health_status` CHECK in `models/source.py` lines 43-46, (3) the same CHECK in the new migration. The lifecycle docstring's "Health status values" block (lines 18-22) must also document `paused`.

**Note on auto-pause transitions:** if Phase 2 wants `failed → paused` and `paused → healthy` to be *guarded* transitions, follow the `ALLOWED_TRANSITIONS` map + `assert_transition` pattern (lines 48-93). RESEARCH does not mandate this — `HEALTH_STATUSES` is currently an unguarded set — but the `assert_transition` pure-guard shape (lines 78-93) is the established pattern if the planner wants health-state guarding.

---

### `src/brm/config.py` (settings — MODIFIED)

**Analog:** itself — `src/brm/config.py` lines 10-33.

**Pattern to copy** — `Settings(BaseSettings)` with `model_config = SettingsConfigDict(env_file=".env", ...)`. Required secrets have **no default** (fail loud — docstring lines 14-16). Phase 2's `sentry_dsn` is *optional* (Pitfall 5 — missing DSN must be a no-op), so it gets a default:
```python
# Optional Sentry DSN — when unset, alerting degrades to a local-log no-op (Pitfall 5).
sentry_dsn: str | None = None
```
Add it as a new field on the existing `Settings` class; the module-level `settings = Settings()` singleton (line 37) is unchanged.

---

### `src/brm/ingest/adapter.py` (interface/seam — NEW, no analog)

**No analog exists.** RESEARCH.md asserts this is "EXISTING (Phase 1, unchanged)" — it is not; the `ingest/` directory is empty. Phase 2 must **create** the `SourceAdapter` Protocol.

**Use RESEARCH.md Pattern 1** (RESEARCH lines 280-297) as the spec: `class SourceAdapter(Protocol)` with `async def fetch(self, source: Source) -> FetchResult`.

**Conventions to carry from Phase 1** even without a code analog: module docstring with a design-rationale block (every Phase 1 module has one — see `db.py` lines 1-9, `lifecycle.py` lines 1-22); `from __future__`-free typed signatures using `Mapped`-style modern typing; `src/brm` absolute imports (`from brm.models import Source`), never relative.

---

### `src/brm/ingest/outcome.py` (enum + dataclass — NEW, no analog)

**Closest analog:** `src/brm/lifecycle.py` lines 24-42 — the pattern for "a small fixed vocabulary of string constants exposed as a module."

**Pattern to copy** — Phase 1 deliberately uses **string constants + a CHECK constraint**, *not* native `Enum`, so the taxonomy can grow without `ALTER TYPE` (see `change.py` docstring lines 4-6, `lifecycle.py` lines 28-42). Apply the same judgment to `FetchOutcome`: either string constants (`OUTCOME_CHANGED = "changed"`, etc.) or a `StrEnum` — match the lifecycle module's constant-list style (`ALL_STATUSES: list[str] = [...]`).

**`FetchResult` shape** — RESEARCH Pattern 2 (lines 299-312) specifies fields `outcome, content, raw_etag, raw_last_modified, error` plus a new `failure_reason: str | None` with a fixed vocabulary (`"drift"`, `"soft_404"`, `"login_wall"`, `"empty_region"`, `"selector_miss"`, `"transient"`, `"http_error"`). A frozen `@dataclass` is the right call; document the `failure_reason` vocabulary in the module docstring the way `lifecycle.py` documents its status values.

---

### `src/brm/ingest/html.py` (HTML adapter — NEW, no analog)

**No analog** — there is no RSS adapter to copy from (`ingest/rss.py` does not exist). Build from **RESEARCH Pattern 1 + Pattern 2 + Pattern 4** and the Code Examples (RESEARCH lines 448-515).

**Key spec points from RESEARCH:**
- Implements the `SourceAdapter` Protocol; `async def fetch(self, source: Source) -> FetchResult`.
- Config-driven and source-agnostic — *all* per-source behavior from `source.extraction_config` JSONB, never hard-coded (SRC-06; Anti-Pattern "Per-source parser code", RESEARCH line 376).
- httpx client with conditional-request headers and the exact UA string `"BankruptcyRuleMonitor/1.0 (+internal monitoring)"` (RESEARCH Code Example lines 484-498).
- Bounded retry with stdlib `asyncio.sleep` exponential backoff (RESEARCH Code Example lines 500-515) — **no `tenacity`** (RESEARCH Standard Stack decision).
- Tri-state classification: every failure mode → `FETCH_FAILED`, never `UNCHANGED` (RESEARCH Pattern 2, lines 299-312). Critical invariant: every path provably sets exactly one outcome.

**Phase 1 conventions to carry:** module-docstring rationale block; absolute `brm.*` imports; async-throughout (matches `db.py`'s `AsyncSession` design, lines 1-9).

---

### `src/brm/ingest/extract.py` / `fingerprint.py` / `failure_detect.py` (pure utilities — NEW)

**Closest analog for module *shape*:** `src/brm/lifecycle.py` — a pure module: top-level constants, one or two pure functions, a docstring explaining the rules, **no I/O, no DB, no async**. `failure_detect.py` in particular mirrors `lifecycle.py` almost exactly: a fixed marker vocabulary (like `ALL_STATUSES`) plus a classifier function (like `assert_transition`).

**Spec source:** RESEARCH Code Examples — `extract_region` (lines 449-466), `detect_soft_failure` (lines 469-482), `check_fingerprint` (lines 320-329). All three are explicitly *pure functions that run identically on fixtures and live data* (D-17) — no `if fixture:` branch (Anti-Pattern, RESEARCH line 379).

**Pure-guard signature pattern from `lifecycle.py`** (lines 78-93) — `assert_transition` shows the house style for a pure validation function: clear docstring with `Args`/`Raises`, explicit error type. `check_fingerprint` returning `tuple[bool, str | None]` is consistent with this.

---

### `src/brm/ingest/snapshot_store.py` (append-only DB write — NEW)

**No code analog** (`snapshot_store.py` does not exist) — but the **table it writes** (`src/brm/models/snapshot.py`) fully documents the contract.

**Critical constraints from the Snapshot model docstring** (`snapshot.py` lines 1-40): rows are INSERT-only; the `UNIQUE(source_id, version)` constraint (line 37) means `store_snapshot` must compute `version = max(version)+1` per source and **handle a concurrent-insert IntegrityError as a retryable hard error**, not silently (review finding #5, docstring lines 7-10). The `idx_snapshot_source_id` index (line 39) exists specifically to speed the `max(version)` lookup.

**Session pattern** — use `AsyncSession` per `db.py` (lines 1-9): one session per operation, never a module-level shared session, `expire_on_commit=False`.

---

### `src/brm/detect/identity.py` (pure utility — NEW)

**Closest analog for shape:** `src/brm/lifecycle.py` (pure module). 

**Spec source + highest-risk warning:** RESEARCH Pattern 7 (lines 367-373) and Pitfall 4 (lines 417-421). `identity.py` must be a **channel-independent** substantive-text normalization producing a `SHA-256` hash — separate from any per-channel `normalize()`. RESEARCH explicitly flags this as the highest-risk part of Phase 2: if feed-channel and scrape-channel text do not normalize to byte-identical strings, dedup silently fails. The planner must make this a pure, tested function with the D-17 feed+scrape fixture pair as its acceptance test (`change_identity(feed) == change_identity(scrape)` as a hard assertion).

**Hash primitive** — stdlib `hashlib.sha256`, the same primitive Phase 1 specified for `content_hash` (RESEARCH Don't Hand-Roll table).

---

### `src/brm/detect/detector.py` (event-driven DB write — NEW, no analog)

**No analog.** Build from RESEARCH Pattern 7 (lines 367-373) and the Architecture Diagram dedup block (lines 225-232).

**Flow spec:** compute `change_identity`; `SELECT ... WHERE change_identity = ?`; if found → insert a `change_observation` row only, return the existing `Change` (no second `Change`, D-16); if not found → insert `Change` + first `change_observation`.

**Conventions:** `AsyncSession` per `db.py`; the DB unique constraint on `change_identity` (see `change.py` analog above) is the real enforcement — the `SELECT`-then-insert is the application path, the constraint is the race backstop (same philosophy as `snapshot.py`'s `UNIQUE(source_id, version)`).

---

### `src/brm/health/staleness.py` (query service — NEW, no analog)

**No analog.** Build from RESEARCH Pattern 6 (lines 351-365) — the code example is given verbatim.

**Key correctness trap (D-14):** the query keys on `last_successful_fetch_at`, **never** `last_changed_at` (Anti-Pattern, RESEARCH line 378). Excludes `health_status == "paused"` sources (already escalated). Uses SQLAlchemy 2.x `select(...)` + `session.scalars(...)` — consistent with the `db.py` async-session model.

---

### `src/brm/health/alerts.py` (Sentry wrapper — NEW)

**Closest analog:** `src/brm/config.py` — the graceful-optional-config pattern. `config.py` distinguishes required secrets (no default, fail loud) from what Phase 2 needs here (optional, degrade gracefully).

**Spec:** RESEARCH Pitfall 5 (lines 423-427). `alerts.py` wraps `sentry_sdk` so a missing `SENTRY_DSN` is a no-op that logs locally instead — **the alert path must never raise into `run_ingest`**. Reads `settings.sentry_dsn` (the new optional field on `config.py`). `capture_message(..., level="warning")` for drift/staleness/auto-pause; `capture_exception` for unexpected errors.

---

### `src/brm/pipeline.py` / `run_pipeline.py` (orchestrator + CLI — NEW, no analog)

**No analog** — `run_ingest` does not exist; `pyproject.toml` line for `brm-run-pipeline = "brm.run_pipeline:main"` points at a missing module.

**Build from** RESEARCH Architecture Diagram (`run_ingest` box, lines 214-222) and the Tier note (lines 80-81): **no scheduler/worker** in Phase 2 — `run_ingest` is a directly-invokable async function triggered by CLI/test.

**Responsibilities per RESEARCH:** politeness `min_interval` gate before fetch (D-08); on `CHANGED` → `store_snapshot` + `detect_change`; on `UNCHANGED` → `health=healthy`, reset `consecutive_failure_count`, set `last_successful_fetch_at`; on `FETCH_FAILED` → `health=failed`, increment `consecutive_failure_count`, auto-pause at threshold (D-12); every outcome sets `last_checked_at`.

**Convention:** the `pyproject.toml` `[project.scripts]` entry expects a `main` callable in `brm.run_pipeline` — honor that path/name. Async entry: wrap in `asyncio.run(...)` (consistent with `alembic/env.py`'s async pattern and `conftest.py`).

---

### `src/brm/seed.py` (seed script — NEW)

**Closest analog:** `tests/test_models.py::make_source` (lines 25-37) — the only existing example of constructing a `Source` row with all required fields.

**Pattern to copy** — the field set from `make_source`: `jurisdiction`, `layer`, `feed_url`, `ingestion_method`, `adapter_ref`, `polling_cadence`, `health_status`. Phase 2's pilot HTML source row adds the new JSONB columns (`extraction_config` with `content_selector=".field--name-body"` per RESEARCH Pilot Source table, `compliance_record`, `structural_fingerprint`, `min_interval_seconds`). Onboarding the pilot is a **config-only DB insert** — no code change (SRC-06, D-06).

---

### `tests/test_*.py` Phase 2 suites (tests — exact analog)

**Analogs:** `tests/conftest.py`, `tests/test_models.py`, `tests/test_lifecycle.py`.

**DB-test pattern** — use the `db_session` fixture (`conftest.py` lines 82-121): SAVEPOINT-rollback isolation, `@pytest.mark.asyncio`, `await db_session.flush()`, assert on persisted attributes. CHECK-constraint tests use `pytest.raises((IntegrityError, Exception))` (`test_models.py` lines 77-83, 227-253) — Phase 2 reuses this for the updated `health_status` CHECK and the `change_identity` unique constraint.

**Pure-logic test pattern** — `test_lifecycle.py` (no DB, no `asyncio` marker) is the model for testing `extract.py` / `fingerprint.py` / `failure_detect.py` / `identity.py`: one assertion-focused test per rule, allowed + forbidden cases paired.

**HTTP-replay pattern** — the `mock_http` fixture (`conftest.py` lines 129-144) is a `respx` router, already wired for offline fetch-adapter tests. Phase 2's HTML-fixture replay (D-17) uses it: `mock_http.get(url).mock(return_value=httpx.Response(200, content=FIXTURE_HTML))`.

**Helper-factory pattern** — `make_source(**kwargs)` with a `defaults` dict (`test_models.py` lines 25-37) is the established way to build test rows; Phase 2 test files should add an analogous `make_html_source(...)` carrying the new JSONB config.

---

## Shared Patterns

### ORM column declaration
**Source:** `src/brm/models/source.py` lines 49-78, `change.py` lines 75-118.
**Apply to:** every modified/new model file.
```python
some_col: Mapped[str | None] = mapped_column(String, nullable=True)
count_col: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0")
ts_col: Mapped[datetime] = mapped_column(
    nullable=False, default=datetime.utcnow, server_default="now()",
)
jsonb_col: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
```
Defaults are declared **twice** (Python `default=` + DB `server_default=`). Every column is documented in the class docstring's `Columns` block. Every new model is registered in `models/__init__.py`.

### CHECK constraint kept in three places
**Source:** `models/source.py` lines 42-47, `alembic/versions/0001_initial_schema.py` lines 64-67, `lifecycle.py` line 67.
**Apply to:** the `health_status` `'paused'` addition.
A status vocabulary lives in **three coupled locations** — the `HEALTH_STATUSES` set, the model `CheckConstraint`, and the migration `CheckConstraint`. Changing one without the others is a latent bug. The planner must list all three edits in the same plan step.

### Hand-written Alembic migrations
**Source:** `alembic/versions/0001_initial_schema.py` lines 1-16, 185-191.
**Apply to:** the `0002` migration.
Never autogenerate — autogenerate drops CheckConstraints and composite/partial indexes (review finding #19). Write `upgrade()` and a strict-LIFO `downgrade()` by hand. `revision`/`down_revision` chain: `"0002"` / `"0001"`.

### Pure module of constants + classifier function
**Source:** `src/brm/lifecycle.py` (whole file).
**Apply to:** `outcome.py`, `failure_detect.py`, `fingerprint.py`, `extract.py`, `identity.py`.
Top-level constants (fixed vocabularies), small pure functions, a docstring stating the rules, explicit custom exception types, `Args`/`Raises` docstrings. No I/O, no DB, no async, no `if fixture:` branch.

### Async session usage
**Source:** `src/brm/db.py` lines 1-67.
**Apply to:** `snapshot_store.py`, `detector.py`, `staleness.py`, `pipeline.py`.
One `AsyncSession` per operation; never a module-level shared session; `expire_on_commit=False`; psycopg-3 async driver. SQLAlchemy 2.x `select(...)` + `await session.scalars(...)`.

### Optional-config graceful degradation
**Source:** `src/brm/config.py` lines 10-33 (required-secret-no-default discipline, inverted for optional).
**Apply to:** `config.py` `sentry_dsn` field and `health/alerts.py`.
Required secrets have no default (fail loud); the new `sentry_dsn` is optional (`= None`) and a missing value degrades the alert path to a local-log no-op — alerting must never crash ingest (Pitfall 5).

### Module docstring rationale block
**Source:** every Phase 1 module — `db.py` lines 1-9, `lifecycle.py` lines 1-22, `snapshot.py` lines 1-10, `0001_initial_schema.py` lines 1-16.
**Apply to:** every new Phase 2 module.
Each module opens with a docstring stating *what* it is and *why* the key design decisions were made (often citing a requirement ID or review finding). This is a strong, consistent Phase 1 convention.

### Test isolation & fixtures
**Source:** `tests/conftest.py` lines 82-121 (`db_session`), 129-144 (`mock_http`).
**Apply to:** all Phase 2 test files.
SAVEPOINT-rollback `db_session` for DB tests; `respx` `mock_http` router for offline HTTP replay; `@pytest.mark.asyncio`; `make_*` helper factories with a `defaults` dict.

## No Analog Found

Files with no close match — planner should build from RESEARCH.md patterns (cited), applying the Shared Patterns above for house style:

| File | Role | Data Flow | Reason | RESEARCH spec |
|------|------|-----------|--------|---------------|
| `src/brm/ingest/adapter.py` | interface/seam | request-response | No `SourceAdapter` Protocol exists; Phase 1 never built the ingest layer | Pattern 1 (lines 280-297) |
| `src/brm/ingest/html.py` | adapter | request-response | No RSS adapter to mirror; `ingest/` is empty | Patterns 1, 2, 4 + Code Examples (449-515) |
| `src/brm/ingest/snapshot_store.py` | service | append-only CRUD | No store code exists | Snapshot model docstring contract |
| `src/brm/detect/detector.py` | service | event-driven | No detector code exists | Pattern 7 (367-373) |
| `src/brm/health/staleness.py` | service | batch/read | No `health/` package exists | Pattern 6 (351-365) |
| `src/brm/pipeline.py` / `run_pipeline.py` | orchestrator + CLI | event-driven | `run_ingest` never built; `pyproject.toml` script entry dangling | Architecture Diagram (214-222), Tier note (80-81) |
| `tests/fixtures/html/*.html` | test fixture | n/a | No `tests/fixtures/` directory exists | D-17 — 6 fixtures (clean, drift, soft-404, login-wall, empty, dedup pair) |

## Metadata

**Analog search scope:** `src/brm/**`, `tests/**`, `alembic/versions/**`, `pyproject.toml`, `alembic/env.py`
**Files scanned:** 14 source/test/migration files (the entire current codebase)
**Pattern extraction date:** 2026-05-22
**Key structural finding:** Phase 1 delivered plan 01-01 only (domain foundation). The ingest/detect/pipeline layers RESEARCH.md treats as "existing" do not exist — Phase 2 must create the `SourceAdapter` seam, tri-state contract, snapshot store, detector, and orchestrator from scratch.
