---
phase: 2
slug: html-scraping-source-health
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-21
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from RESEARCH.md § Validation Architecture. Locked by CONTEXT.md D-17
> (deterministic fixture replay, no production-only branch) and D-18 (the source-health
> guarantees are explicitly exercised and asserted, not just the happy path).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio (`asyncio_mode = "auto"`) — exists from Phase 1 |
| **Config file** | `pyproject.toml [tool.pytest.ini_options]` (exists from Phase 1) |
| **HTTP mocking** | `respx` (dev dependency, Phase 1) — replays HTML fixtures offline |
| **Quick run command** | `uv run pytest -x -q` |
| **Full suite command** | `uv run pytest` |
| **Estimated runtime** | ~15 seconds (offline fixture replay) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest -x -q`
- **After every plan wave:** Run `uv run pytest` (full backend suite)
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~15 seconds

---

## Per-Task Verification Map

> Task IDs are assigned by the planner. This map is completed during planning — each
> task gets either an `<automated>` verify command or a Wave 0 dependency. Rows below
> are the requirement → behavior anchors from RESEARCH.md the planner must satisfy.

| Anchor | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|--------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| Clean HTML → snapshot → detected Change | INGEST-02 | — | N/A | integration (respx) | `uv run pytest tests/test_html_adapter.py -x -q` | ❌ W0 | ⬜ pending |
| `extract_region` applies selector + strip rules deterministically | INGEST-02 / D-05 | T-V5 (config shape) | Validated `extraction_config` Pydantic shape | unit | `uv run pytest tests/test_extract.py -x -q` | ❌ W0 | ⬜ pending |
| Empty region / selector-miss → FETCH_FAILED, never UNCHANGED | INGEST-04 / D-07 | — | No silent "no change" on broken scrape | integration (respx) | `uv run pytest tests/test_html_adapter.py -k "empty or selector" -x -q` | ❌ W0 | ⬜ pending |
| Soft-404 / login-wall → FETCH_FAILED + correct `failure_reason` | SRC-05 / D-07 | — | HTTP-200 failure pages never UNCHANGED | integration (respx) | `uv run pytest tests/test_failure_detect.py -x -q` | ❌ W0 | ⬜ pending |
| Drifted layout → fingerprint fails → FETCH_FAILED + alert, source stays active | SRC-05 / D-09, D-10 | T-ID (alert payload) | Alert carries metadata only | integration (respx) | `uv run pytest tests/test_fingerprint.py -x -q` | ❌ W0 | ⬜ pending |
| N consecutive FETCH_FAILED → auto-pause; single failure does NOT pause | SRC-05 / D-12 | — | N/A | integration | `uv run pytest tests/test_health.py -k "pause" -x -q` | ❌ W0 | ⬜ pending |
| No successful fetch in N days → staleness sweep alerts; quiet-but-fetched does NOT | SRC-05 / D-14 | — | N/A | unit/integration | `uv run pytest tests/test_health.py -k "stale" -x -q` | ❌ W0 | ⬜ pending |
| Politeness ceiling: min-interval skip, conditional headers, 304 → UNCHANGED | INGEST-07 / D-08 | — | Descriptive User-Agent on every request | integration (respx) | `uv run pytest tests/test_html_adapter.py -k "politeness or conditional" -x -q` | ❌ W0 | ⬜ pending |
| New HTML source onboarded as config-only `Source` row, no code change | SRC-06 | T-V5 | Operator config validated before use | integration | `uv run pytest tests/test_onboarding.py -x -q` | ❌ W0 | ⬜ pending |
| Feed+scrape pair → ONE Change + TWO `change_observation` rows | DETECT-03 / D-15, D-16 | — | N/A | integration | `uv run pytest tests/test_dedup.py -x -q` | ❌ W0 | ⬜ pending |
| Fixture-replay path and live path produce identical detection (no prod-only branch) | D-17 | — | N/A | integration | `uv run pytest tests/test_fixture_replay.py -k html -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/fixtures/html/clean.html` — verified pilot-page capture (capture live, do not hand-author)
- [ ] `tests/fixtures/html/drifted.html` — pilot page with the rule region replaced by an order-of-magnitude-larger block
- [ ] `tests/fixtures/html/soft_404.html` — an HTTP-200 "page not found" page
- [ ] `tests/fixtures/html/login_wall.html` — an HTTP-200 page with a login form
- [ ] `tests/fixtures/html/empty_region.html` — pilot page with `.field--name-body` present but empty
- [ ] `tests/fixtures/html/scrape_dedup.html` + matching feed fixture — the feed+scrape pair for the *same* FRBP amendment (D-16)
- [ ] `tests/test_extract.py`, `tests/test_failure_detect.py`, `tests/test_fingerprint.py`, `tests/test_html_adapter.py`, `tests/test_health.py`, `tests/test_dedup.py`, `tests/test_onboarding.py` — new test files (created within their owning tasks)
- [ ] `uv add sentry-sdk` — the only new dependency; pytest/pytest-asyncio/respx all exist from Phase 1

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live pilot page still reachable + `.field--name-body` selector still valid | INGEST-02 | Depends on a live government site; not deterministic | Run the adapter once against `https://www.uscourts.gov/forms-rules/pending-rules-and-forms-amendments`; confirm HTTP 200 and a non-empty extracted region. Fixture replay (D-17) is the primary automated path. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (6 HTML fixtures + 7 test files + sentry-sdk)
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
