# Story 034: Stage-by-Stage Analysis & Unstructured Optimization

**Date**: 2025-11-29  
**Purpose**: Analyze each stage in `recipe-ff-unstructured.yaml` to understand what it does, how it processes Unstructured output, and identify optimization opportunities.

---

## Current Pipeline Stages (recipe-ff-unstructured.yaml)

### Stage 1: `unstructured_intake` → `elements.jsonl`
**Module**: `unstructured_pdf_intake_v1`  
**Input**: PDF file  
**Output**: `elements.jsonl` with rich element structure

**What it does**:
- Partitions PDF using Unstructured library
- Extracts structured elements with:
  - Element IDs (`elem-123`)
  - Element types (`Title`, `NarrativeText`, `ListItem`, etc.)
  - Text content
  - Page numbers
  - Precise bounding box coordinates
  - Reading order sequence (`_codex.sequence`)

**Status**: ✅ **OPTIMAL** - This stage properly leverages Unstructured's capabilities.

---

### Stage 2: `portionize_fine` → `window_hypotheses.jsonl`
**Module**: `portionize_sliding_v1`  
**Input**: `elements.jsonl`  
**Output**: Portion hypotheses with page spans

**What it's supposed to do**:
- Detect logical portions (sections, covers, TOC, etc.)
- Identify section boundaries and section IDs
- Create portion hypotheses with page_start/page_end spans

**How it currently processes Unstructured**:
1. **Converts elements → pages**: Groups elements by page, sorts, concatenates text
2. **Loses element-level information**:
   - ❌ Element IDs (can't reference back to source elements)
   - ❌ Element types (Title, NarrativeText, etc.) - only used for formatting hints
   - ❌ Precise bounding boxes (coordinates discarded)
   - ❌ Element boundaries (everything concatenated into page text)
3. **Sliding window over pages**: Windows of 8 pages, stride 1, sends to LLM
4. **LLM returns page spans**: Only page-level granularity, no element precision

**Problems**:
- **Information loss**: Rich element structure thrown away
- **Granularity too coarse**: Section boundaries forced to page boundaries
- **Misses section starts**: If section starts mid-page, LLM must guess from text
- **No element awareness**: Can't use element types (e.g., "Title" elements are likely section starts)
- **Inefficient**: LLM processes concatenated page text instead of structured elements

**Optimal approach for Unstructured**:
- **Work directly with elements**: Don't convert to pages
- **Use element types**: Detect section starts by finding `Title` or `NarrativeText` elements starting with numbers
- **Element-based windows**: Slide over element sequences, not pages
- **Preserve element IDs**: Reference elements by ID in portions
- **Element boundaries**: Portions can start/end at element boundaries (not just pages)

**Example optimization**:
```python
# Instead of: elements → pages → sliding window
# Do: elements → element-based portionization

# Detect section starts from element types
for elem in sorted_elements:
    if elem.type == "Title" and is_numeric_section(elem.text):
        section_id = extract_section_number(elem.text)
        # Start new portion at this element
        portion = create_portion(
            element_ids=[elem.id, ...],  # Reference elements by ID
            page_start=elem.metadata.page_number,
            section_id=section_id
        )
```

---

### Stage 3-6: Consensus, Dedupe, Normalize, Resolve
**Modules**: `consensus_vote_v1`, `dedupe_ids_v1`, `normalize_ids_v1`, `resolve_overlaps_v1`  
**Input**: Portion hypotheses/portions  
**Output**: Resolved portions

**What they're supposed to do**:
- **Consensus**: Merge overlapping hypotheses, vote on best portions
- **Dedupe**: Remove duplicate portion IDs
- **Normalize**: Standardize portion ID formats
- **Resolve**: Handle overlapping portions, choose best spans

**How they process Unstructured**:
- Work with portion hypotheses that have **page spans only**
- No element awareness - can't resolve at element-level granularity
- Overlaps resolved by page boundaries, not element boundaries

**Problems**:
- **Coarse resolution**: Can't resolve overlaps at element-level precision
- **No element references**: Can't preserve which elements belong to which portions

**Optimal approach**:
- **Element-aware resolution**: Resolve overlaps using element boundaries
- **Preserve element IDs**: Portions reference specific elements
- **Finer granularity**: Resolve conflicts at element-level, not page-level

**Status**: ⚠️ **SUBOPTIMAL** - Works but loses precision due to page-level granularity.

---

### Stage 7: `enrich_sections` → `portions_enriched.jsonl`
**Module**: `section_enrich_v1`  
**Input**: `elements.jsonl`, resolved portions  
**Output**: Enriched portions with section_id and targets

**What it's supposed to do**:
- Extract section IDs from portion text (regex: `^\s*(\d{1,4})\b`)
- Extract navigation targets (regex: `turn to (\d+)`)
- Add section_id and targets to portions

**How it currently processes Unstructured**:
1. **Converts elements → pages**: Again! (duplicate `elements_to_pages_dict()`)
2. **Extracts text by page span**: `extract_text(portion, pages, max_chars)` slices page text
3. **Regex on concatenated text**: Runs regex on page-span text

**Problems**:
- **Another conversion loss**: Converts elements to pages again, loses structure
- **Text slicing inefficiency**: Extracts text by page span, then slices characters
- **Missing element context**: Regex on concatenated text instead of structured elements
- **Can't leverage element types**: E.g., section numbers might be in `Title` elements

**Optimal approach**:
- **Work with element IDs**: If portions reference element IDs, extract text directly from elements
- **Element-aware extraction**: Section numbers often in `Title` or first `NarrativeText` element
- **Preserve element boundaries**: Don't concatenate, work with element structure

**Example optimization**:
```python
# Instead of: elements → pages → extract_text(page_start, page_end) → regex
# Do: element_ids → load elements → regex on specific elements

if portion.element_ids:
    # Load elements directly
    section_elements = [load_element(id) for id in portion.element_ids]
    # Section ID is likely in first Title or NarrativeText element
    section_id = find_section_id_in_elements(section_elements)
    targets = find_targets_in_elements(section_elements)
```

**Status**: ❌ **HIGHLY SUBOPTIMAL** - Converting elements to pages again, inefficient text extraction.

---

### Stage 8: `build_ff_engine` → `gamebook.json`
**Module**: `build_ff_engine_v1`  
**Input**: `elements.jsonl`, enriched portions  
**Output**: FF Engine gamebook JSON

**What it's supposed to do**:
- Assemble section text from portions
- Build navigation links from targets
- Create gamebook structure with sections

**How it currently processes Unstructured**:
1. **Converts elements → pages**: Third time! (another `elements_to_pages_dict()`)
2. **Slices text by page span**: `slice_text(pages, page_start, page_end)` extracts page text
3. **Assembles sections**: Concatenates page-span text into section text

**Problems**:
- **Triple conversion**: Converting elements to pages in 3 different modules
- **Inefficient text assembly**: Slicing and concatenating page text
- **No element precision**: Can't extract exactly the elements that belong to a section
- **Loses element metadata**: Can't preserve element-level provenance

**Optimal approach**:
- **Element-based assembly**: If portions reference element IDs, assemble directly from elements
- **Preserve element provenance**: Track which elements contributed to each section
- **Efficient extraction**: No need to convert to pages if working with element IDs

**Example optimization**:
```python
# Instead of: elements → pages → slice_text(page_start, page_end)
# Do: element_ids → load elements → assemble text

if portion.element_ids:
    elements = [load_element(id) for id in portion.element_ids]
    section_text = "\n\n".join(elem.text for elem in elements)
    section_provenance = {
        "source_elements": portion.element_ids,
        "element_types": [elem.type for elem in elements]
    }
```

**Status**: ❌ **HIGHLY SUBOPTIMAL** - Triple conversion, inefficient text assembly.

---

## Summary: What We're Losing

### Information Loss at Each Stage

1. **Portionization**:
   - ❌ Element IDs (can't reference source elements)
   - ❌ Element types (can't use Title/NarrativeText for detection)
   - ❌ Element boundaries (forced to page boundaries)
   - ❌ Precise coordinates (can't use layout for detection)

2. **Enrichment**:
   - ❌ Element structure (regex on concatenated text)
   - ❌ Element types (can't target Title elements for section IDs)

3. **Build**:
   - ❌ Element-level precision (can't extract exact elements)
   - ❌ Element provenance (can't track which elements contributed)
   - ❌ Efficient assembly (converting to pages just to slice text)

### Performance Impact

- **Triple conversion overhead**: Converting elements to pages 3 times
- **Inefficient text extraction**: Slicing page text instead of loading specific elements
- **Lost precision**: Page-level granularity instead of element-level
- **Missed opportunities**: Not leveraging element types for better detection

---

## Optimal Strategy for Unstructured

### Phase 1: Element-Aware Portionization
- **Work directly with elements**: Don't convert to pages
- **Use element types**: Detect section starts from `Title` or first `NarrativeText` elements
- **Element-based windows**: Slide over element sequences
- **Preserve element IDs**: Portions reference elements by ID

### Phase 2: Element-Referenced Portions
- **Portions carry element IDs**: `element_ids: ["elem-123", "elem-124"]`
- **Element-aware enrichment**: Extract section IDs from specific elements
- **Element-based assembly**: Build sections directly from element IDs

### Phase 3: Full Element Integration
- **Element-level provenance**: Track which elements contributed to each section
- **Coordinate preservation**: Keep bounding boxes for visual debugging
- **Type-aware processing**: Leverage element types throughout pipeline

---

## Recommendations

### Immediate (High Impact, Low Effort)
1. **Use `portionize_sections_v1`**: Regex-based, works on page text, but simpler than sliding window
2. **Consolidate `elements_to_pages*` functions**: At least remove duplication
3. **Add element ID preservation**: Track which elements contributed to each page

### Short-term (High Impact, Medium Effort)
1. **Element-aware portionization**: New module that works directly with elements
2. **Element-referenced portions**: Extend schema to include `element_ids`
3. **Optimize enrichment/build**: Use element IDs if present, fallback to pages

### Long-term (Full Optimization)
1. **Redesign portionization**: Element-based instead of page-based
2. **Element-first pipeline**: All stages work with element IDs
3. **Leverage element types**: Use types throughout for better detection

---

## Questions to Answer

1. **Why is `portionize_sliding_v1` missing 75% of sections?**
   - Is it because page-based sliding window misses section starts?
   - Would element-based portionization catch more sections?
   - Should we try `portionize_sections_v1` first (regex-based, simpler)?

2. **Can we test element-based portionization quickly?**
   - Prototype element-aware portionizer
   - Compare results with current approach
   - Measure section detection improvement

3. **Is page-based approach fundamentally flawed?**
   - Or is it just a configuration/prompt issue?
   - Would better LLM prompts fix it?
   - Or do we need element-level processing?

