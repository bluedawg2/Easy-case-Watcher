# Implementation Plan for Phase 2

## Overview
Phase 2 focuses on HTML scraping capabilities and source health monitoring to ensure comprehensive coverage and prevent silent scraper failures.

## Key Components

### 1. HTML Fetcher Adapter
- Develop adapter with per-source extraction configuration
- Implement boilerplate stripping functionality
- Create content normalization pipeline

### 2. Source Health Monitoring
- Implement tri-state fetch hardening
- Add content fingerprinting for scraper validation
- Create source health model with alerting

### 3. Source Onboarding
- Enable config-only source onboarding
- Implement politeness policies
- Add cross-channel deduplication

## Technical Requirements

### Core Functionality
- HTML content extraction with per-source configuration
- Robust error handling for various failure modes
- Content fingerprinting to detect scraper issues
- Configurable source onboarding without code changes
- Rate limiting and politeness policies

### Security & Reliability
- Content normalization to handle various HTML formats
- Proper error classification (404, login walls, empty pages)
- Deduplication to prevent duplicate processing

## Implementation Steps

### Step 1: HTML Fetcher Development
- Create HTML adapter with extraction configuration
- Implement boilerplate stripping
- Add content normalization

### Step 2: Health Monitoring
- Implement source health model
- Add staleness alarms
- Create layout-drift alerting

### Step 3: Source Onboarding
- Config-only source onboarding
- Politeness ceiling implementation
- Cross-channel deduplication

## Dependencies
This work builds on Phase 1 infrastructure and data models.

## Success Criteria
All success criteria from roadmap will be met:
1. HTML content extraction with per-source configuration
2. Source health monitoring that distinguishes all states
3. Staleness/layout-drift detection
4. Config-only source onboarding
5. Cross-channel change deduplication