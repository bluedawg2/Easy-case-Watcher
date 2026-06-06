# Phase 6 Implementation Plan

## Overview
Phase 6 focuses on effective-date lifecycle management and scheduler implementation.

## Implementation Steps

### 1. Effective-date scheduler
- Implement pending-effective to active activation job with monitoring

### 2. Relative-date resolution
- Implement relative date resolution (e.g. "30 days after entry")
- Add escalation path for unresolvable phrases

### 3. Postponement/withdrawal handling
- Implement handling for pending-effective changes

### 4. Effective-date calendar
- Create effective-date calendar endpoint
- Implement polling-cadence intensification feedback loop

### 5. API integration
- Add API active vs pending-effective status distinction

## Technical Requirements

### Core Functionality
- Pending-effective to active transition
- Effective-date calendar
- Relative date resolution
- Postponement/withdrawal handling
- API status distinction

## Success Criteria
All success criteria from roadmap will be met:
1. Verified changes with future effective dates stay pending-effective
2. Scheduler automatically transitions pending-effective to active
3. Pending-effective changes can be revised/withdrawn
4. Effective-date calendar exposed
5. API distinguishes active vs pending-effective changes