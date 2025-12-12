# Story: OCR Content Type Detection Module

**Status**: Open  
**Created**: 2025-12-10  
**Parent Story**: story-061 (OCR ensemble fusion - IN PROGRESS)

## Goal

Add a content type detection module to the OCR pipeline that automatically tags OCR output with semantic content/layout types. This provides two benefits:
1) **Downstream routing hints** for frontmatter/gameplay/endmatter detection and the frontmatter/gameplay sectionizers.  
2) **Layout‑intent preservation** so future exporters can reconstruct richer outputs (e.g., HTML) without guessing from flattened text.

Default to an industry‑standard layout taxonomy rather than ad‑hoc HTML tags.

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

**Recommended baseline taxonomy (industry‑standard)**:
- **DocLayNet (11 labels)** is a common, cross‑domain layout analysis label set used by SOTA models:
  - `Title`, `Section-header`, `Text`, `List-item`, `Table`, `Picture`, `Caption`, `Formula`, `Footnote`, `Page-header`, `Page-footer`.
  - Rationale: richer than PubLayNet, directly supports our needs (headings vs body, lists, tables, figures/captions, headers/footers), and maps cleanly to HTML later.
- **PubLayNet (5 labels)** is a simpler academic‑paper taxonomy often used in layout models:
  - `Title`, `Text`, `List`, `Table`, `Figure`.
  - Useful as a fallback or for lightweight models, but too coarse for FF books.

**Mapping for pipeline use (examples)**:
- `Title` / `Section-header` → strong positive signal for section starts; candidates for gameplay/frontmatter headers.
- `Text` → default narrative/rules paragraphs.
- `List-item` → likely TOC entries, bullets, numbered instructions; should not be misread as gameplay headers.
- `Table` / `Picture` / `Caption` / `Formula` / `Footnote` / `Page-header/footer` → non‑gameplay structural regions; preserve for export and avoid false boundaries.

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
  - **Prioritize DocLayNet/PubLayNet labels as our default** and document any gaps for gamebooks (e.g., “adventure sheet/form” as a specialization of Table/Form).

- [ ] **Research Output**
  - Create research document with findings
  - Identify best practices and reusable ideas
  - Document which approaches are feasible for our pipeline
  - Recommend content type taxonomy for our use case

### Phase 2: Module Design

- [ ] **Define Content Type Taxonomy**
  - Adopt DocLayNet labels as core.
  - Add minimal codex‑forge extensions only if evidence demands (e.g., `Form` or `Adventure-sheet`), with explicit mapping to DocLayNet + HTML.
  - Optional hierarchical subtype field (e.g., `heading_level`) derived from size/position for downstream use.
  - Confidence scores for each type
  - Edge cases: mixed content, ambiguous regions

- [ ] **Design Module Interface**
  - Input: OCR output (pagelines or elements with text + bounding boxes)
  - Output: Same structure with added `content_type` and `content_type_confidence` per line/element, plus optional `content_subtype`.
  - Parameters: Model selection, thresholds, `allow_extensions`, and a `coarse_only` mode (PubLayNet‑style) for fast runs.
  - Schema: Define output schema for content type tags

- [ ] **Choose Implementation Approach**
  - Start with a hybrid: lightweight layout heuristics + LLM classifier for ambiguous regions.
  - Track a follow‑up path for a trained detector (LayoutLMv3 / YOLO‑DocLayNet) if cost/perf warrants.
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
  - Ensure downstream portionizers/guards read and exploit tags (header detection, TOC filtering, table avoidance).

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
  - DocLayNet dataset / label set (11 classes) and common finetuned models (YOLO/ LayoutLMv3).
  - PubLayNet label set (5 classes) and LayoutLMv3 layout‑analysis results.

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
### 20251212-1355 — Taxonomy direction clarified
- **Result:** Success.
- **Notes:** Based on SOTA layout analysis practice, default taxonomy should follow DocLayNet (11 labels) rather than HTML‑only tags; PubLayNet (5 labels) noted as coarse fallback. Added mapping notes to guide downstream sectionizers and future HTML export.
- **Next:** Execute Phase 1 research with DocLayNet/PubLayNet comparison, then design module interface around these labels.
