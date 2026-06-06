# Phase 6: Effective-Date Lifecycle & Scheduler - Requirements Analysis

## Phase Goal
Make timing first-class — full lifecycle state machine, future-dated changes held pending, automatic activation on the effective date, and a forward-looking calendar.

## Business Impact
This phase enables the system to handle time-sensitive rule changes and provide forward-looking visibility into upcoming effective dates.

## Key Requirements
1. **Lifecycle state machine**: Full lifecycle state machine for changes
2. **Pending-effective handling**: Future-dated changes held pending with automatic activation
3. **Postponement/withdrawal**: Support for revising/withdrawing pending-effective changes
4. **Effective-date calendar**: Forward-looking calendar of changes
5. **API status distinction**: API distinguishes active vs pending-effective changes

## Implementation Approach
- Implement effective-date scheduler with monitoring
- Add relative date resolution with escalation
- Create postponement/withdrawal handling
- Implement effective-date calendar endpoint
- Add API status distinction

## Success Criteria Alignment
The implementation must ensure:
1. Pending-effective changes stay pending
2. Automatic activation on effective date
3. Postponement/withdrawal support
4. Effective-date calendar exposure
5. API status distinction