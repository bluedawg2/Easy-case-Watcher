<!-- GSD:project-start source:PROJECT.md -->
## Project

**Bankruptcy Rule Monitor**

A complementary regulatory-change monitoring service for a bankruptcy application. It tracks rule changes across three layers of U.S. bankruptcy law — national, district, and state — and feeds verified changes into the main bankruptcy product ("the other product"). Built for the product team first, but architected to become a sellable add-on for other bankruptcy practitioners.

**Core Value:** The main bankruptcy product never operates on stale rules — every relevant jurisdiction rule change is detected, verified, and available before (or exactly when) it takes effect.

### Constraints

- **Integration**: API-first — the other product pulls changes; no shared database — Keeps the two products decoupled and independently deployable
- **Architecture**: Internal-use first, but designed for productization — Must not bake in single-tenant assumptions that would block a future sellable add-on
- **Accuracy**: Rule/order text changes require human review before publishing downstream — The legal consequences of a wrong or missed change are high
- **Coverage**: ~140+ distinct heterogeneous sources (national + ~90 districts + states) — Ingestion must scale across many sources with inconsistent formats and feeds
<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->
## Technology Stack

## Recommended Stack
### Core Technologies
| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.12 (or 3.13) | Primary backend language | Strongest ecosystem for scraping, PDF extraction, and the Anthropic SDK; 3.12 is the safe production default in 2026 (3.13 fine, 3.14 too fresh for some C-extension deps). |
| FastAPI | 0.136.x | API framework (the API the other product pulls; serves the review-UI backend) | Async-native (matches async scraping/LLM I/O), automatic OpenAPI schema for the consuming product, Pydantic v2 validation, first-class dependency-injection for per-tenant auth later. Mature and dominant for new Python APIs. |
| Uvicorn | 0.34.x | ASGI server | Standard production ASGI server for FastAPI. Run behind a process manager; pair with Gunicorn workers if multi-process is needed. |
| PostgreSQL | 16 (17 acceptable) | Primary datastore: rule snapshots, change records, review queue, source registry, schedule state | Single dependable datastore covers relational data (sources, changes, audit trail), JSONB (LLM structured output, taxonomy), full-text search, and — critically — doubles as the **job queue** (see below), removing the need for Redis/RabbitMQ at v1. Row-level data is the natural seam for future multi-tenancy. |
| Anthropic Python SDK (`anthropic`) | 0.103.x | LLM orchestration — diff classification, summarization, structured extraction | Official, typed SDK. Direct SDK use (not a framework wrapper) is correct here: the LLM workload is a handful of well-defined, single-turn prompt operations, not an autonomous agent. Use the Messages API with tool/`response_format`-style structured output for the extraction step and the **Message Batches API** for non-urgent bulk diffs. |
| SQLAlchemy 2.x + Alembic | 2.0.x / 1.13.x | ORM + schema migrations | SQLAlchemy 2.0 async style pairs with FastAPI; Alembic gives versioned, reviewable migrations — essential for an auditable system that will evolve its change taxonomy. |
| Pydantic | 2.x | Data validation / settings / LLM-output schemas | Defines the API contract, validates LLM structured output before persistence, and `pydantic-settings` manages per-environment config. |
### Job Scheduling & Background Processing
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Procrastinate | 3.x | Postgres-backed distributed task queue + periodic (cron) scheduling | Recommended primary. Stores tasks in Postgres (no Redis/RabbitMQ to operate), supports async workers, deferred/scheduled tasks, periodic tasks, retries, and **task locks** — locks map directly onto "one poll per source at a time." Deferred-task scheduling is exactly how you implement "future-dated change activates on its effective date" and "intensify polling near an effective date." |
| APScheduler | 3.11.x | In-process scheduling | Alternative only if you stay single-process and never need durable, distributed task state. Adequate for a prototype; outgrown quickly because schedules live in memory. |
### Web Scraping & Document Extraction
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| httpx | 0.28.x | Async HTTP client for fetching pages, feeds, PDFs | Default fetcher. Async (matches the scheduler), HTTP/2, connection pooling, timeouts/retries. Most court pages are static HTML/PDF — no browser needed. |
| selectolax | 0.3.x | Fast HTML parsing / content extraction | Recommended HTML parser — C-backed, far faster than BeautifulSoup, CSS-selector API. Use BeautifulSoup instead only if you value forgiving API over speed. |
| feedparser | 6.0.x | RSS / Atom feed parsing | For the courts that publish RSS or notice feeds — robust against malformed feeds. |
| pypdfium2 | 4.x | PDF text extraction | **Recommended PDF extractor.** Apache-2.0 / BSD-3-Clause license — critical because the product is being architected for resale; PyMuPDF's AGPL would force open-sourcing or a paid commercial license. Fast, good text quality with positional data. |
| pdfplumber | 0.11.x | Table-aware PDF extraction | Add only for specific sources where fee schedules or exemption tables must be parsed as structured tables. Slower; use selectively, not as the default. |
| Playwright | 1.5x.x | Headless-browser fetching | **Escape hatch only.** Add per-source if and when a court site is found to require JavaScript rendering. Do not adopt project-wide — it is heavy and most `.uscourts.gov` pages are static. |
### Change / Diff Detection
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Python `difflib` (stdlib) | stdlib | Cheap deterministic pre-filter — has the normalized text changed at all? | Always run first. Hash + difflib gate avoids paying for an LLM call when nothing changed (boilerplate, timestamps, nav chrome). |
| (Anthropic SDK) | — | Semantic diff: what *substantively* changed, classification, summary | The LLM does the meaningful diff on the subset that passed the cheap gate. difflib output can be fed into the prompt as context. |
### Review-Queue Web UI
| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| React + Vite + TypeScript | React 19.x / Vite 6.x | Single-page review-queue app | The review queue is an authenticated internal tool — no SEO need, so a Vite React SPA is lighter and simpler than Next.js. Component model fits queue/table/diff-detail UI. TypeScript catches contract drift against the FastAPI OpenAPI schema. |
| shadcn/ui + Tailwind CSS | current | Component layer | Tables, dialogs, badges (taxonomy/severity), and approve/reject controls out of the box. Copy-in components, no heavy framework lock-in. |
| TanStack Query | 5.x | Server-state / data fetching | Handles queue polling, optimistic approve/reject, cache invalidation cleanly. |
| `react-diff-viewer-continued` | current | Side-by-side old-vs-new rule-text rendering | The reviewer must see exactly what changed; a proven diff component beats hand-rolling. |
### Development Tools
| Tool | Purpose | Notes |
|------|---------|-------|
| uv | Python dependency & venv management | Fast, lockfile-based; the 2026 default for new Python projects. Replaces pip/poetry. |
| Ruff | Lint + format | One fast tool for both; replaces flake8/black/isort. |
| pytest + pytest-asyncio | Testing | Test source adapters against saved HTML/PDF fixtures so parser regressions are caught without hitting live court sites. |
| respx / vcrpy | HTTP mocking for tests | Record/replay court-site responses; keeps the scraping test suite deterministic and offline. |
| Docker + docker-compose | Packaging / local Postgres | Containerize the API and the worker as separate images from one codebase. |
| Sentry | Error monitoring | A scraper that silently breaks is the top operational risk — see PITFALLS. Alerting is not optional. |
## Installation
# Project + dependency management
# Core backend
# LLM
# Scheduling / task queue
# Scraping + document extraction
# Optional headless-browser escape hatch (install only when a source needs it)
# uv add playwright && playwright install chromium
# Dev dependencies
# Review UI (separate frontend package)
# shadcn/ui + tailwind set up per their CLI
## Alternatives Considered
| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| Procrastinate (Postgres queue) | Celery + Redis | If job volume grows into millions/day or you need complex multi-step workflows (chords/chains). Not the case here — Celery's broker overhead is unjustified at ~140 sources. |
| Procrastinate | Dramatiq + Redis | If you later need a dedicated broker; Dramatiq is the reliability-focused choice. Still adds infrastructure Procrastinate avoids. |
| FastAPI | Django + DRF | If you want a batteries-included admin UI for the review queue for free. Trade-off: heavier, less async-native for the scraping/LLM I/O. Reasonable if the team already knows Django. |
| pypdfium2 | PyMuPDF | If extraction quality on a specific gnarly PDF is materially better AND you buy the Artifex commercial license. Default to pypdfium2 to keep the resale path license-clean. |
| React SPA | HTMX + FastAPI templates | If there is zero front-end capacity and v1 must ship fast. Acceptable for internal-only; reconsider before productization. |
| httpx | Scrapy | If this became a massive broad crawler. It is not — it is ~140 known, targeted sources with bespoke adapters; Scrapy's framework is overkill. |
| selectolax | BeautifulSoup | If parser ergonomics/forgiveness matter more than speed, or team familiarity favors it. Performance difference is irrelevant at this scale, so either is defensible. |
## What NOT to Use
| Avoid | Why | Use Instead |
|-------|-----|-------------|
| PyMuPDF (as the default PDF lib) | AGPL-3.0 — for a product "architected to become a sellable add-on," AGPL forces open-sourcing the whole service or buying a commercial license. License risk baked into the foundation. | pypdfium2 (Apache-2.0 / BSD-3-Clause) |
| LangChain / LlamaIndex / agent frameworks | The LLM work is a few fixed, single-turn operations (diff, classify, summarize, extract). An agent/orchestration framework adds abstraction, version churn, and debugging pain for zero benefit. | Anthropic SDK directly, with plain functions per operation |
| Redis / RabbitMQ at v1 | Another stateful service to run, monitor, and back up, for a workload Postgres handles trivially. Premature infrastructure. | Procrastinate on the existing Postgres |
| Selenium | Slower, flakier, heavier than Playwright; legacy choice. | Playwright — and only as a per-source escape hatch |
| Scraping via raw `requests` + regex on HTML | Brittle; breaks silently on markup changes. | httpx + a real HTML parser, with fixture-based regression tests |
| A shared database with "the other product" | Explicitly out of scope in PROJECT.md — couples the two systems. | The pull API (FastAPI) as the only integration seam |
| NoSQL / MongoDB as primary store | The data is relational and audit-critical (sources, changes, review decisions, effective dates). JSONB columns in Postgres cover the semi-structured LLM output. | PostgreSQL with JSONB where needed |
| SQLite in production | Fine for tests/prototype; no concurrent-writer story for parallel scraper workers + API + queue. | PostgreSQL |
## Stack Patterns by Variant
- Keep the React SPA but skip multi-tenancy plumbing; use HTMX-rendered pages only if no front-end help exists.
- Single Postgres, single worker process, Procrastinate periodic tasks. Defer per-source Playwright until a source actually demands it.
- Add a `tenant_id` column to all tenant-scoped tables from day one (cheap insurance) even if v1 has one tenant; enforce with row-level security or query-layer scoping.
- Move API auth to per-tenant API keys / OAuth client credentials.
- Source registry and rule snapshots are shared (the rules are the same for everyone); only saved searches, subscriptions, and webhook configs are tenant-scoped.
- Add Playwright as a per-adapter fetch strategy behind the source-adapter interface — do not convert the whole fetch layer to a browser.
## Hosting / Deployment Considerations
- **Two process types from one codebase:** (1) the FastAPI API (web), (2) the Procrastinate worker(s) running scrapers + the LLM pipeline. Scale them independently.
- **The scheduler must never stop.** Use a platform that runs persistent worker processes — a container platform (Fly.io, Railway, Render, AWS ECS/Fargate, or a plain VM with systemd). **Do not** build the poller on pure serverless/Lambda-with-cron — long PDF/LLM jobs and stateful adaptive scheduling fight the serverless model. Serverless is fine only for the read-only pull API if ever split out.
- **Managed Postgres** (RDS, Cloud SQL, Neon, Supabase) — it holds rule snapshots, the audit trail, and the job queue, so backups and point-in-time recovery matter.
- **Secrets:** `ANTHROPIC_API_KEY` and DB credentials via the platform's secret manager, never in the image.
- **Observability is load-bearing:** a silently broken scraper is the worst failure mode (you stop detecting changes but everything looks green). Required: Sentry for errors, plus a heartbeat/"last successful poll per source" check that alerts when a source goes stale.
- **Timezone discipline:** store everything in UTC; the "effective date" logic must be explicit about court-local vs UTC dates — bankruptcy effective dates are calendar dates, not instants.
- **Polite scraping:** per-domain rate limiting and a descriptive User-Agent; court sites are government infrastructure. Cache ETags/Last-Modified to avoid refetching unchanged pages.
## Version Compatibility
| Package | Compatible With | Notes |
|---------|-----------------|-------|
| FastAPI 0.136.x | Pydantic 2.x, Python 3.10+ | Pydantic v1 is end-of-life — use v2 only. |
| SQLAlchemy 2.0.x | psycopg 3.x (`psycopg[binary]`) | Use psycopg 3, not psycopg2; async support is needed for async SQLAlchemy. |
| Procrastinate 3.x | PostgreSQL 13+, Python 3.10+ | Shares the Postgres instance with app data — same connection config. |
| anthropic 0.103.x | Python 3.9+ | SDK moves fast; pin the version and review changelog on upgrade. Model IDs (e.g. `claude-opus-4-7`) are passed as strings — not tied to SDK version. |
| pypdfium2 4.x | Python 3.8+ | Self-contained binary wheels; no system PDF libs to install. |
| React 19.x | Vite 6.x, TypeScript 5.x | Stable pairing in 2026. |
## Sources
- /anthropics/anthropic-sdk-python (Context7) — official Anthropic Python SDK — HIGH
- https://pypi.org/project/fastapi/ — FastAPI 0.136.x current release — HIGH
- https://pypi.org/project/anthropic/ — `anthropic` 0.103.x current release — HIGH
- https://github.com/procrastinate-org/procrastinate — Postgres task queue, Python 3.10+/PG 13+ — HIGH
- https://github.com/janbjorge/pgqueuer — alternative Postgres queue (SKIP LOCKED / LISTEN-NOTIFY) — MEDIUM
- https://pypi.org/project/pypdfium2/ — Apache-2.0 / BSD-3-Clause licensing confirmed — HIGH
- https://pymupdf.readthedocs.io/en/latest/about.html — PyMuPDF AGPL / commercial license — HIGH
- https://www.scrapingbee.com/blog/best-python-web-scraping-libraries/ — 2026 scraping library landscape — MEDIUM
- https://judoscale.com/blog/choose-python-task-queue — Python task queue comparison — MEDIUM
- https://www.nutrient.io/blog/best-python-pdf-libraries/ — 2026 Python PDF library comparison — MEDIUM
- https://dev.to/syedahmershah/react-is-overkill-why-python-htmx-is-dominating-in-2026-17ib — internal-tool UI tradeoffs — LOW
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
