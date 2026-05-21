# Phase 1: End-to-End Feed Slice - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-20
**Phase:** 1-End-to-End Feed Slice
**Areas discussed:** Seed source pick, AI summary shape, Reviewer actions

---

## Area Selection

| Option | Description | Selected |
|--------|-------------|----------|
| Seed source pick | Which national RSS feed seeds the slice | ✓ |
| AI summary shape | What a good plain-language change summary looks like | ✓ |
| Reviewer actions | Approve/edit/reject + effective-date entry | ✓ |
| Review UI access | Open internal tool vs login-gated; reviewer identity | |

---

## Seed Source Pick

### Source family

| Option | Description | Selected |
|--------|-------------|----------|
| Federal Rules (FRBP) | uscourts.gov rulemaking area — most feed-shaped national source; rule-text changes match the review tier | ✓ |
| Official Forms | Frequent, discrete revisions, but form changes are the auto-publish tier | |
| Bankruptcy Code (Title 11) | Changes rarely, via Congress; weak feed and demo | |
| You decide | Let research pick the most reliable feed | |

**User's choice:** Federal Rules (FRBP)

### Slice validation strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Fixture replay | Real snapshot + modified copy run through detection; deterministic, demoable, doubles as regression fixture | ✓ |
| Synthetic injection | Live feed + on-demand altered-snapshot injection | |
| Wait for live change | Only proven when the real feed moves | |

**User's choice:** Fixture replay
**Notes:** Live polling against the real feed still runs in parallel; detection logic runs identically on fixture and live snapshots.

---

## AI Summary Shape

### Structure

| Option | Description | Selected |
|--------|-------------|----------|
| Structured fields | Labeled parts — headline, what changed, who/what affected; scannable, JSONB-friendly | ✓ |
| Plain prose paragraph | Single free-form paragraph | |
| Headline + detail | Short headline + expandable longer explanation | |

**User's choice:** Structured fields
**Notes:** UI renders structured fields as headlines in the queue with expandable detail sections — scannability plus flexibility.

### Depth

| Option | Description | Selected |
|--------|-------------|----------|
| Concise | 1–3 sentences / short fields — the gist; reviewer reads the diff for detail | ✓ |
| Thorough | Fuller explanation including likely practical impact | |

**User's choice:** Concise
**Notes:** Encode as a compact change-spec contract in the Phase 1 prompt — one-line headline + a 1–3-sentence "What changed / Where / To whom / For what cases" block. No-go constraints: no speculation about practical impact beyond the explicit rule text; no advice phrasing.

---

## Reviewer Actions

### Available actions

| Option | Description | Selected |
|--------|-------------|----------|
| Approve / edit / reject | Reject marks a detection as not-a-real-change/noise so it never reaches the API | ✓ |
| Approve / edit only | Defer reject; false-positive detections sit pending forever | |

**User's choice:** Approve / edit / reject

### Effective-date entry

| Option | Description | Selected |
|--------|-------------|----------|
| Reviewer enters it | Reviewer types the effective date during review; nullable until then | ✓ |
| Reviewer enters, with hint | Reviewer enters it; AI surfaces a non-authoritative date hint | |
| Leave null in Phase 1 | Defer to Phase 6 | |

**User's choice:** Reviewer enters it
**Notes:** Reviewer is the authoritative source for the effective date in Phase 1. The "AI date hint" variant is noted as a reasonable quick upgrade once the baseline works.

---

## Claude's Discretion

- Specific FRBP feed URL — research selects the most reliable real RSS/Atom feed.
- Review UI access model and reviewer-identity capture — not discussed; minimal sensible default for an internal-only v1 tool; full attribution is Phase 8.
- API response shape, snapshot retention, diff-rendering library — standard approaches per the CLAUDE.md stack.

## Deferred Ideas

- AI date-hint for effective-date entry — quick win to layer on after the Phase 1 baseline works; revisit end of Phase 1 or in Phase 5.
- Review UI access/auth and full reviewer-identity attribution — full audit trail is Phase 8 (AUDIT-02).
