# Bankruptcy Rule Monitor

## What This Is

A complementary regulatory-change monitoring service for a bankruptcy application. It tracks rule changes across three layers of U.S. bankruptcy law — national, district, and state — and feeds verified changes into the main bankruptcy product ("the other product"). Built for the product team first, but architected to become a sellable add-on for other bankruptcy practitioners.

## Core Value

The main bankruptcy product never operates on stale rules — every relevant jurisdiction rule change is detected, verified, and available before (or exactly when) it takes effect.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

(None yet — ship to validate)

### Active

<!-- Current scope. Building toward these. All Active requirements are hypotheses until shipped and validated. -->

- [ ] Monitor national bankruptcy rules — Bankruptcy Code (Title 11), Federal Rules of Bankruptcy Procedure, Official Forms
- [ ] Monitor the ~90 federal bankruptcy court districts' local rules, standing orders, and general orders
- [ ] Monitor state exemption statutes and related dollar amounts
- [ ] Ingest from both court websites (scraping) and official feeds/notices (RSS, notice lists)
- [ ] Adaptive polling cadence — daily by default, sub-daily for feed-backed sources, intensified around known upcoming effective dates
- [ ] AI detects what substantively changed between old and new rule text
- [ ] AI classifies each change into a taxonomy (type, jurisdiction, severity)
- [ ] AI writes a plain-language summary of each change
- [ ] AI extracts structured data (fees, dates, form numbers) from each change
- [ ] Tiered handling — fees/forms auto-publish; rule/order text changes route to human review
- [ ] Web review queue for approving or rejecting pending changes, with the AI summary visible
- [ ] Track detected date and effective date separately; future-dated changes stay pending until their effective date
- [ ] Expose verified changes to the other product via an API the other product pulls

### Out of Scope

<!-- Explicit boundaries. Includes reasoning to prevent re-adding. -->

- Shared database between this monitor and the other product — keep the two systems decoupled; integrate via API only
- Webhook push at v1 — API-pull first; webhook notification is a deliberate later addition
- Non-bankruptcy areas of law — scope is U.S. bankruptcy rules only
- Legal advice or interpretation beyond plain-language summarization — the monitor reports what changed, it does not advise

## Context

- Companion to an existing bankruptcy application ("the other product"), also built with Claude.
- U.S. bankruptcy rules are layered: national (Title 11, Federal Rules of Bankruptcy Procedure, Official Forms), district (~90 bankruptcy court districts each with their own local rules and orders), and state (exemption statutes and dollar amounts).
- The source landscape is uneven — some courts publish RSS or notice feeds, others only static web pages — so ingestion must handle both reliably.
- Rule changes are frequently announced with a future effective date, so timing and scheduling are first-class concerns, not edge cases.
- AI (Claude) is central to the offering: diffing, classification, summarization, and structured extraction.

## Constraints

- **Integration**: API-first — the other product pulls changes; no shared database — Keeps the two products decoupled and independently deployable
- **Architecture**: Internal-use first, but designed for productization — Must not bake in single-tenant assumptions that would block a future sellable add-on
- **Accuracy**: Rule/order text changes require human review before publishing downstream — The legal consequences of a wrong or missed change are high
- **Coverage**: ~140+ distinct heterogeneous sources (national + ~90 districts + states) — Ingestion must scale across many sources with inconsistent formats and feeds

## Key Decisions

<!-- Decisions that constrain future work. Add throughout project lifecycle. -->

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Monitor all three rule layers (national, district, state) | Comprehensive coverage is the core of the offering | — Pending |
| Tiered handling: auto-publish fees/forms, human-review rule/order text | Balances speed with accuracy where the legal stakes are highest | — Pending |
| Track detected date vs effective date; future-dated changes stay pending | Changes announced ahead of effect must activate at exactly the right time | — Pending |
| Adaptive polling cadence driven by feed availability and upcoming effective dates | Catches time-sensitive changes without over-polling static sources | — Pending |
| API-first integration, no shared DB; webhook deferred | Keeps the two products decoupled rather than coupling them into one system | — Pending |
| Build internal-first, architect for productization | Deliver value now while preserving a path to a sellable add-on | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-20 after initialization*
