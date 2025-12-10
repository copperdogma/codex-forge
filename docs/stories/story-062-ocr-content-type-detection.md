# Story: OCR Content Type Detection Module

**Status**: Open  
**Created**: 2025-12-10  
**Parent Story**: story-061 (OCR ensemble fusion - IN PROGRESS)

## Goal

Add a content type detection module to the OCR pipeline that automatically tags OCR output with semantic content types (heading, TOC, table, paragraph, list, etc.). This will enable downstream modules to make smarter decisions about text processing, layout handling, and structure extraction.

## Success Criteria

- [ ] Research phase complete: SOTA OCR engines and their content type detection approaches documented
- [ ] Module design: Content type taxonomy defined, module interface designed
- [ ] Module implementation: Content type detector module created in `modules/extract/` or `modules/adapter/`
- [ ] Integration: Module integrated into OCR pipeline recipes
- [ ] Validation: Content types correctly identified on test pages (headings, TOC, tables, paragraphs)
- [ ] Documentation: Module usage and content type taxonomy documented

## Context

**Current State**:
- OCR pipeline (`extract_ocr_ensemble_v1`) produces raw text lines with basic metadata (confidence, bounding boxes)
- Downstream modules (portionization, section detection) must infer content structure from text patterns
- No explicit content type tagging exists in the pipeline
- Content type information would help:
  - Better column detection (tables vs. paragraphs)
  - Improved section boundary detection (headings vs. body text)
  - Smarter text reconstruction (TOC formatting vs. narrative text)
  - Layout-aware processing (forms, tables, lists)

**Problem**:
- Downstream modules make assumptions about content structure that may be incorrect
- Column detection struggles with tables vs. multi-column text
- Section detection may miss headings or misclassify TOC entries
- Text reconstruction doesn't account for different formatting needs (TOC, tables, lists)

**Solution**:
- Add a content type detection module that analyzes OCR output (text + layout) to tag each element/region with its semantic type
- Research SOTA approaches from modern OCR engines (Google Cloud Vision, AWS Textract, Azure Form Recognizer, etc.)
- Implement a module that can be inserted into the OCR pipeline to enrich output with content type tags

## Tasks

### Phase 1: Research SOTA OCR Content Type Detection

- [ ] **Research Modern OCR Engines**
  - Google Cloud Vision API: Document structure detection, block types (TEXT, TABLE, etc.)
  - AWS Textract: Document analysis with layout detection (tables, forms, key-value pairs)
  - Azure Form Recognizer: Layout analysis (tables, selection marks, key-value pairs)
  - Adobe PDF Services API: Content structure extraction
  - Tesseract: Layout analysis capabilities (if any)
  - PaddleOCR: Structure analysis features
  - Document AI approaches: Academic papers on document structure detection

- [ ] **Document Content Type Taxonomies**
  - Compare taxonomies across engines (what types do they detect?)
  - Identify common patterns (heading detection, table detection, list detection)
  - Document layout-based vs. text-based detection approaches
  - Confidence scoring approaches

- [ ] **Research Output**
  - Create research document with findings
  - Identify best practices and reusable ideas
  - Document which approaches are feasible for our pipeline
  - Recommend content type taxonomy for our use case

### Phase 2: Module Design

- [ ] **Define Content Type Taxonomy**
  - Core types: heading, paragraph, table, list, TOC, form, image_caption, footnote, etc.
  - Hierarchical types (e.g., heading_1, heading_2, heading_3)
  - Confidence scores for each type
  - Edge cases: mixed content, ambiguous regions

- [ ] **Design Module Interface**
  - Input: OCR output (pagelines or elements with text + bounding boxes)
  - Output: Same structure with added `content_type` field per element/line
  - Parameters: Detection thresholds, model selection, confidence requirements
  - Schema: Define output schema for content type tags

- [ ] **Choose Implementation Approach**
  - Rule-based heuristics (text patterns, layout analysis)
  - LLM-based classification (GPT-4V for layout understanding)
  - Hybrid approach (heuristics + LLM for ambiguous cases)
  - Consider cost/performance tradeoffs

### Phase 3: Module Implementation

- [ ] **Create Module Structure**
  - Module ID: `content_type_detector_v1` (or better name)
  - Stage: `adapter` (transforms OCR output) or `extract` (if integrated into OCR)
  - Location: `modules/adapter/content_type_detector_v1/` or `modules/extract/`
  - Module YAML with input/output schemas

- [ ] **Implement Detection Logic**
  - Heading detection (font size, position, text patterns)
  - Table detection (grid structure, alignment, columnar text)
  - TOC detection (numbered entries, indentation patterns)
  - List detection (bullets, numbering, indentation)
  - Paragraph detection (default/fallback)
  - Form detection (boxes, fields, labels)

- [ ] **Add Confidence Scoring**
  - Per-type confidence scores
  - Multi-type assignments for ambiguous content
  - Threshold-based filtering

### Phase 4: Integration & Validation

- [ ] **Integrate into Pipeline**
  - Add module to OCR recipes (after OCR extraction, before or after text reconstruction)
  - Update schemas to include `content_type` field
  - Test with existing recipes (recipe-ff-canonical, recipe-ocr)

- [ ] **Validation Testing**
  - Test on known pages: headings (section headers), TOC pages, tables, forms
  - Verify content types match expectations
  - Check false positives/negatives
  - Validate on 20-page test set (story-060 regression suite)

- [ ] **Documentation**
  - Module README with usage examples
  - Content type taxonomy reference
  - Integration guide for recipes

## Research Sources

**To Investigate**:
- Google Cloud Vision API: [Document Text Detection](https://cloud.google.com/vision/docs/detecting-full-text)
- AWS Textract: [Analyzing Documents](https://docs.aws.amazon.com/textract/latest/dg/analyzing-document.html)
- Azure Form Recognizer: [Layout Analysis](https://learn.microsoft.com/en-us/azure/applied-ai-services/form-recognizer/concept-layout)
- Adobe PDF Services API: [Content Extraction](https://developer.adobe.com/document-services/docs/overview/pdf-services-api/)
- Academic: Document structure detection papers, layout analysis research

## Related Stories

- story-061: OCR ensemble fusion (provides OCR output to tag)
- story-057: OCR quality & column detection (could benefit from table vs. paragraph detection)
- story-059: Section detection & boundaries (could use heading detection)
- story-060: Pipeline regression testing (validation baseline)

## Work Log

### 2025-12-10 — Story created
- **Context**: Need to add semantic content type detection to OCR pipeline to improve downstream processing
- **Scope**: Research SOTA approaches first, then design and implement module
- **Priority**: Medium (enhances pipeline but not blocking)
- **Next**: Begin Phase 1 research on modern OCR engines and their content type detection approaches
