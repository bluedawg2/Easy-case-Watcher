# Phase 3: PDF Ingestion & District Coverage - Requirements Analysis

## Phase Goal
Add PDF text extraction and onboard the initial ~3 federal bankruptcy court district tranche plus their launch-state exemption sources.

## Business Impact
This phase significantly expands the system's coverage to include PDF-based sources which are common in the bankruptcy court system. It addresses the need to process both text-based and image-based PDFs while maintaining the same reliability and error handling as with HTML sources.

## Key Requirements
1. **PDF Processing**: System must ingest and extract text from PDF source documents, detecting text-layer vs scanned PDFs
2. **OCR Integration**: Route image-only PDFs to OCR processing
3. **Content Normalization**: Handle de-hyphenation, line-number/header stripping before diffing
4. **District Coverage**: Onboard initial tranche of federal bankruptcy court districts
5. **State Exemption Rules**: Include state exemption rules for launch states

## Implementation Approach
- Implement PDF extraction core with pypdfium2/pdfplumber
- Add source_pattern and pdf_provenance to data model
- Create two-axis scanned-vs-broken classifier
- Implement PDF text normalization (de-hyphenation, line numbers, ligatures)
- Create PdfSourceAdapter document mode flowing end-to-end
- Onboard ~3-district tranche with criterion-5 Oregon LBR
- Add launch-state exemption source onboarding (OR/CA/TX)
- Implement selective pdfplumber tabular extraction

## Technical Considerations
- Content normalization to handle various PDF formats
- Per-source expected-content fingerprints to detect broken PDF processing
- Adaptive error handling for various failure modes (broken PDFs, empty content)
- Rate limiting and politeness policies to respect court website constraints
- Deduplication logic to prevent duplicate processing

## Dependencies
This phase depends on Phase 2 completion, as it builds on the source health monitoring and error handling established in Phase 2.

## Success Criteria Alignment
The implementation must ensure:
1. Proper PDF content extraction with text and image handling
2. Robust error handling for broken PDFs
3. Configurable source onboarding without code changes
4. Effective cross-channel deduplication
5. Content normalization to handle variations in PDF structure