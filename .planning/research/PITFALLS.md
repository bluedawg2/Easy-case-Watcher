# Pitfalls Research

**Domain:** U.S. bankruptcy regulatory-change monitoring (multi-source scraping + LLM diff/classification/summarization)
**Researched:** 2026-05-20
**Confidence:** HIGH for scraping/LLM pitfalls (corroborated by Free Law Project experience, academic legal-hallucination studies, PACER policy, and web-scraping post-mortems); MEDIUM for the bankruptcy-specific procedural details (training data + reasoning, fewer current sources).

## Critical Pitfalls

### Pitfall 1: Silent scraper failure mistaken for "no change"

**What goes wrong:**
A court reorganizes its site, moves a "Local Rules" page, changes a URL, or wraps content in JavaScript. The scraper returns an empty result, a 404 page body, a login wall, or a "page not found" HTML blob. The pipeline interprets "I retrieved content and it differs from / equals last time" without distinguishing "the rule genuinely did not change" from "I failed to fetch the rule." For a change-monitor, a silent fetch failure is indistinguishable from "all quiet" — and produces a false negative on a legal rule, which is the single worst outcome for this product.

**Why it happens:**
Scrapers are written against one layout at one moment. Across ~140+ heterogeneous sources, some subset breaks every week (industry data: 10-15% of crawlers in volatile domains need weekly fixes). Teams treat a successful HTTP 200 as success, but courts serve 200s for soft-404s, maintenance pages, and "access denied" interstitials. Nobody monitors the monitor, so it "fails silently for days or weeks."

**How to avoid:**
- Treat every source fetch as having three outcomes, not two: CHANGED, UNCHANGED, FETCH_FAILED. Never collapse FETCH_FAILED into UNCHANGED.
- Per-source health checks: expected content fingerprints (a known anchor string that must be present, e.g. "Local Bankruptcy Rule" / a known rule number), expected content-length floor, expected content-type. If a fetch lacks the fingerprint, mark FETCH_FAILED, not UNCHANGED.
- Staleness alarms: if a source has not produced a *verified successful* fetch within N polling cycles, raise an operational alert — silence is suspicious, not safe.
- Snapshot the raw fetched bytes every cycle so a human can diff "what the scraper saw" vs "what the site shows."
- Canary/heartbeat per source; dashboard of last-good-fetch timestamp for all ~140 sources.

**Warning signs:**
A source that "never changes" for months (could be genuine, could be broken). Sudden drop in content length. A run where many sources simultaneously report UNCHANGED. Parsed text that contains words like "404", "not found", "sign in", "maintenance".

**Phase to address:**
Ingestion / scraping foundation phase — must be designed in from day one, not bolted on. The CHANGED/UNCHANGED/FETCH_FAILED tri-state and per-source health monitoring are core architecture, not polish.

---

### Pitfall 2: Diff noise drowns the human review queue (false positives)

**What goes wrong:**
The system flags "changes" that are not substantive rule changes: a copyright-year bump, a reformatted PDF, a re-OCR'd document with different whitespace, a CMS template change, a "last updated" timestamp, navigation/footer edits, or a non-deterministic page (rotating banner, session token in HTML). Reviewers get dozens of noise items per day, lose trust, start rubber-stamping or ignoring the queue — and a real change slips through because it looked like more noise.

**Why it happens:**
Naive byte-level or DOM-level diffing treats every byte change as a change. Court PDFs are especially bad: re-saving a PDF changes internal structure without changing legal text; OCR of a scanned order is non-deterministic. The team optimizes for "detect everything" and forgets that a monitoring product's real currency is *signal-to-noise in the review queue*.

**How to avoid:**
- Normalize before diffing: strip boilerplate (headers, footers, nav, timestamps, copyright lines), collapse whitespace, normalize quotes/encoding, extract just the rule-text region.
- Diff on normalized *semantic content*, not raw HTML/PDF bytes. Maintain a per-source extraction template that isolates the legal text region.
- Two-stage detection: cheap normalized text-hash to detect *candidate* changes, then LLM to judge whether the candidate is substantive before it ever reaches a human.
- Track a noise metric explicitly: percentage of queue items reviewers reject as "not a real change." Treat a rising number as a defect, with a target (e.g. <10% noise).
- For PDFs: extract text and diff text, never diff the PDF binary or rendered image.

**Warning signs:**
Reviewers rejecting most queue items. "Changes" with effective dates in the past or no effective date. Diffs where only whitespace/punctuation moved. Same source flagging "changed" every single poll.

**Phase to address:**
Change-detection / diffing phase. The normalization layer and the noise metric are first-class deliverables of this phase, not the LLM phase.

---

### Pitfall 3: LLM hallucination / interpretive overconfidence on legal text

**What goes wrong:**
The LLM writes a plain-language summary or extracts structured data that is subtly wrong: it says a fee went to $338 when it went to $388; it says a rule "now requires" something that the rule made optional; it characterizes a clarifying amendment as a substantive obligation change; it invents a rationale the order never stated. Studies show legal-domain hallucination is common and that the dominant failure mode is *interpretive overconfidence* — not invented citations, but "adding unsupported characterizations" and "transforming attributed opinions into general statements." A wrong summary that reads fluently and confidently is more dangerous than an obvious error.

**Why it happens:**
LLMs are fluent and confident regardless of correctness, and "struggle to accurately gauge their own confidence." Teams trust a clean-sounding summary. Legal text is dense, full of cross-references and negations ("notwithstanding," "except as provided in") that models misread. Models also perform worse on niche jurisdictions and older material — exactly the long tail of ~90 district local rules and 50 states' exemption statutes.

**How to avoid:**
- Constrain the LLM to *grounded extraction*, not free generation: every claim in a summary must be traceable to a span of the actual rule text. Use the diff as the input, not the model's prior knowledge.
- Separate the two jobs: (a) "what literally changed" (mechanical, quotable, verifiable) and (b) "plain-language explanation." Always show the verbatim old-text / new-text alongside the summary in the review UI so the human verifies against source, not against the model.
- Never let the model invent or fill effective dates, fee amounts, or form numbers — extract them with strict patterns and have the model only *confirm/locate*, then validate (a fee must parse as currency; a date must parse and be plausible; a form number must match a known catalog).
- Use the model for classification/triage, but treat low-confidence or ambiguous classifications as automatic escalation to human review.
- Build a regression test set of real past rule changes with known-correct summaries/extractions; run it on every prompt or model change.

**Warning signs:**
Summaries that read well but the reviewer keeps correcting. Extracted numbers that fail validation. Model output asserting things not present in the diff. High agreement rate that drops when spot-checked against source text.

**Phase to address:**
LLM diff/classification/summarization phase. The grounding constraint, side-by-side source display, and extraction validation are core to that phase; the regression test set should be a phase deliverable.

---

### Pitfall 4: Auto-publish tier publishes a wrong change downstream

**What goes wrong:**
The "fees/forms auto-publish" tier is meant to be the safe, mechanical lane. But a misclassification routes a substantive rule change into the auto-publish lane (it looked like a forms update), or a fee extraction is wrong, and an unreviewed error flows straight into the other product's live behavior. Because there is no human gate on that tier, the error is live before anyone sees it — and the downstream product silently operates on bad law.

**Why it happens:**
The team assumes "fees and forms are simple." But classifying *what kind of change this is* is itself an LLM judgment that can be wrong. The auto-publish design trusts the classifier's output as if it were ground truth. The risk is the *routing decision*, not the change itself.

**How to avoid:**
- Recognize that the classifier's "this is a fee/form change" decision is itself a fallible LLM judgment — gate the *routing* with confidence thresholds. Only auto-publish when classification confidence is high AND extraction passes strict validation AND the change is small/well-formed.
- Anything ambiguous, low-confidence, large, or that touches rule/order text goes to human review — bias the router toward the review queue.
- Even auto-published changes get logged, are diff-able, and are *reversible*: keep an audit trail and a one-click rollback so a bad auto-publish can be retracted from the API.
- Post-publish sampling: a human spot-checks a sample of auto-published items; track the auto-publish error rate as a monitored metric.
- Version the API output so consumers can detect a correction/retraction.

**Warning signs:**
Auto-publish lane carrying items with large diffs or rule-text language. Downstream product or users reporting a wrong fee/form. No rollback path exists. Classification confidence not recorded.

**Phase to address:**
Tiered-routing phase, with the audit trail / rollback in the API-exposure phase. The confidence-gated router is the central deliverable.

---

### Pitfall 5: Effective-date errors — activating a change at the wrong time

**What goes wrong:**
A rule change is announced March 1 with an effective date of December 1. The system either (a) activates it immediately on detection, so the downstream product applies a not-yet-effective rule for nine months, or (b) loses the future date and the change never activates, so the product is stale after December 1. Variants: timezone mistakes flip activation by a day; an amended order *changes* a previously announced effective date and the system keeps the old one; a "retroactive to" date is treated as the activation date; a rule effective "30 days after publication" is never resolved to a concrete date.

**Why it happens:**
Teams conflate three distinct dates — *detected date*, *announced/published date*, and *effective date* — and store one when they need all three. Effective dates in legal text are expressed in many forms ("effective December 1, 2026"; "30 days after entry"; "upon approval by the Judicial Conference"; "the first day of the following month"). Future-dated activation is a scheduler problem that is easy to defer and easy to get wrong.

**How to avoid:**
- Model detected date, published date, and effective date as three separate fields; never overwrite one with another.
- Effective date is a first-class extracted field with its own validation: must parse to a concrete future-or-past calendar date, store the timezone explicitly, and flag "could not resolve to a concrete date" for human resolution (relative dates like "30 days after entry" must be computed or escalated, never silently dropped).
- Future-dated changes carry a PENDING state; a scheduler transitions them to ACTIVE at the effective date. The transition itself is a monitored job — alert if it does not fire.
- The API distinguishes "verified and effective now" from "verified, effective on <date>" so the downstream product can prepare without prematurely applying.
- Re-detection of the same rule must support *superseding* a prior effective date (an amendment that moves the date). Key changes by rule identity, not just by text.
- Add an "effective date arrived but we never saw the expected change" reconciliation check.

**Warning signs:**
A single date column in the schema. Changes going live the moment they are detected. "Effective date" fields containing relative phrases. No scheduled job for PENDING→ACTIVE. Timezone not stored.

**Phase to address:**
Data-model / state-machine phase for the three-date model and PENDING/ACTIVE states; scheduler phase for the activation job. This is explicitly called out in PROJECT.md as a first-class concern — treat it as such.

---

### Pitfall 6: Coverage gaps — a source that exists but is not being watched

**What goes wrong:**
A bankruptcy court issues changes through a channel the system does not monitor: a "General Orders" page separate from "Local Rules," a "Recent Announcements" feed, a judge-specific standing order, a PDF linked only from a news post, or a state legislature page for exemption amounts. The system faithfully monitors the pages it knows about and reports "all clear" while a real change lives on a page nobody registered. This is a false negative caused by an incomplete source map, not a broken scraper.

**Why it happens:**
The ~90 districts are wildly inconsistent in how and where they publish. Teams build a source list once, early, and treat it as complete. There is no process to discover that a court added a new publication channel. State exemption updates come through legislatures, not courts — an entirely different source class easy to under-scope.

**How to avoid:**
- Treat the source registry as a living, versioned artifact with an owner and a periodic re-audit cadence, not a one-time list.
- For each district, document *every* known publication channel (local rules, general orders, standing orders, notices, RSS) and the fact of which exist — explicitly record "this court has no RSS" so absence is a known fact, not an oversight.
- Periodically crawl each court's site index/sitemap for new pages matching rule-related keywords; surface candidates for a human to register.
- Track per-source provenance and a "last meaningful change observed" date — a district that has shown zero changes for an unusually long time is a coverage-gap suspect worth auditing.
- Cross-check against external corroboration where possible (e.g. Free Law Project / Juriscraper coverage, court newsletters) to catch missed channels.
- For state exemptions, monitor legislative sources, not just court sources.

**Warning signs:**
Source list created once and never revised. A district with zero detected changes over a long window while peers show activity. Discovering a change through an external channel (a user, a newsletter) that the monitor missed.

**Phase to address:**
Source-mapping / ingestion-design phase, with an ongoing operational re-audit process defined as part of operations. Coverage completeness should be an explicit phase exit criterion.

---

### Pitfall 7: PDF extraction failures corrupting the diff and the data

**What goes wrong:**
Court rules and orders are heavily PDF-based. Extraction fails in ways that are not obvious: a scanned/image-only order yields empty or garbage text; two-column layouts interleave lines; tables of exemption dollar amounts collapse into unreadable runs; ligatures and OCR artifacts turn "fi" into "ﬁ" or "$1,250" into "$1.250"; headers/footers/line numbers pollute the text; non-deterministic OCR makes an unchanged PDF look changed every poll. The downstream diff and the LLM then operate on corrupted input — producing both false positives (noise) and false negatives (a real change buried in garbage).

**Why it happens:**
Teams test extraction on a few clean, text-based PDFs and assume it generalizes. Court PDFs are a worst case: mixed scanned and digital, decades-old documents, inconsistent layouts across ~90 districts, tables of numbers (exemptions) that text extraction mangles.

**How to avoid:**
- Detect PDF type up front: text-layer PDF vs image-only/scanned. Route image-only PDFs through OCR; never assume a text layer exists.
- Validate extraction output: a non-trivial PDF that yields near-empty text is a FETCH_FAILED-class event, not "no content."
- Normalize extracted text aggressively (de-hyphenate line breaks, strip line numbers/headers/footers, fix ligatures/encoding) before diffing or sending to the LLM.
- For tabular data (exemption amounts), prefer structured table extraction and validate numbers parse as currency; treat a table that extracts as prose with low confidence.
- For OCR'd documents, diff on normalized text with fuzzy tolerance so OCR jitter does not register as a change; consider a similarity threshold rather than exact match.
- Keep the original PDF and a page-rendered image so a human reviewer can verify against the true document.

**Warning signs:**
Empty or tiny extracted text from a multi-page PDF. The same PDF flagged "changed" on consecutive polls with only whitespace differences. Exemption dollar figures that fail currency validation. Garbled characters in summaries.

**Phase to address:**
Ingestion / extraction phase — PDF handling deserves its own dedicated workstream and should not be treated as a sub-task of generic scraping.

---

### Pitfall 8: Rate limiting, terms-of-use, and getting blocked from court sources

**What goes wrong:**
Aggressive polling across ~140 sources gets the system's IP throttled or blocked by a court CDN, or violates a site's terms of use. PACER explicitly suspends accounts that cause "an unacceptable level of congestion" and restricts large data pulls to off-peak hours (6pm-6am Central); other court sites have their own implicit limits. A block is a coverage outage — and a terms-of-use or billing-avoidance violation around PACER can carry "criminal prosecution or civil action." Losing access to a source is a self-inflicted false-negative source.

**Why it happens:**
The adaptive scheduler is tuned for *freshness* (poll harder around effective dates) without a *politeness* budget. Teams forget that court sites are public infrastructure with limited capacity, and that "intensified polling around effective dates" can collide with exactly when everyone else is also checking.

**How to avoid:**
- Per-source politeness policy: minimum interval between requests, off-peak windows where required (PACER off-peak rule), conditional requests (HTTP If-Modified-Since / ETag) to avoid re-downloading unchanged content.
- Identify the client with a real User-Agent and contact info; respect robots.txt and documented usage policies; read each major source's terms of use and record compliance per source.
- Prefer official feeds (RSS/notice lists) over scraping wherever they exist — lighter on the source and more reliable. PROJECT.md already calls for this; enforce it.
- Cap the adaptive scheduler with a hard politeness ceiling — "intensify" means "up to a documented max," not "unbounded."
- Cache aggressively; only fetch full content when a cheap signal (feed entry, ETag, content-length, index page) indicates a probable change.
- For PACER specifically: be deliberate about whether/how it is used, the billing implications, and stay strictly within its developer policy.

**Warning signs:**
Rising 429/403 responses, sudden 503s, CAPTCHAs appearing. A court contacting the team. Polling intervals trending toward "every few minutes." No robots.txt or ToS review on file for major sources.

**Phase to address:**
Scheduler / ingestion phase. The politeness budget and per-source policy must be designed alongside the adaptive cadence, and a ToS review is a prerequisite before scaling to all ~140 sources.

---

### Pitfall 9: No verifiable provenance / audit trail for a published change

**What goes wrong:**
A downstream consumer (or, later, a paying customer) acts on a change and asks "where did this come from, and is it right?" The system cannot produce the original source document, the exact URL and fetch timestamp, the verbatim before/after text, who reviewed it, and when. Without provenance, every change is unverifiable on demand, disputes cannot be resolved, and a wrong change cannot be traced to its cause. In a domain with "high legal stakes," unaccountable output is a liability.

**Why it happens:**
Teams store the LLM's summary and the structured fields but discard the raw source snapshot and the review metadata. Provenance feels like overhead until the first dispute.

**How to avoid:**
- For every change, persist immutably: source URL, fetch timestamp, raw retrieved bytes (HTML/PDF), extracted/normalized text, the computed diff, the LLM output and the model/prompt version, the reviewer identity and decision, and all timestamps.
- The API should be able to return, or link to, the supporting evidence for any change it exposes.
- Version the API payloads so a correction is visible as a new version, not a silent overwrite.
- Make changes append-only/auditable; corrections are new records that supersede, not edits that erase history.

**Warning signs:**
Raw source documents not retained. LLM prompt/model version not recorded with the output. Reviewer decisions not timestamped or attributed. No way to answer "show me the source for this change."

**Phase to address:**
Data-model phase (provenance schema) and review-queue phase (capturing reviewer metadata); surfaced in the API phase.

---

### Pitfall 10: Reviewer fatigue and rubber-stamping erode the human safeguard

**What goes wrong:**
The human-review queue is the product's core accuracy guarantee. But if it is full of noise (Pitfall 2), poorly prioritized, or just high-volume, reviewers start approving without truly reading — especially since the AI summary looks authoritative. The safeguard becomes theater: the queue exists, items get approved, but human judgment is no longer actually applied. The most consequential change can be approved with the least scrutiny.

**Why it happens:**
Teams build the queue UI and assume the human will be diligent. They do not measure review quality, do not prioritize by risk, and present the AI summary so prominently that the reviewer anchors on it instead of the source text.

**How to avoid:**
- Drive queue volume down by killing noise upstream (Pitfall 2) — protect reviewer attention as a scarce resource.
- Prioritize the queue by severity/jurisdiction so high-stakes changes get the freshest attention, not buried mid-list.
- Design the review UI to force verification against source: show verbatim old vs new text prominently; the AI summary is supporting context, not the headline. Consider requiring the reviewer to confirm specific extracted fields (fee, date, form number) rather than one blanket "approve."
- Track review-quality signals: time-on-item, post-approval error catches, sampled re-review. A reviewer approving everything in seconds is a red flag.
- Avoid presenting AI output with false confidence — surface model uncertainty so reviewers know where to look hardest.

**Warning signs:**
Approval times trending toward seconds. Near-100% approval rate. Errors found downstream that "passed review." Reviewers report the queue is overwhelming.

**Phase to address:**
Review-queue phase. UI design and queue prioritization are core deliverables; review-quality metrics should be built in, not added later.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| One generic scraper for all ~140 sources | Fast to start | Breaks constantly; per-source quirks unhandled; silent failures | Only as a thin shared core under per-source adapters — never as the whole solution |
| Byte/DOM diff with no normalization | Trivial to implement | Floods review queue with noise; destroys reviewer trust | MVP for *feed-backed* clean sources only; never for PDFs or scraped HTML |
| Single date field per change | Simple schema | Effective-date errors; cannot represent future-dated changes | Never — the three-date model is core to the product premise |
| Storing only the LLM summary, not raw source | Less storage | No provenance; unverifiable changes; no re-diff on prompt change | Never — raw retention is a legal-defensibility requirement |
| Trusting classifier output to route auto-publish | Less reviewer load | Unreviewed wrong change goes live | Never without confidence gating + rollback |
| Hardcoding the source list once | Ship faster | Coverage gaps as courts add channels | Acceptable for MVP if a re-audit process is scheduled |
| Skipping per-source ToS/robots review | Faster onboarding of sources | Blocks, possible legal exposure (esp. PACER) | Never for PACER; risky elsewhere |
| No FETCH_FAILED state (only changed/unchanged) | Simpler pipeline | Silent false negatives on legal rules | Never |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Court websites (HTML) | Treating HTTP 200 as success | Verify content fingerprint; detect soft-404s, login walls, maintenance pages |
| Court PDFs | Assuming a text layer exists; diffing PDF binary | Detect text-vs-scanned, OCR when needed, diff normalized text, validate non-empty |
| RSS / notice feeds | Assuming a feed is complete and authoritative | Feeds often omit local orders; corroborate with page scraping; treat feed as a hint |
| PACER | Scraping aggressively / avoiding billing | Off-peak pulls, strict policy compliance; avoiding billing risks prosecution |
| Claude / LLM API | Trusting fluent output; no version pinning | Pin and record model+prompt version; ground on diff text; validate extractions |
| Downstream API consumer | Silently overwriting a corrected change | Versioned payloads; explicit "effective now" vs "effective later"; retraction signal |
| State legislature sources | Monitoring only courts for exemptions | Exemption amounts change via legislatures — a separate source class |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Re-downloading unchanged content every poll | Bandwidth waste, source throttling | Conditional requests (ETag/If-Modified-Since), cheap pre-checks | When source count grows and polling intensifies |
| Running the LLM on every poll of every source | High cost, slow cycles, rate limits | LLM only on *candidate* changes detected by cheap text-hash | Once ~140 sources poll daily+ |
| Unbounded adaptive polling near effective dates | Source blocks, IP bans | Hard politeness ceiling on intensification | When multiple effective dates cluster |
| Synchronous full-pipeline per source | One slow source stalls the run | Decouple fetch / diff / LLM / publish into stages with queues | As source count and PDF sizes grow |
| OCR on every PDF every poll | Slow, expensive, non-deterministic noise | Cache by content hash; OCR only changed/new PDFs | Immediately with scanned-PDF-heavy districts |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Treating scraped HTML/PDF as trusted input | Malformed/hostile content corrupts pipeline or prompt-injects the LLM | Sanitize; sandbox extraction; isolate LLM input; never let page content alter system instructions |
| No authn/authz on the downstream API | Unauthorized consumers, scraping of your verified data | API keys/auth, rate limits, per-consumer access |
| Storing PACER credentials / billing-linked access loosely | Account compromise, unexpected billing, ToS breach | Secrets management; least-privilege; monitor usage |
| Mutable change history | A wrong/altered record cannot be detected or audited | Append-only, immutable provenance store |
| LLM prompt injection from rule text ("ignore previous instructions" embedded in a scraped doc) | Misclassification, false summary | Structurally separate instructions from document content; constrain output schema |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| AI summary shown as the headline, source text hidden | Reviewer anchors on AI, misses errors | Verbatim old/new text prominent; summary as secondary context |
| Flat, unprioritized review queue | High-severity changes buried; reviewed late | Sort/filter by severity, jurisdiction, effective-date proximity |
| One blanket "Approve" button | Reviewer approves without checking each extracted field | Field-level confirmation for fee/date/form number |
| No visibility into source/provenance in the queue | Reviewer cannot verify; approves on faith | One-click access to source URL, raw doc, fetch time |
| API exposes changes without effective-date status | Downstream applies a not-yet-effective rule | Explicit state: pending / effective-now / effective-on-date |
| No noise/health dashboard for operators | Silent scraper failures and rising noise go unnoticed | Per-source health + queue noise metrics surfaced operationally |

## "Looks Done But Isn't" Checklist

- [ ] **Scraper:** Often missing FETCH_FAILED detection — verify a soft-404 / login wall / empty PDF is NOT recorded as UNCHANGED.
- [ ] **Change detection:** Often missing normalization — verify a copyright-year bump or PDF re-save does NOT create a queue item.
- [ ] **PDF extraction:** Often missing scanned-PDF handling — verify an image-only order is OCR'd, not silently extracted as empty.
- [ ] **Effective dates:** Often missing the future-dated path — verify a change announced today, effective in 6 months, stays PENDING and activates on the date.
- [ ] **Effective dates:** Often missing relative-date resolution — verify "30 days after entry" is computed or escalated, never dropped.
- [ ] **Auto-publish tier:** Often missing rollback — verify a wrong auto-published change can be retracted from the API.
- [ ] **LLM extraction:** Often missing validation — verify a fee that doesn't parse as currency or an implausible date is flagged, not published.
- [ ] **Provenance:** Often missing raw-source retention — verify you can produce the original document and fetch timestamp for any change.
- [ ] **Coverage:** Often missing channels — verify each district's general/standing orders pages are registered, not just "local rules."
- [ ] **Scheduler:** Often missing the PENDING→ACTIVE job's own monitoring — verify an alert fires if the activation job fails.
- [ ] **Politeness:** Often missing per-source ToS review — verify PACER and major sources have documented compliance.
- [ ] **API:** Often missing correction semantics — verify a retracted/corrected change is visibly versioned, not silently overwritten.

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Silent scraper failure (missed change) | HIGH | Re-scrape full history of affected source; diff against last-known-good; notify downstream of any missed change; add fingerprint check to prevent recurrence |
| Diff noise flooding queue | MEDIUM | Add/strengthen normalization; bulk-dismiss noise; retroactively tune; communicate to reviewers |
| LLM misclassification published downstream | HIGH | Retract via API versioning; notify consumers; correct record; add case to regression set; tighten confidence gate |
| Effective-date error (early/late activation) | HIGH | Correct date; re-issue change with proper state; notify downstream; reconcile what was applied during the wrong window |
| Wrong auto-published change | HIGH | One-click rollback; API retraction signal; route similar future changes to human review |
| Court block / IP ban | MEDIUM | Pause polling that source; contact court; switch to feed/lower cadence; rotate to compliant access; backfill missed window |
| Coverage gap discovered | MEDIUM | Register the missed channel; backfill its history; audit peer districts for the same gap |
| PDF extraction corruption | MEDIUM | Re-extract with correct (OCR) path; re-diff; re-summarize; add PDF-type detection |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Silent scraper failure | Ingestion / scraping foundation | Inject a soft-404 / empty PDF in tests; confirm FETCH_FAILED + alert, not UNCHANGED |
| Diff noise flooding queue | Change-detection / diffing | Feed a copyright-year-only change; confirm no queue item; measure queue noise <10% |
| LLM hallucination on legal text | LLM diff/classification/summarization | Run regression set of real past changes; confirm grounded, validated output; spot-check vs source |
| Auto-publish wrong change | Tiered-routing (+ API for rollback) | Confirm low-confidence/large/rule-text changes route to review; confirm rollback works |
| Effective-date errors | Data-model + scheduler | Confirm three-date model; future-dated change stays PENDING and activates on date; relative dates resolved/escalated |
| Coverage gaps | Source-mapping / ingestion design | Confirm every district channel registered; re-audit process defined; zero-change districts flagged |
| PDF extraction failures | Ingestion / extraction | Test scanned + multi-column + tabular PDFs; confirm OCR routing and non-empty validation |
| Rate limiting / ToS / blocks | Scheduler / ingestion | Confirm per-source politeness ceiling, conditional requests, documented ToS compliance (esp. PACER) |
| No provenance / audit trail | Data-model + review-queue | Confirm raw source, prompt/model version, reviewer + timestamps retrievable for any change |
| Reviewer fatigue / rubber-stamping | Review-queue | Confirm queue prioritized by severity; source text prominent; review-quality metrics tracked |

## Sources

- Stanford / Oxford Journal of Legal Analysis — "Large Legal Fictions: Profiling Legal Hallucinations in Large Language Models" (legal hallucination rates 58-88%; worse on niche/older jurisdictions): https://academic.oup.com/jla/article/16/1/64/7699227 — HIGH
- arXiv — "Not Wrong, But Untrue: LLM Overconfidence in Document-Based Queries" (interpretive overconfidence as dominant failure mode; ~30% of outputs contain a hallucination): https://arxiv.org/pdf/2509.25498 — HIGH
- arXiv — "Place Matters: Comparing LLM Hallucination Rates for Place-Based Legal Queries" (jurisdiction-dependent hallucination): https://arxiv.org/html/2511.06700v1 — MEDIUM
- PACER — "Are there any limits to PACER usage?" and off-peak data-pull guidance (account suspension for congestion; 6pm-6am scraping window; billing-avoidance prohibition): https://pacer.uscourts.gov/help/faqs/are-there-any-limits-pacer-usage and https://pacer.uscourts.gov/announcements/2021/05/10/reminder-limit-large-data-pulls-non-peak-hours — HIGH
- Free Law Project — Juriscraper (court-scraping toolkit; "several hundred point releases" adapting to changing court sites; centralizing scraping because per-org scrapers duplicate maintenance): https://free.law/projects/juriscraper/ and https://github.com/freelawproject/juriscraper — HIGH
- Web-scraping post-mortems — "Most Web Scrapers Break for the Same Reasons" / PromptCloud / Firecrawl / Grepsr (silent failure, DOM-shift breakage, 10-15% weekly breakage, normalization as the quiet failure point): https://yagneshmangali.medium.com/most-web-scrapers-break-for-the-same-reasons-656da4833b2f , https://www.promptcloud.com/blog/how-to-fix-web-scraping-errors-2026/ , https://www.firecrawl.dev/blog/web-scraping-mistakes-and-fixes — MEDIUM
- Regulatory-change-monitoring industry sources — Visualping / Regology / NAVEX (manual monitoring misses updates; structured routing; need for human oversight on automated systems): https://visualping.io/blog/regulatory-compliance-monitoring , https://www.regology.com/the-ultimate-regulatory-change-management-q-a-guide — MEDIUM
- Document change-detection research — survey + X-Diff (semantic vs surface diffing; key-based matching to reduce noise): https://arxiv.org/pdf/2307.07691 — MEDIUM
- Web-scraping legal compliance — GroupBWT (contractual ToS limits, circumventing rate limits viewed unfavorably by courts): https://groupbwt.com/blog/is-web-scraping-legal/ — MEDIUM
- Domain reasoning on U.S. bankruptcy rule structure (Title 11, FRBP, Official Forms effective-date conventions, district local/general/standing orders, state exemption statutes) — training data + reasoning — MEDIUM

---
*Pitfalls research for: U.S. bankruptcy regulatory-change monitoring service*
*Researched: 2026-05-20*
