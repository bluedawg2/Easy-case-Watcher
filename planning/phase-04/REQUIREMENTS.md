# Phase 4: Adaptive Polling & Deduplication - Requirements Analysis

## Phase Goal
Replace manual triggers with cadence-driven unattended polling that is fast where it matters and polite everywhere.

## Business Impact
This phase enables the system to operate unattended with adaptive polling schedules while maintaining politeness policies and preventing system overload.

## Key Requirements
1. **Polling Scheduler**: Compute `next_run_at` per source and run sources unattended at a daily default cadence with durable per-source task locks
2. **Cadence Policy**: Feed-backed sources poll at sub-daily cadence while static scraped sources poll daily
3. **Politeness Ceiling**: Hard per-source politeness ceiling so cadence intensification can never become unbounded
4. **AI Confidence Scoring**: AI output carries confidence score recorded on Change record for later routing decisions

## Implementation Approach
- Implement Procrastinate-based polling scheduler with per-source task locks
- Create cadence policy for daily default and sub-daily for feed-backed sources
- Implement politeness ceiling enforcement
- Add AI confidence scoring to processing pipeline

## Success Criteria Alignment
The implementation must ensure:
1. Proper polling scheduler with durable task locks
2. Appropriate cadence policies
3. Politeness ceiling enforcement
4. Confidence scoring integration