# Story: Sequential Page Numbering Refactor — Dual-Field Provenance

**Status**: To Do  
**Created**: 2025-12-18  
**Priority**: High

---

## Goal

Refactor the page identification system to eliminate the complexity of alphanumeric IDs (e.g., "051L", "051R"). Currently, split pages are handled using string suffixes, which makes basic math, sorting, and range-checking difficult and error-prone. 

The goal is to move to a dual-field integer-based system that separates **physical source provenance** from **logical pipeline sequence**.

---

## The Problem

1. **Broken Math**: You can't do `page_id + 1` with "051L".
2. **Logic Leaks**: Dozens of modules contain regex patterns like `re.match(r'^(\d+)([LR]?)$')` to "understand" what page they are on.
3. **Number Confusion**: Code often accidentally uses the base number (51) instead of the specific split ID (051L), leading to data loss or incorrect section mapping.
4. **Ordering Issues**: Alphanumeric sorting works for "L/R" but becomes brittle if new split patterns emerge.

---

## Proposed Solution: Dual-Field Numbering

Every page object in the pipeline should carry two distinct fields:

1. **`original_page_number` (int)**:
   - Represents the physical index/number in the source document (e.g., the PDF page index).
   - Used for provenance and referencing the original scan image.
   - For a split page, both the Left and Right halves share the same `original_page_number`.

2. **`page_number` (int)**:
   - A unique, sequential integer for every distinct page in the pipeline's current view.
   - If pages are NOT split, `page_number` == `original_page_number`.
   - If pages ARE split, `page_number` is a monotonically increasing counter (1, 2, 3...).
   - **Critical Assumption**: All downstream code (boundary detection, portionization, etc.) can use `page_number` blindly as a simple integer.

---

## Success Criteria

- [ ] **Sequential IDs**: Every page in the `pages_raw.jsonl` (and downstream) has a `page_number` that is a simple integer.
- [ ] **Simplified Logic**: Remove regex-based page parsing (`extract_num_and_suffix`, `parse_page_id`) from at least 3 major modules (portionize, extract, etc.).
- [ ] **Provenance Intact**: `original_page_number` is preserved for every element, allowing a trace back to the source image/PDF.
- [ ] **Math Works**: Downstream range checks and sorting use simple integer comparison.
- [ ] **Element IDs**: Update element ID generation (e.g., `P051L-S001`) to use the new sequential `page_number`.

---

## Tasks

### Phase 1: Impact Analysis
- [ ] **Audit `pages_raw.jsonl`**: Identify where `page_id` is first introduced and how many downstream schemas it affects.
- [ ] **Scan for regex parsing**: Grep for `[LR]` and `(\d+)` patterns used for page logic to ensure all are captured.

### Phase 2: Implementation (Upstream)
- [ ] **Update Intake**: Modify OCR ensemble or intake modules to emit both `original_page_number` and `page_number`.
- [ ] **Handle Splitting**: Update `ocr_split_v1` (or similar) to increment the sequential `page_number` while preserving the same `original_page_number`.
- [ ] **Schema Update**: Update `schemas.py` and `validate_artifact.py` to support the new fields.

### Phase 3: Downstream Migration
- [ ] **Update Elements**: Refactor element generation to use the new IDs.
- [ ] **Refactor Portionization**: Clean up the range-checking logic in `detect_boundaries_code_first_v1` and `coarse_segment_v1`.
- [ ] **Verify Forensics**: Ensure diagnostic tools (`scripts/trace_section_pipeline.py`) correctly display both numbers.

---

## Context

**Current Failure Mode**:
In Deathtrap Dungeon, pages are often split. When the pipeline sees page "12L" and "12R", some modules default to "12", causing the data from "12L" to be overwritten or ignored by "12R", or causing boundaries to fail because "13" is expected after "12", but "12R" is found instead.

**Why This Matters**:
- Achieving 100% accuracy (Story 074) requires robust page handling.
- Simplifying the code makes the pipeline more maintainable for non-FF books (Onward to the Unknown).
- Reduces the risk of "silent data loss" where one half of a split page is dropped.

---

## Work Log

### 2025-12-18 — Story created
- **Scope**: Migration to dual-field (original vs sequential) page numbering.
- **Next**: Audit current artifact schemas to see how many `page_id` references need updating.

