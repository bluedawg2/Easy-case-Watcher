# Phase 4 Implementation Plan

## Overview
Phase 4 focuses on adaptive polling and deduplication to enable unattended polling with politeness policies.

## Implementation Steps

### 1. Procrastinate-based polling scheduler
- Implement per-source `next_run_at` computation
- Set up durable per-source task locks
- Create polling scheduler with Procrastinate

### 2. Cadence policy implementation
- Daily default cadence for static scraped sources
- Sub-daily cadence for feed-backed sources
- Implement politeness ceiling enforcement

### 3. AI confidence scoring
- Add confidence scoring to processing pipeline
- Record confidence scores on Change records
- Implement confidence-based routing decisions

## Technical Requirements

### Core Functionality
- Scheduler computes `next_run_at` per source
- Unattended polling at appropriate cadences
- Politeness ceiling enforcement
- AI confidence scoring integration
- Task locking to prevent duplicate processing

## Success Criteria
All success criteria from roadmap will be met:
1. Polling scheduler computes `next_run_at` per source with durable task locks
2. Feed-backed sources poll at sub-daily cadence while static sources poll daily
3. Polling has hard per-source politeness ceiling
4. AI output carries confidence score recorded on Change record