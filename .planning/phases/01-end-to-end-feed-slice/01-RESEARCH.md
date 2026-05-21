# Phase 1: End-to-End Feed Slice - Research

**Researched:** 2026-05-20
**Domain:** RSS ingestion → change detection → LLM summarization → human review → pull API (vertical MVP slice / walking skeleton)
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** The slice is seeded with the **Federal Rules of Bankruptcy Procedure (FRBP)** rule family — not the Bankruptcy Code (Title 11) or Official Forms. Rationale: the uscourts.gov rulemaking area is the most genuinely feed-shaped national source, and rule-text changes are exactly the human-review tier this slice is built to prove.
- **D-02:** The exact FRBP feed URL/endpoint is a research task — the *layer choice* (FRBP) is locked; the *specific feed* is for research to confirm. **(Resolved below — see "FRBP Feed Identification".)**
- **D-03:** The slice is proven via **fixture replay**: capture a real FRBP feed snapshot, then a modified copy, and run change detection against the pair. Deterministic, demoable any time, doubles as the regression-test fixture.
- **D-04:** Live polling against the real feed still runs **in parallel** with the fixture path. Detection logic must run identically on fixture and live snapshots — **no production-only code branch, no synthetic-injection backdoor.**
- **D-05:** The AI summary is **structured fields**, not free-form prose: a one-line **headline** + a 1–3-sentence block answering **"What changed / Where / To whom / For what cases"**.
- **D-06:** Depth is **concise** — 1–3 sentences. The reviewer reads the verbatim diff for detail; the summary is the gist only.
- **D-07:** Prompt hard guardrails: do NOT speculate about practical impact beyond the explicit rule text; do NOT phrase output as advice.
- **D-08:** Every summary carries the **"informational / not legal advice"** label (AI-06).
- **D-09:** The structured summary is stored as **JSONB**. The review UI renders the headline in the queue list with the detail block expandable per row.
- **D-10:** The review queue supports **approve / edit / reject** — all three (full ROUTE-04). Reject marks a detected change as not-a-real-change / noise.
- **D-11:** "Edit" in this slice means correcting the **AI summary** (the only AI output in Phase 1).
- **D-12:** The **effective date** is entered by the reviewer during review. The field is nullable until then; the reviewer is the authoritative source of truth for it in Phase 1.

### Claude's Discretion

- The specific FRBP feed URL (per D-02) — researcher selects the most reliable real feed. **(Recommendation made below.)**
- Review UI access model (open internal tool vs login-gated) and reviewer-identity capture — planner/researcher may choose a sensible minimal default for an internal-only v1 tool; full reviewer attribution / audit trail is explicitly Phase 8 (AUDIT-02). **Do not over-build auth here.**
- API response shape, snapshot retention policy, and diff-rendering library details — standard approaches per the locked stack in CLAUDE.md.

### Deferred Ideas (OUT OF SCOPE)

- **AI date-hint for effective date** — surfacing an AI-noticed date phrase as a non-authoritative reviewer hint. A quick win to layer on *after* the Phase 1 baseline works. Revisit at end of Phase 1 or in Phase 5.
- Review UI access/auth model and full reviewer-identity attribution — full audit trail with reviewer identity is Phase 8 (AUDIT-02).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SRC-01 | Source registry: one record per source — jurisdiction, layer, feed URL, ingestion method, adapter ref, cadence, last-checked, last-changed, health status | Domain model in plan 01-01; columns enumerated in "Architecture Patterns → Domain Model" |
| SRC-02 | v1 covers the national layer (Title 11, FRBP, Official Forms) | Phase 1 seeds exactly one national FRBP source; SRC-02 fully satisfied later, partially here |
| INGEST-01 | Ingest changes from RSS and official notice feeds | `feedparser` 6.0.12 + `httpx` 0.28.1 fetch pattern; "RSS Fetcher Adapter" |
| INGEST-04 | Every fetch resolves to tri-state CHANGED / UNCHANGED / FETCH_FAILED | "Tri-State Fetch Outcome" pattern — exception taxonomy + 304 handling |
| INGEST-05 | Each successful fetch stores a versioned snapshot | "Append-Only Snapshot Store" pattern |
| DETECT-01 | Detect substantive changes; ignore boilerplate/nav/timestamps | Normalization step before hashing; `difflib` diff; "Hash-Gate + Textual Diff" |
| DETECT-02 | Content-hash gate prevents unchanged content triggering downstream work | SHA-256 over normalized content; gate logic |
| AI-01 | AI identifies what substantively changed between old and new text | Anthropic Messages API single-turn call grounded on verbatim diff |
| AI-03 | AI writes a plain-language summary | Structured-output call producing D-05 fields |
| AI-06 | Every AI summary labeled informational / "not legal advice" | Label is a server-set field, NOT model-generated (see "AI Summary" pitfall) |
| ROUTE-03 | Web review queue shows AI summary, diff, source link, snapshot, effective date | React/Vite review queue; Phase 1 subset of ROUTE-03 fields |
| ROUTE-04 | Reviewer can approve / reject / edit | D-10/D-11 — three actions; edit = correct summary |
| EFF-01 | Records detected date and effective date as separate fields | Change model: `detected_at`, `effective_date` (nullable), distinct columns |
| EFF-02 | Change progresses through a lifecycle state machine | Status enum + allowed-transition guard; Phase 1 subset of states |
| API-01 | Pull-based read API exposes only verified changes | FastAPI read-only endpoint filtering `status = verified` |
| API-07 | Monitor integrates with the other product via API only — no shared DB | The FastAPI pull endpoint is the only integration seam; no DB credentials shared |
</phase_requirements>

## Summary

Phase 1 is a walking skeleton: build the thinnest end-to-end vertical slice of the Bankruptcy Rule Monitor — project scaffold, one real RSS source ingested, one real DB read/write per stage, one real reviewer UI interaction, and a pull API — using the fully locked stack in `CLAUDE.md`. There is no application code yet; this phase *establishes* every foundational pattern (domain models, source-adapter interface, snapshot store, hash-gate, lifecycle state machine, AI-call wrapper, review UI, pull API).

The single highest-value research finding concerns the seed feed (D-02). The uscourts.gov rulemaking area (`/forms-rules/pending-rules-and-forms-amendments`) is **a static HTML page with no RSS/Atom feed** — only an email-subscription form. The only real, verified RSS feed uscourts.gov publishes is the **general Judiciary News feed at `https://www.uscourts.gov/news/rss`** (valid RSS 2.0, channel "Judiciary News - United States Courts"). Bankruptcy rule amendments *do* surface in this feed (e.g., the May 2026 item on the Federal Rules of Evidence), but it is a general news feed, not a rules-only feed. This is a real ecosystem constraint, not a gap in research — and it must shape the plan: **the seed Source row points at the Judiciary News RSS feed; the slice is validated via fixture replay (D-03) precisely because the live feed is general-purpose and FRBP amendments land only ~once a year (effective Dec 1).**

Anthropic structured outputs are now **GA** (no beta header) with native Pydantic support via `client.messages.parse()` — this is the correct mechanism for the D-05 structured summary and eliminates JSON-parsing retry loops. Every other stack choice (FastAPI, SQLAlchemy 2.0 async, Alembic, feedparser, httpx, React 19 + Vite + TanStack Query + `react-diff-viewer-continued`) is verified current and compatible.

**Primary recommendation:** Seed the registry with the **Judiciary News RSS feed (`https://www.uscourts.gov/news/rss`)** as the FRBP-layer source; build detection identically on fixture and live snapshots (one code path, fixtures are just stored snapshots); use `client.messages.parse()` with a Pydantic schema for the AI summary; keep the review UI an unauthenticated internal tool with a free-text `reviewer_name` field (no real auth — that is Phase 8).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| RSS fetch + conditional GET | API/Backend (worker-style code, run synchronously in Phase 1) | — | Network I/O + ETag bookkeeping belongs server-side; no scheduler yet (Procrastinate is Phase 4) |
| Snapshot persistence | Database/Storage | API/Backend | Append-only snapshot rows in Postgres; content as text/JSONB |
| Hash-gate + textual diff | API/Backend | — | Deterministic CPU work; `difflib` is stdlib, runs in-process |
| AI summary call | API/Backend | External (Anthropic API) | Single-turn Messages API call; the only external service dependency |
| Lifecycle state transitions | API/Backend | Database/Storage | Status enum + transition guard enforced in service layer + DB constraint |
| Review queue rendering | Browser/Client | Frontend (Vite SPA) | Authenticated-free internal SPA; TanStack Query for server state |
| Approve / edit / reject actions | API/Backend | Browser/Client | Mutations hit FastAPI; optimistic UI via TanStack Query |
| Pull delivery API | API/Backend | — | Read-only FastAPI endpoint; the ONLY integration seam (API-07) |

**Tier note:** Phase 1 has *no* scheduler/worker process. Procrastinate (the Postgres task queue) is locked in `CLAUDE.md` but its first use is **Phase 4** (per ROADMAP). In Phase 1, fetch/detect/summarize run as **directly-invokable functions** (triggered by a CLI command, test, or a manual FastAPI admin endpoint). Do not stand up a Procrastinate worker in Phase 1 — that is scope creep against the roadmap.

## FRBP Feed Identification (D-02 — resolved)

**Recommendation:** Seed the source registry with the **uscourts.gov Judiciary News RSS feed**.

| Property | Value |
|----------|-------|
| Feed URL | `https://www.uscourts.gov/news/rss` `[VERIFIED: fetched 2026-05-20, valid RSS 2.0]` |
| Format | RSS 2.0 with Dublin Core (`dc:`) namespace `[VERIFIED: fetched]` |
| Channel title | "Judiciary News - United States Courts" `[VERIFIED: fetched]` |
| Item fields | title, link (permalink), description/summary, pubDate, dc:creator, guid `[VERIFIED: fetched]` |
| Aliases (all 301/302 redirect here) | `https://news.uscourts.gov/feed`, `https://www.uscourts.gov/feed` `[VERIFIED: redirect chain followed 2026-05-20]` |
| Update cadence | Irregular — general judiciary news; multiple items/month, but FRBP-specific items are rare `[VERIFIED: feed contents — May/Apr/Mar 2026 items observed]` |
| Stability | Long-standing official feed; uscourts.gov has published RSS since ~2012 `[CITED: uscourts.gov/data-news/judiciary-news/2012/04/16/feed-need]` |

**Critical caveat for the planner:** This is **not** a rules-specific feed. The uscourts.gov rulemaking pages themselves carry **no RSS/Atom feed** — `https://www.uscourts.gov/forms-rules/pending-rules-and-forms-amendments` is a static HTML page with only an email-subscription form `[VERIFIED: fetched 2026-05-20]`. Consequences for Phase 1:

1. The seed Source row's `layer` is **FRBP** (locked by D-01) even though the *feed* is general judiciary news. The registry models a source's *subject layer* independent of feed breadth — this is honest and forward-compatible (Phase 2 adds HTML scraping of the rulemaking page itself as a second FRBP source).
2. FRBP amendments follow a fixed annual rhythm: proposed amendments transmitted by the Supreme Court in spring, **effective December 1** each year `[CITED: uscourts.gov rulemaking process — "about three years"; Dec 1 effective dates confirmed for 2024/2025/2026]`. The live feed will almost certainly be *quiet on FRBP* during the Phase 1 build (May 2026). This is exactly why D-03 mandates fixture replay.
3. As of research date, the rulemaking page lists FRBP amendments effective **Dec 1, 2026** (Rules 1007, 3018, 5009, 9006, 9014, 9017, new Rule 7043) and **Dec 1, 2027** (Rule 2002, Forms 101 & 106C) `[VERIFIED: fetched pending-amendments page 2026-05-20]` — useful realistic fixture material.

**Alternative considered:** A district bankruptcy court news feed (e.g., `nvb.uscourts.gov/news-rss/`) — rejected: district feeds are district-layer, contradicting the locked FRBP layer choice (D-01), and add no value over the national feed for a one-source slice.

## Standard Stack

All choices are LOCKED in `CLAUDE.md` — versions below are **verified current on PyPI/npm as of 2026-05-20**. Do not re-litigate; this table confirms currency and pins versions.

### Core (backend)
| Library | Verified Version | Purpose | Why Standard |
|---------|------------------|---------|--------------|
| Python | 3.12 | Backend language | Locked; production-safe default |
| FastAPI | 0.136.1 `[VERIFIED: PyPI]` | API framework — pull API + review-UI backend | Async-native, OpenAPI schema, Pydantic v2 |
| Uvicorn | 0.47.0 `[VERIFIED: PyPI]` | ASGI server | Standard FastAPI server. CLAUDE.md says 0.34.x — **0.47.0 is current**; planner should pin latest |
| SQLAlchemy | 2.0.49 `[VERIFIED: PyPI]` | ORM (async style) | Pairs with FastAPI async |
| Alembic | 1.18.4 `[VERIFIED: PyPI]` | Schema migrations | Versioned, reviewable migrations |
| Pydantic | 2.13.4 `[VERIFIED: PyPI]` | Validation, settings, LLM-output schemas | API contract + structured-output schema |
| psycopg | 3.3.4 `[VERIFIED: PyPI]` | Postgres driver (`psycopg[binary]`) | psycopg 3 for async SQLAlchemy |
| anthropic | 0.103.1 `[VERIFIED: PyPI]` | LLM SDK — diff summarization | Official typed SDK; `messages.parse()` for structured output |
| feedparser | 6.0.12 `[VERIFIED: PyPI]` | RSS/Atom parsing | Robust against malformed feeds; built-in ETag/Modified support |
| httpx | 0.28.1 `[VERIFIED: PyPI]` | Async HTTP client | Conditional requests, HTTP/2, timeouts |
| difflib | stdlib | Cheap deterministic textual diff | No dependency; produces reviewer-facing unified diff |

### Core (frontend — review UI)
| Library | Verified Version | Purpose | Why Standard |
|---------|------------------|---------|--------------|
| React | 19.x | Review-queue SPA | Locked |
| Vite | 6.x | Build tool / dev server | Locked; lighter than Next for an internal tool |
| TypeScript | 5.x | Type safety vs OpenAPI contract | Locked |
| TanStack Query | 5.100.11 `[VERIFIED: npm; peer react ^18 || ^19]` | Server state — queue polling, optimistic approve/reject | Locked |
| react-diff-viewer-continued | 4.2.2 `[VERIFIED: npm; peerDeps include react ^19.0.0]` | Side-by-side old-vs-new rule text | Locked; **React 19 supported** — see Pitfalls |
| shadcn/ui + Tailwind | current | Tables, dialogs, badges, approve/reject controls | Locked; copy-in components |

### Supporting / Dev Tools
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| uv | latest | Python deps + venv + lockfile | Project setup (replaces pip/poetry) |
| Ruff | latest | Lint + format | One tool for both |
| pytest + pytest-asyncio | latest | Testing — async services + adapters | All test code |
| respx | latest (httpx-native) | Mock httpx in tests — replay feed responses offline | Fixture-based fetch tests |
| Docker + docker-compose | latest | Local Postgres 16 | Dev DB; planner must include since Postgres is not installed locally |

### Alternatives Considered
| Instead of | Could Use | Tradeoff / Verdict |
|------------|-----------|--------------------|
| `messages.parse()` + Pydantic | Tool-use forced JSON / prompt "respond JSON only" | Structured outputs are now GA and strictly better — guaranteed schema-valid, no retry loop. Use `parse()`. |
| Procrastinate worker in Phase 1 | Direct function calls / manual trigger | Procrastinate is locked but first used Phase 4. Phase 1 = direct calls. Do NOT add the worker now. |
| `react-diff-viewer-continued` | shadcn diff blocks / `assistant-ui` diff viewer | Locked choice works with React 19; no reason to deviate. |

**Installation (backend — uv):**
```bash
uv init && uv add fastapi==0.136.1 "uvicorn[standard]==0.47.0" \
  "sqlalchemy==2.0.49" alembic==1.18.4 "psycopg[binary]==3.3.4" \
  pydantic==2.13.4 pydantic-settings anthropic==0.103.1 \
  feedparser==6.0.12 httpx==0.28.1
uv add --dev ruff pytest pytest-asyncio respx
```

**Installation (frontend — npm, in a separate `web/` package):**
```bash
npm create vite@latest web -- --template react-ts
npm install @tanstack/react-query@5.100.11 react-diff-viewer-continued@4.2.2
# shadcn/ui + tailwind set up per the shadcn CLI
```

## Package Legitimacy Audit

> All packages are drawn directly from the LOCKED stack in `CLAUDE.md` (an authoritative project document), not discovered via web search. Versions verified against the correct ecosystem registry on 2026-05-20.

| Package | Registry | Verified Version | slopcheck | Disposition |
|---------|----------|------------------|-----------|-------------|
| fastapi | PyPI | 0.136.1 | n/a (unavailable) | Approved — CLAUDE.md locked |
| uvicorn | PyPI | 0.47.0 | n/a | Approved — CLAUDE.md locked |
| sqlalchemy | PyPI | 2.0.49 | n/a | Approved — CLAUDE.md locked |
| alembic | PyPI | 1.18.4 | n/a | Approved — CLAUDE.md locked |
| pydantic | PyPI | 2.13.4 | n/a | Approved — CLAUDE.md locked |
| psycopg | PyPI | 3.3.4 | n/a | Approved — CLAUDE.md locked |
| anthropic | PyPI | 0.103.1 | n/a | Approved — CLAUDE.md locked, official Anthropic SDK |
| feedparser | PyPI | 6.0.12 | n/a | Approved — CLAUDE.md locked |
| httpx | PyPI | 0.28.1 | n/a | Approved — CLAUDE.md locked |
| @tanstack/react-query | npm | 5.100.11 | n/a | Approved — CLAUDE.md locked; no postinstall script |
| react-diff-viewer-continued | npm | 4.2.2 | n/a | Approved — CLAUDE.md locked; no postinstall script |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

*slopcheck was not installable in this environment. Mitigating factors that justify `[VERIFIED: registry]` rather than `[ASSUMED]`: (1) every package is named in the project's own LOCKED `CLAUDE.md`, an authoritative source — not discovered via web search; (2) each was confirmed to exist at a current version on the correct ecosystem registry; (3) npm packages were checked for `postinstall` scripts (none present); (4) `anthropic` is Anthropic's first-party SDK. The planner need not add `checkpoint:human-verify` gates for these specific packages, but should still review the generated lockfile.*

## Architecture Patterns

### System Architecture Diagram

```
                          ┌─────────────────────────────────────┐
   FIXTURE PATH (D-03)     │   LIVE PATH (D-04) — runs in parallel│
   stored snapshot pair    │   uscourts.gov Judiciary News RSS    │
        │                  │   https://www.uscourts.gov/news/rss  │
        │                  └──────────────┬──────────────────────┘
        │                                 │ httpx GET (ETag / If-Modified-Since)
        │                                 ▼
        │                  ┌──────────────────────────────┐
        │                  │  RSS Fetcher Adapter          │
        │                  │  → feedparser.parse(bytes)    │
        │                  │  → outcome: CHANGED /         │
        │                  │    UNCHANGED / FETCH_FAILED   │
        │                  └──────────────┬───────────────┘
        │                                 │ on CHANGED/first-fetch
        │                                 ▼
        │                  ┌──────────────────────────────┐
        │                  │  Append-Only Snapshot Store   │
        │                  │  (snapshot row: content,      │
        │                  │   content_hash, fetched_at)   │
        │                  └──────────────┬───────────────┘
        └────────────────────────────────►│  (fixture = pre-stored snapshot rows;
            SAME CODE PATH — no branch     │   identical downstream processing)
                                           ▼
                            ┌──────────────────────────────┐
                            │  Hash-Gate + Diff             │
                            │  normalize → SHA-256          │
                            │  hash == prior?  → STOP       │
                            │  hash != prior?  → difflib    │
                            │    unified diff → Change row  │
                            │    (status = detected)        │
                            └──────────────┬───────────────┘
                                           ▼
                            ┌──────────────────────────────┐
                            │  AI Summary (Anthropic)       │
                            │  messages.parse() over the    │
                            │  verbatim diff → JSONB summary│
                            │  status: detected → processed │
                            └──────────────┬───────────────┘
                                           ▼
                            ┌──────────────────────────────┐
                            │  PostgreSQL 16                │
                            │  source · snapshot · change   │
                            └──────┬──────────────────┬─────┘
                  read pending     │                  │  read verified
                                   ▼                  ▼
                  ┌────────────────────────┐  ┌──────────────────────┐
                  │ FastAPI review backend │  │ FastAPI pull API     │
                  │ GET /review/queue      │  │ GET /changes         │
                  │ POST .../approve|edit  │  │  (status=verified)   │
                  │      |reject           │  │ ← the ONLY seam      │
                  └───────────┬────────────┘  │   (API-07, no shared │
                              ▼               │   DB)                │
                  ┌────────────────────────┐  └──────────┬───────────┘
                  │ React/Vite review SPA  │             ▼
                  │ TanStack Query · diff  │     "the other product"
                  │ viewer · approve/edit/ │
                  │ reject                 │
                  └────────────────────────┘
```

### Recommended Project Structure
```
/                          # repo root (C:\data\cc)
├── pyproject.toml          # uv-managed backend
├── docker-compose.yml      # local Postgres 16
├── alembic.ini
├── alembic/versions/       # migrations
├── src/brm/                # "Bankruptcy Rule Monitor" backend package
│   ├── db.py               # async engine, session factory
│   ├── models/             # SQLAlchemy ORM — source.py, change.py, snapshot.py
│   ├── schemas/            # Pydantic — API contracts + AI-summary schema
│   ├── ingest/
│   │   ├── adapter.py      # SourceAdapter protocol/ABC
│   │   ├── rss.py          # RSS fetcher adapter (httpx + feedparser)
│   │   └── outcome.py      # FetchOutcome enum + result dataclass
│   ├── detect/
│   │   ├── normalize.py    # content normalization (boilerplate stripping)
│   │   └── diff.py         # hash-gate + difflib unified diff
│   ├── ai/
│   │   └── summarize.py    # Anthropic messages.parse() wrapper
│   ├── lifecycle.py        # status enum + allowed-transition guard
│   ├── api/
│   │   ├── review.py       # review-queue endpoints (queue, approve, edit, reject)
│   │   └── pull.py         # pull delivery API (verified changes)
│   └── seed.py             # seeds the one FRBP source row
├── tests/
│   ├── fixtures/           # captured FRBP feed snapshot + modified copy (D-03)
│   ├── conftest.py         # async DB fixture, respx fixture
│   └── test_*.py
└── web/                    # React/Vite review SPA (separate npm package)
    └── src/
```

### Pattern 1: Source-Adapter Interface
**What:** A `SourceAdapter` protocol/ABC with a single `fetch(source) -> FetchResult` method. Phase 1 has one implementation (`RssAdapter`); Phase 2 adds `HtmlAdapter`, Phase 3 `PdfAdapter`. Establish the seam now even with one adapter.
**When to use:** Any source ingestion. The Source row carries an `ingestion_method` / `adapter_ref` column (SRC-01) that selects the adapter.
**Example:**
```python
# Source: pattern derived from CLAUDE.md "source-adapter interface"; structure standard
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

class FetchOutcome(str, Enum):
    CHANGED = "changed"
    UNCHANGED = "unchanged"
    FETCH_FAILED = "fetch_failed"

@dataclass
class FetchResult:
    outcome: FetchOutcome
    content: str | None          # normalized snapshot content; None on UNCHANGED/FAILED
    raw_etag: str | None
    raw_last_modified: str | None
    error: str | None            # populated only on FETCH_FAILED

class SourceAdapter(Protocol):
    async def fetch(self, source: "Source") -> FetchResult: ...
```

### Pattern 2: Tri-State Fetch Outcome (INGEST-04)
**What:** Every fetch resolves to exactly one of CHANGED / UNCHANGED / FETCH_FAILED. A silent failure must never read as "no change."
**When to use:** All fetch logic.
**Rules:**
- HTTP 304 (Not Modified, from `If-None-Match`/`If-Modified-Since`) → `UNCHANGED`.
- HTTP 200 + content hash equal to last snapshot → `UNCHANGED`.
- HTTP 200 + content hash differs → `CHANGED`.
- Network error, timeout, non-2xx/304 status, `feedparser` `bozo` parse failure on otherwise-empty result, or zero-length body → `FETCH_FAILED` (with `error` set).
- `feedparser` sets `bozo=1` on *malformed but partially parseable* feeds — treat `bozo` as a warning, not an automatic failure: if entries were still parsed, proceed; only fail if no usable content resulted.
**Example:**
```python
# Source: feedparser conditional-GET docs + httpx; structure standard
import hashlib, httpx, feedparser

async def fetch_rss(source) -> FetchResult:
    headers = {}
    if source.last_etag:           headers["If-None-Match"] = source.last_etag
    if source.last_modified_http:  headers["If-Modified-Since"] = source.last_modified_http
    headers["User-Agent"] = "BankruptcyRuleMonitor/1.0 (+internal monitoring)"
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as c:
            resp = await c.get(source.feed_url, headers=headers)
    except (httpx.HTTPError, httpx.TimeoutException) as e:
        return FetchResult(FetchOutcome.FETCH_FAILED, None, None, None, str(e))
    if resp.status_code == 304:
        return FetchResult(FetchOutcome.UNCHANGED, None, source.last_etag,
                           source.last_modified_http, None)
    if resp.status_code != 200 or not resp.content:
        return FetchResult(FetchOutcome.FETCH_FAILED, None, None, None,
                           f"HTTP {resp.status_code}, {len(resp.content)} bytes")
    parsed = feedparser.parse(resp.content)
    if parsed.bozo and not parsed.entries:
        return FetchResult(FetchOutcome.FETCH_FAILED, None, None, None,
                           f"unparseable feed: {parsed.bozo_exception!r}")
    content = normalize(parsed)             # see detect/normalize.py
    new_hash = hashlib.sha256(content.encode()).hexdigest()
    outcome = (FetchOutcome.UNCHANGED if new_hash == source.last_content_hash
               else FetchOutcome.CHANGED)
    return FetchResult(outcome, content,
                       resp.headers.get("ETag"),
                       resp.headers.get("Last-Modified"), None)
```

### Pattern 3: Append-Only Snapshot Store (INGEST-05)
**What:** Each successful fetch with new content inserts a new immutable `snapshot` row — never updates. Snapshots are versioned by `created_at` + a monotonic `version` per source. The Change row references the prior and current snapshot.
**When to use:** Every CHANGED outcome (and the first-ever fetch of a source).
**Rules:**
- `snapshot` rows are INSERT-only; no UPDATE/DELETE in normal operation.
- Store `content` (normalized text) and `content_hash`; optionally store `raw_content` for the reviewer's "snapshot" link (ROUTE-03). MVP: storing normalized content is sufficient.
- Retention policy is Claude's discretion — for Phase 1, keep all snapshots (volume is trivial: one source, ~annual real changes).

### Pattern 4: Hash-Gate + Textual Diff (DETECT-01, DETECT-02)
**What:** Before any LLM call, normalize content, hash it, and gate. Only a hash difference produces a `difflib` unified diff and a `detected` Change row.
**When to use:** Every fetch that yields content.
**Normalization (DETECT-01 — ignore boilerplate/nav/timestamps):** For an RSS feed in Phase 1, normalization is light — extract item titles + summaries + links into a stable canonical text, strip `pubDate`/`lastBuildDate` timestamps and feed-generator chrome that change without substance. Keep normalization in `detect/normalize.py` as a pure function so it is identically applied to fixture and live content.
**Diff:** `difflib.unified_diff` over the prior vs current normalized content produces the verbatim textual diff stored on the Change row and rendered by `react-diff-viewer-continued`.
```python
# Source: Python stdlib difflib + hashlib
import difflib, hashlib

def content_hash(normalized: str) -> str:
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

def textual_diff(old: str, new: str) -> str:
    return "".join(difflib.unified_diff(
        old.splitlines(keepends=True), new.splitlines(keepends=True),
        fromfile="previous", tofile="current"))
```

### Pattern 5: Lifecycle State Machine (EFF-02)
**What:** The Change row carries a `status` enum. EFF-02 names the full lifecycle (`detected → classified → (review | auto-routed) → verified → active | pending-effective → superseded`). **Phase 1 implements only the subset reachable without classification/scheduler:**
`detected → processed → in_review → verified` (plus terminal `rejected`).
- `detected` — diff produced, Change created.
- `processed` — AI summary attached (D-04 wording; ROADMAP plan 01-04 says "advancing Change to processed").
- `in_review` — surfaced in the review queue.
- `verified` — reviewer approved; effective date entered.
- `rejected` — reviewer marked it noise (D-10).
**Rule:** Implement an explicit allowed-transitions map and reject illegal transitions in the service layer. A DB `CHECK` or enum constraint backs it. Do NOT implement `classified`, `pending-effective`, `active`, or `superseded` — those are Phases 5/6.

### Pattern 6: AI Summary via Structured Output (AI-01, AI-03, D-05)
**What:** A single-turn Anthropic Messages call grounded **only** on the verbatim diff, returning the D-05 structured fields via a Pydantic schema.
**When to use:** Once per `detected` Change.
**Example:**
```python
# Source: platform.claude.com/docs/build-with-claude/structured-outputs (GA, 2026)
import anthropic
from pydantic import BaseModel, Field

class ChangeSummary(BaseModel):
    headline: str = Field(description="One-line headline of what changed")
    what_changed: str = Field(description="1-3 sentences: what changed")
    where: str = Field(description="Which rule / section")
    to_whom: str = Field(description="Who is affected")
    for_what_cases: str = Field(description="Which cases/proceedings it applies to")

client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

SYSTEM = (
    "You summarize changes to U.S. bankruptcy procedural rules for a reviewer. "
    "Summarize ONLY what the diff explicitly states. "
    "Do NOT speculate about practical impact beyond the explicit rule text. "  # D-07
    "Do NOT phrase any output as advice or recommendation. "                   # D-07
    "Be concise: 1-3 sentences per field."                                     # D-06
)

def summarize(diff_text: str) -> ChangeSummary:
    resp = client.messages.parse(
        model="claude-opus-4-7",          # model ID is a string, not SDK-tied
        max_tokens=1024,
        system=SYSTEM,
        messages=[{"role": "user",
                   "content": f"Verbatim diff of the rule source:\n\n{diff_text}"}],
        output_format=ChangeSummary,
    )
    return resp.parsed_output
```
- The **"informational / not legal advice" label (D-08, AI-06) is NOT a model output field** — it is a constant the server attaches to every summary record. Never ask the model to produce it (the model could omit or alter it). Store it as a fixed column/constant or render it statically in the UI.
- Persist the summary as **JSONB** (D-09). Also record the `model` string and the prompt/system text for later reproducibility — AUDIT-03 is Phase 8, but capturing the model ID now is free insurance.
- **Prompt caching:** With one source and ~annual real changes, the system prompt is short and call volume is tiny — prompt caching offers negligible benefit in Phase 1. Skip it; revisit when call volume grows (Phase 4+).

### Pattern 7: Fixture Replay With No Production Branch (D-03, D-04)
**What:** The fixture path and live path differ ONLY in where snapshot content originates — never in detection/summary logic.
**How:**
- Capture a real Judiciary News feed response into `tests/fixtures/frbp_feed_v1.xml`; hand-edit a copy `frbp_feed_v2.xml` introducing a realistic FRBP amendment item.
- A test (or seed script) inserts these as two `snapshot` rows for the seed source, then invokes the *same* `detect` + `summarize` functions the live path calls.
- The live path uses `respx` in tests to replay `frbp_feed_v1.xml`/`v2.xml` as HTTP responses — so even the fetch adapter is exercised offline and deterministically.
- **Anti-backdoor rule:** there is no `if fixture:` branch anywhere in `src/`. Fixtures are ordinary stored snapshots / replayed HTTP responses. The only fixture-specific code lives in `tests/`.

### Anti-Patterns to Avoid
- **Production-only / synthetic-injection branch** — explicitly forbidden by D-04. Fixtures must flow through identical code.
- **Standing up a Procrastinate worker in Phase 1** — Procrastinate's first use is Phase 4 per ROADMAP. Phase 1 invokes pipeline functions directly.
- **Asking the LLM to emit the "not legal advice" label** — it is a server constant (AI-06 reliability).
- **Treating `feedparser` `bozo=1` as automatic failure** — it flags malformed-but-parseable feeds; only fail when no entries were recovered.
- **Building real auth for the review UI** — Claude's discretion + Deferred Ideas say keep it an internal unauthenticated tool; capture reviewer identity as a free-text field only.
- **Implementing lifecycle states beyond `verified`/`rejected`** — `pending-effective`, `active`, `superseded` are Phases 6/7.
- **Sharing a DB connection with "the other product"** — API-07; the pull endpoint is the only seam.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Parsing RSS/Atom | Regex / ElementTree feed parser | `feedparser` | Handles RSS 0.9x–2.0, Atom, malformed feeds, date formats, encodings |
| Conditional GET / caching | Manual header bookkeeping from scratch | httpx + stored ETag/Last-Modified columns | Standard If-None-Match / If-Modified-Since flow |
| Textual diff | Custom line-diff algorithm | `difflib.unified_diff` (stdlib) | Correct, zero-dependency |
| LLM JSON extraction | Prompt "return JSON" + `json.loads` + retry loop | `client.messages.parse()` + Pydantic | GA structured outputs guarantee schema-valid output |
| Diff rendering in UI | Hand-built side-by-side table | `react-diff-viewer-continued` | Locked; proven, React 19-compatible |
| Server-state caching in React | `useEffect` + `useState` fetch glue | TanStack Query | Polling, optimistic updates, cache invalidation |
| Schema migrations | Hand-written SQL DDL scripts | Alembic | Versioned, reversible, reviewable — essential for an auditable system |
| HTTP mocking in tests | Live calls to uscourts.gov | `respx` | Deterministic, offline, polite to a government site |

**Key insight:** Phase 1 is a walking skeleton — every line of hand-rolled infrastructure is a line that competes with the actual goal (a working vertical slice). The locked stack already solves every generic problem here; the only bespoke code should be domain logic (the source-adapter, normalization, the lifecycle map, the prompt).

## Runtime State Inventory

Not applicable — Phase 1 is a greenfield build, not a rename/refactor/migration. No prior runtime state exists (`C:\data\cc` contains only `.planning/`, `.claude/`, `CLAUDE.md`). **Verified: no databases, services, OS-registered tasks, secrets, or build artifacts exist for this project yet.**

## Common Pitfalls

### Pitfall 1: Treating the Judiciary News feed as FRBP-specific
**What goes wrong:** Planner assumes the seed feed contains only rule amendments; detection logic or fixtures get built around rules-only content.
**Why it happens:** D-01 locks the FRBP *layer*; D-02 implied a rules feed exists. Research shows it does not — only a general judiciary news feed.
**How to avoid:** Model the Source's `layer = FRBP` independently of feed breadth. Fixtures must look like *real Judiciary News feed items*, one of which is an FRBP amendment announcement. Detection compares whole-feed snapshots; a new FRBP item appearing is the "change."
**Warning signs:** Fixtures that are bare rule text rather than RSS items; normalization that assumes a rules-document structure.

### Pitfall 2: Silent fetch failure read as UNCHANGED
**What goes wrong:** A timeout, 500, soft-404, or empty body is swallowed and the source looks healthy with "no change" — the core failure mode the project's CLAUDE.md calls out as the top operational risk.
**Why it happens:** Broad `except` blocks; trusting HTTP 200 without checking body length; not distinguishing 304 from a content-equal 200.
**How to avoid:** Enforce the tri-state outcome rules (Pattern 2) exhaustively. Any path that does not provably yield CHANGED or UNCHANGED must yield FETCH_FAILED. Unit-test each branch.
**Warning signs:** A fetch function that can return without setting an explicit outcome; no test for the timeout/non-200 path.

### Pitfall 3: LLM omits or alters the "not legal advice" label
**What goes wrong:** AI-06 requires every summary to carry the label; if the model generates it, it can drop or reword it.
**Why it happens:** Putting the label in the structured-output schema.
**How to avoid:** The label is a server-side constant attached to the persisted record and rendered statically by the UI. The model schema (D-05) contains only headline + the four content fields.
**Warning signs:** A `legal_disclaimer` field in `ChangeSummary`; the label appearing inside model output text.

### Pitfall 4: `react-diff-viewer-continued` + React 19 peer-dependency
**What goes wrong:** Historically (early 2025) there was an open issue asking for React 19 support, causing peer-dependency install warnings.
**Why it happens:** Stale assumption from training data.
**How to avoid:** **Resolved** — `react-diff-viewer-continued@4.2.2` peerDependencies explicitly include `react ^19.0.0` and `react-dom ^19.0.0` `[VERIFIED: npm 2026-05-20]`. Install 4.2.2; no `--legacy-peer-deps` needed.
**Warning signs:** Pinning an old (<4.2) version; npm peer-dependency errors (indicates a too-old version).

### Pitfall 5: Alembic + PostgreSQL ENUM migration friction
**What goes wrong:** SQLAlchemy `Enum` types backed by native PostgreSQL `ENUM` are awkward to alter — Alembic autogenerate does not always emit `CREATE TYPE`/`ALTER TYPE`, and adding enum values later requires manual migration code.
**Why it happens:** Postgres native enums are not freely alterable; the lifecycle enum (EFF-02) will gain values in Phases 5/6.
**How to avoid:** Two viable options — (a) use a native PG enum and accept manual `op.execute("ALTER TYPE ... ADD VALUE ...")` migrations later, or (b) store `status` as a `VARCHAR` with a `CHECK` constraint (or app-level validation), which is trivially extensible. For a system whose taxonomy will provably evolve, **option (b) (VARCHAR + CHECK, or VARCHAR + app-enforced)** is the lower-friction choice. Planner should pick one explicitly and document it.
**Warning signs:** An autogenerated migration that silently drops/recreates the enum type; needing to edit a migration by hand to add a status value.

### Pitfall 6: Async SQLAlchemy session misuse
**What goes wrong:** Sharing one `AsyncSession` across requests, or mixing sync and async engines, causes "another operation is in progress" errors.
**Why it happens:** Copying sync SQLAlchemy patterns into an async app.
**How to avoid:** One `AsyncSession` per request via a FastAPI dependency (`async def get_session()` yielding from an `async_sessionmaker`). Use `create_async_engine` with the `psycopg` async driver (`postgresql+psycopg://`).
**Warning signs:** Module-level session objects; `psycopg2` (sync-only) in dependencies.

## Code Examples

### Async DB session dependency (FastAPI + SQLAlchemy 2.0)
```python
# Source: SQLAlchemy 2.0 async docs + FastAPI dependency-injection pattern
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

engine = create_async_engine("postgresql+psycopg://user:pw@localhost/brm")
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def get_session() -> AsyncSession:
    async with SessionLocal() as session:
        yield session
```

### Pull delivery API — verified changes only (API-01, API-07)
```python
# Source: FastAPI standard pattern
from fastapi import APIRouter, Depends
from sqlalchemy import select

router = APIRouter(prefix="/changes", tags=["pull-api"])

@router.get("", response_model=list[ChangeOut])
async def list_verified_changes(session: AsyncSession = Depends(get_session)):
    # The ONLY integration seam with "the other product" — read-only, verified only
    result = await session.execute(
        select(Change).where(Change.status == "verified").order_by(Change.detected_at.desc())
    )
    return result.scalars().all()
```

### Review-queue mutation with TanStack Query (approve/edit/reject)
```typescript
// Source: TanStack Query v5 mutation pattern
import { useMutation, useQueryClient } from "@tanstack/react-query";

function useReviewAction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (p: { id: string; action: "approve" | "reject" | "edit";
                      effectiveDate?: string; summary?: ChangeSummary }) =>
      fetch(`/review/${p.id}/${p.action}`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(p),
      }).then(r => { if (!r.ok) throw new Error("review action failed"); return r.json(); }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["review-queue"] }),
  });
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| LLM JSON via prompt + `json.loads` + retry | `client.messages.parse()` with Pydantic, structured outputs **GA** | 2025→2026 (GA, no beta header) | No retry loop; schema-valid output guaranteed; use `messages.parse()` |
| `output_format=` convenience param (beta) | `output_config={"format": {...}}` GA shape; `output_format` still works for backward-compat | 2026 GA | Either works in SDK 0.103.x; `parse()` accepts a Pydantic model directly |
| `react-diff-viewer-continued` lacked React 19 peer dep | 4.2.2 peerDeps include `react ^19.0.0` | 2025 | Install 4.2.2; no peer-dep workaround |
| psycopg2 (sync) | psycopg 3 (`postgresql+psycopg://`, async) | — | Required for async SQLAlchemy |

**Deprecated/outdated:**
- CLAUDE.md pins Uvicorn `0.34.x` and Alembic `1.13.x` — both are stale. Current: Uvicorn **0.47.0**, Alembic **1.18.4**. Planner should pin current versions (no breaking changes affect Phase 1 usage).
- Pydantic v1 — end of life; v2 only.
- `news.uscourts.gov/feed` as a canonical URL — it 302-redirects to `https://www.uscourts.gov/news/rss`. Register the final URL directly.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The Judiciary News RSS feed is the best available seed for the FRBP layer (no rules-specific feed exists) | FRBP Feed Identification | Low — verified the rulemaking page has no feed; if a better feed exists it would only improve the slice, not break it. Planner/user may confirm. |
| A2 | The uscourts.gov feed endpoint honors `If-None-Match`/`If-Modified-Since` (304 responses) | Pattern 2 | Low — code already falls back to hash-equality for UNCHANGED if the server ignores conditional headers; tri-state still holds. |
| A3 | `client.messages.parse()` exists and accepts a Pydantic model in `anthropic` 0.103.1 | Pattern 6 | Medium — `parse()` is documented in the GA structured-outputs page; if the exact helper name differs in 0.103.1, fall back to `messages.create()` with `output_config`. Planner should verify against the installed SDK at implementation time. |
| A4 | FRBP amendments effective Dec 1, 2026 (Rules 1007/3018/5009/9006/9014/9017/new 7043) are accurate fixture material | FRBP Feed Identification | Low — read directly off the pending-amendments page; even if revised, fixtures only need to be *realistic*, not legally current. |

## Open Questions

1. **Lifecycle `status` storage — native PG ENUM vs VARCHAR+CHECK**
   - What we know: the lifecycle enum will gain values in Phases 5/6; native PG enums are awkward to alter via Alembic.
   - What's unclear: team preference for DB-enforced enum vs app-enforced.
   - Recommendation: VARCHAR + CHECK constraint (extensible). Planner should decide explicitly in plan 01-01.

2. **Snapshot `raw_content` vs normalized-only**
   - What we know: ROUTE-03 wants the reviewer to see "the snapshot"; D-09/discretion leaves retention to standard approaches.
   - What's unclear: whether the reviewer needs the raw feed XML or the normalized text suffices.
   - Recommendation: store normalized content for Phase 1 (sufficient for the diff + a "view snapshot" panel); add `raw_content` only if a reviewer need emerges.

3. **Reviewer identity capture**
   - What we know: full attribution is Phase 8; Claude's discretion allows a minimal default.
   - Recommendation: a free-text `reviewer_name` field on the approve/reject action, stored on the Change row. No login, no user table.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node.js | Review SPA build (Vite) | ✓ | v24.13.0 | — |
| Python 3.12 | Entire backend | ✗ | — | **Blocking — must be installed** |
| uv | Python deps/venv | ✗ | — | pip + venv (worse; uv is locked in CLAUDE.md) |
| PostgreSQL 16 | All persistence | ✗ | — | Run via Docker (`docker-compose`) |
| Docker | Local Postgres container | ✗ (not detected) | — | Install Docker Desktop, OR install Postgres 16 natively |
| Anthropic API key | AI summary call | ✗ (env var) | — | `ANTHROPIC_API_KEY` must be provisioned; tests can mock the SDK |

**Missing dependencies with no fallback (planner MUST address):**
- **Python 3.12** is not installed on the build machine — the entire backend depends on it. Plan 01-01 (or a Wave 0 setup task) must install Python 3.12 + uv.
- **PostgreSQL 16** — required by every persistence stage. Provide it via Docker; if Docker is also absent, the setup task must install Docker Desktop or native Postgres 16.
- **`ANTHROPIC_API_KEY`** — required for the live AI call in plan 01-04. Must be provisioned as an environment variable / secret; AI unit tests should mock the SDK so the suite runs without it.

**Missing dependencies with fallback:**
- Docker absent → install Docker Desktop, or install Postgres 16 natively. Docker is the cleaner path and matches CLAUDE.md's `docker-compose` guidance.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio (latest) — backend; Vitest (Vite default) — frontend |
| Config file | none yet — created in Wave 0 (`pyproject.toml [tool.pytest.ini_options]`) |
| Quick run command | `uv run pytest -x -q` |
| Full suite command | `uv run pytest` (backend) + `npm test` (frontend, in `web/`) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SRC-01 | Source row holds all required registry columns | unit | `uv run pytest tests/test_models.py::test_source_columns -x` | ❌ Wave 0 |
| INGEST-01/04 | RSS fetch yields CHANGED on new content | integration (respx) | `uv run pytest tests/test_rss_adapter.py::test_fetch_changed -x` | ❌ Wave 0 |
| INGEST-04 | Timeout / non-200 / empty body → FETCH_FAILED | unit (respx) | `uv run pytest tests/test_rss_adapter.py::test_fetch_failed -x` | ❌ Wave 0 |
| INGEST-04 | HTTP 304 / hash-equal → UNCHANGED | unit (respx) | `uv run pytest tests/test_rss_adapter.py::test_fetch_unchanged -x` | ❌ Wave 0 |
| INGEST-05 | Successful CHANGED fetch inserts a snapshot row | integration | `uv run pytest tests/test_snapshot_store.py -x` | ❌ Wave 0 |
| DETECT-02 | Equal hash does NOT create a Change | unit | `uv run pytest tests/test_detect.py::test_hash_gate_blocks -x` | ❌ Wave 0 |
| DETECT-01 | Differing content creates a `detected` Change with a diff | unit | `uv run pytest tests/test_detect.py::test_diff_creates_change -x` | ❌ Wave 0 |
| AI-03/D-05 | Summarize returns the structured fields (mocked SDK) | unit | `uv run pytest tests/test_ai.py::test_summary_shape -x` | ❌ Wave 0 |
| AI-06 | Persisted summary carries the not-legal-advice label | unit | `uv run pytest tests/test_ai.py::test_label_attached -x` | ❌ Wave 0 |
| EFF-02 | Illegal status transition is rejected | unit | `uv run pytest tests/test_lifecycle.py -x` | ❌ Wave 0 |
| EFF-01 | Approve records detected_at and effective_date separately | integration | `uv run pytest tests/test_review_api.py::test_approve_records_dates -x` | ❌ Wave 0 |
| ROUTE-04 | Approve / edit / reject each transition correctly | integration | `uv run pytest tests/test_review_api.py -x` | ❌ Wave 0 |
| API-01 | Pull API returns only `verified` changes | integration | `uv run pytest tests/test_pull_api.py::test_only_verified -x` | ❌ Wave 0 |
| D-03/D-04 | Fixture replay and live path run identical detection code | integration | `uv run pytest tests/test_fixture_replay.py -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest -x -q` (fast unit subset)
- **Per wave merge:** `uv run pytest` + `npm test` in `web/`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `pyproject.toml [tool.pytest.ini_options]` — pytest + pytest-asyncio config (asyncio mode)
- [ ] `tests/conftest.py` — async DB session fixture (test Postgres / transactional rollback), respx fixture
- [ ] `tests/fixtures/frbp_feed_v1.xml` + `frbp_feed_v2.xml` — captured + modified Judiciary News feed (D-03)
- [ ] Framework install: `uv add --dev pytest pytest-asyncio respx`
- [ ] Frontend: Vitest comes with the Vite React-TS template; add component tests for the review queue
- [ ] A test Postgres database (Docker compose service or a dedicated test schema)

## Security Domain

> `security_enforcement` is not set in `.planning/config.json` — treated as enabled. Phase 1 is an internal-only tool with no real auth (per Claude's discretion / Deferred Ideas), so the surface is small but not zero.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no (Phase 1) | Internal unauthenticated tool by explicit decision; real auth deferred to Phase 8 context |
| V3 Session Management | no | No sessions in Phase 1 |
| V4 Access Control | partial | The pull API is read-only and exposes only `verified` changes — enforced by query filter, not by role |
| V5 Input Validation | yes | Pydantic models validate all API request bodies; reviewer-entered effective date validated as a real date; feed content treated as untrusted input |
| V6 Cryptography | minimal | SHA-256 used only as a content fingerprint (not a security primitive); `ANTHROPIC_API_KEY` and DB credentials via env/secrets, never in code or image |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| SQL injection via reviewer input / filter params | Tampering | SQLAlchemy 2.0 parameterized queries / ORM — never string-format SQL |
| Malicious / malformed feed content (XML) crashing the parser or XXE | Denial of Service / Information Disclosure | `feedparser` is hardened against malformed feeds and disables external entity resolution; treat `bozo` results per Pattern 2 |
| Untrusted feed text reaching the LLM prompt (prompt injection in feed content) | Tampering | Diff is presented as data, not instructions; system prompt fixes the task; output is schema-constrained (structured outputs) and human-reviewed before it reaches the pull API |
| Stored XSS — feed/AI text rendered in the review SPA | Tampering | React escapes JSX by default; never use `dangerouslySetInnerHTML` for feed/diff/summary content; `react-diff-viewer-continued` renders text safely |
| Secret leakage (`ANTHROPIC_API_KEY`, DB creds) | Information Disclosure | Env vars / `pydantic-settings`; `.env` git-ignored; never baked into the Docker image |
| Pull API leaking non-verified changes | Information Disclosure | Endpoint filters `status == "verified"` at the query level; integration test `test_only_verified` enforces it |

## Sources

### Primary (HIGH confidence)
- `https://www.uscourts.gov/news/rss` — fetched 2026-05-20: confirmed valid RSS 2.0, channel "Judiciary News - United States Courts", item structure
- `https://www.uscourts.gov/forms-rules/pending-rules-and-forms-amendments` — fetched 2026-05-20: confirmed NO feed, only email subscription; FRBP amendments effective Dec 1 2026/2027
- `https://www.uscourts.gov/rss-feeds` — fetched 2026-05-20: confirmed Judiciary News is the only published feed
- `https://news.uscourts.gov/feed`, `https://www.uscourts.gov/feed` — fetched 2026-05-20: confirmed 301/302 redirect to `/news/rss`
- `https://platform.claude.com/docs/en/build-with-claude/structured-outputs` — fetched 2026-05-20: structured outputs GA, `messages.parse()`, model support
- PyPI registry — verified versions for fastapi 0.136.1, anthropic 0.103.1, feedparser 6.0.12, httpx 0.28.1, sqlalchemy 2.0.49, alembic 1.18.4, procrastinate 3.8.1, pydantic 2.13.4, uvicorn 0.47.0, psycopg 3.3.4 (2026-05-20)
- npm registry — verified `react-diff-viewer-continued@4.2.2` (peerDeps include react ^19.0.0) and `@tanstack/react-query@5.100.11` (peer react ^18 || ^19); no postinstall scripts (2026-05-20)
- `CLAUDE.md` — LOCKED technology stack (authoritative project document)

### Secondary (MEDIUM confidence)
- feedparser docs — ETag/Last-Modified conditional GET support (`feedparser.readthedocs.io/.../http-etag/`)
- uscourts.gov rulemaking process pages — ~3-year amendment cycle, Dec 1 effective dates

### Tertiary (LOW confidence)
- General SQLAlchemy-2.0/FastAPI/Alembic tutorial corpus — used only to confirm well-known patterns already implied by CLAUDE.md; no novel claims rest on these

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every package verified against its registry; all locked in CLAUDE.md
- FRBP feed (D-02): HIGH — the feed URL, format, and the absence of a rules-specific feed were directly verified by fetching
- Architecture / patterns: HIGH — standard patterns for the locked stack; AI structured-output mechanism verified against current official docs
- Pitfalls: HIGH — each pitfall is verified (React 19 peer dep, enum migration friction, tri-state rules) or follows directly from project constraints

**Research date:** 2026-05-20
**Valid until:** 2026-06-19 (30 days — stable stack; re-verify the `anthropic` SDK `messages.parse()` API and the feed URL if the build slips materially)
