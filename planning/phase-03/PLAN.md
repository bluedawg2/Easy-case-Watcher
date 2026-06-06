# Implementation Plan for Phase 3

## Overview
Phase 3 focuses on PDF ingestion capabilities and district coverage to ensure comprehensive coverage and prevent silent PDF processing failures.

## Key Components

### 1. PDF Extraction Core
- Implement PDF extraction with pypdfium2/pdfplumber
- Add source_pattern and pdf_provenance to data model
- Create two-axis scanned-vs-broken classifier
- Create PDF fixtures for testing

### 2. PDF Text Processing
- Implement PDF text normalization (de-hyphenation, line numbers, ligatures)
- Create PdfSourceAdapter document mode flowing end-to-end
- Implement selective pdfplumber tabular extraction
- Add content normalization to handle variations in PDF structure

### 3. District Coverage
- Onboard ~3-district tranche with criterion-5 Oregon LBR
- Add launch-state exemption source onboarding (OR/CA/TX)
- Implement district-specific processing logic

## Technical Requirements

### Core Functionality
- PDF content extraction with text and image handling
- OCR integration for image-only PDFs
- Robust error handling for broken PDFs
- Content normalization for various PDF formats
- Per-source expected-content fingerprints to detect broken PDF processing

### Security & Reliability
- Content normalization to handle various PDF structures
- Proper error classification for failed PDF processing
- Rate limiting and politeness policies to respect court website constraints
- Deduplication logic to prevent duplicate processing

## Implementation Steps

### Wave 1: PDF Extraction Core
- Install pypdfium2/pdfplumber
- 0002 migration (source_pattern + pdf_provenance)
- FetchResult.reason_code implementation
- Two-axis scanned-vs-broken classifier
- PDF fixtures creation

### Wave 2: PDF Text Processing
- PDF text normalization (de-hyphenation, line numbers, ligatures)
- PdfSourceAdapter document mode flowing end-to-end through run_ingest

### Wave 3: District Coverage
- Index/listing adapter mode
- pdf_provenance stamping
- ~3-district tranche onboarding
- Criterion-5 Oregon LBR end-to-end replay

### Wave 4: State Exemption Rules
- Launch-state exemption source onboarding (OR/CA/TX)
- Selective pdfplumber tabular extraction
- Exemption text-change detection

## Dependencies
This work builds on Phase 2 infrastructure and data models.

## Success Criteria
All success criteria from roadmap will be met:
1. PDF content extraction with text and image handling
2. Proper error handling for broken PDFs
3. Configurable source onboarding without code changes
4. Effective cross-channel deduplication
5. Content normalization to handle variations in PDF structure