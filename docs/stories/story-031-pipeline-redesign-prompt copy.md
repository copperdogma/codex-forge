# Pipeline Redesign Prompt for Planning Model

## Context: Fighting Fantasy Gamebook Processing Pipeline

We're building an AI-first pipeline to process scanned Fighting Fantasy gamebooks (choose-your-own-adventure books) into structured JSON. Each book has ~400 numbered gameplay sections (e.g., "1", "2", "3"...) that need to be accurately extracted.

### Current Architecture (5-stage AI-first pipeline)

1. **Intake** → Unstructured PDF processing → `elements.jsonl` (1316 elements across 113 pages)
2. **AI Scan** → Detect section boundaries → `section_boundaries.jsonl` 
3. **AI Extract** → Extract section content and gameplay data → `portions_enriched.jsonl`
4. **Build** → Assemble into FF Engine JSON format → `gamebook.json`
5. **Validate** → Quality checks → `validation_report.json`

### The Problem: Batching vs. Boundary Detection

**Core Contradiction:**
- AI models have token limits (~128k context, but responses limited to ~4k-16k tokens)
- We need to process 1316 elements to detect ~400 section boundaries
- Processing all elements at once exceeds response token limits → JSON truncation errors
- Batching is necessary, but batching creates boundary ambiguity problems

**Specific Failure:**
- Current implementation tries to scan all 1316 elements in single API call
- Response exceeds 4000 token limit, gets truncated mid-JSON
- Error: `JSONDecodeError: Unterminated string starting at: line 359 column 27 (char 12608)`

**Boundary Problem Explained:**
When batching elements by pages (e.g., pages 1-10, 11-20, 21-30):

1. **Duplicate Detections**: Section 10 might start at element X in batch 1, but batch 2 also sees section 10 continuation and detects it again → duplicate boundaries

2. **Missed Boundaries**: Section 9 ends at page 10, but batch 2 doesn't know section 9 started in batch 1 → treats continuation as new section → sections get split incorrectly

3. **Boundary Ambiguity**: Section boundary might fall exactly on batch boundary → unclear which batch owns it → potential duplicate or missed detection

4. **Context Loss**: Each batch lacks context from adjacent batches → can't determine if element is section start or continuation

### Why We Can't Just Add Back Old Pipeline Stages

We previously had a complex 8-stage pipeline with:
- `consensus_vote_v1` - Merge overlapping hypotheses
- `dedupe_ids_v1` - Remove duplicate section_ids  
- `resolve_overlaps_v1` - Handle overlapping portions
- `normalize_ids_v1` - Standardize IDs

These stages solve the batching problem, but:
- **We deleted them** as part of simplifying to AI-first approach
- They were over-engineered and hard to debug
- The goal was a cleaner, more AI-native pipeline
- Adding them back defeats the purpose of the redesign

### What We've Learned

**Successful Parts:**
- Intake stage works perfectly (1316 elements extracted with hi_res strategy)
- Element-based approach is correct (better granularity than page-based)
- AI can detect sections accurately (when given proper context)

**Failed Assumptions:**
- ❌ "AI scan can process all elements at once" → Token limits prevent this
- ❌ "No need for deduplication/consensus" → Batching creates duplicates
- ❌ "Simple batching by pages solves token limits" → Creates boundary issues

**Evidence from Old Pipeline:**
- Old pipeline had same problems (duplicate sections, boundary ambiguity)
- Old consensus/dedupe/resolve stages were attempts to fix batching issues
- Old pipeline also failed to properly handle boundaries (see Story 031 Issues 1-12)

### Design Constraints

**Must Have:**
1. Process 1316 elements across 113 pages to detect ~400 section boundaries
2. Respect AI token limits (response max ~4000 tokens for gpt-4o-mini)
3. Handle sections that span multiple batches (common case)
4. Avoid recreating complex consensus/dedupe/resolve pipeline
5. Keep pipeline simple and debuggable (artifacts at each stage)
6. Cost-effective (~$0.03 per book target)

**Should Have:**
1. Element-level precision (not page-level approximations)
2. Confidence scores for boundary detections
3. Ability to resume from failures
4. Clear artifact trail for debugging

**Constraints:**
- Elements are ordered by sequence and page
- Section numbers are 1-400 (known range)
- Sections are gameplay content, distinct from rules/intro (on different pages)
- Elements have IDs, types, text, page numbers, coordinates

### Current Implementation Details

**Elements Structure:**
- Each element has: `id`, `type`, `text`, `metadata.page_number`, `_codex.sequence`
- 1316 elements total across 113 pages
- Average ~11-12 elements per page
- Elements are already in reading order

**Current AI Scan Module** (`portionize_ai_scan_v1`):
- Formats all elements into single prompt: `[ID:abc | Type:X | Page:Y] Text...`
- Single API call to gpt-4o-mini with max_tokens=4000
- Expected JSON response: `{"boundaries": [{"section_id": "1", "start_element_id": "...", ...}]}`
- **Failed because**: Response exceeds token limit, gets truncated

**Expected Output:**
- `section_boundaries.jsonl`: One boundary per section with:
  - `section_id`: "1", "2", "3", etc.
  - `start_element_id`: ID of first element in section
  - `end_element_id`: ID of last element (optional)
  - `confidence`: 0.0-1.0
  - `evidence`: Why AI thinks this is a boundary

### Questions to Address

1. **How to batch intelligently?**
   - By pages? By element count? By token count?
   - Overlapping batches or strict boundaries?
   - How much overlap needed?

2. **How to handle boundary ambiguity?**
   - Pre-process to identify likely boundaries first (cheap pass)?
   - Post-process to merge/dedupe batch results?
   - Two-phase: candidate detection + validation?

3. **How to avoid recreating old pipeline complexity?**
   - Can we use AI to handle deduplication intelligently?
   - Can we batch in a way that prevents duplicates?
   - Can we design boundaries to avoid ambiguity?

4. **What's the minimal elegant solution?**
   - Fewest stages possible
   - Minimal code complexity
   - Maximum reliability

### Success Criteria

A successful solution should:
1. ✅ Process all 1316 elements without token limit errors
2. ✅ Detect all ~400 section boundaries accurately
3. ✅ Handle sections that span batch boundaries correctly
4. ✅ Avoid duplicate boundaries for same section
5. ✅ Keep pipeline simple (no complex consensus/dedupe logic)
6. ✅ Cost-effective (target ~$0.03 per book for AI stages)
7. ✅ Debuggable (clear artifacts, can inspect intermediate results)

### Reference Files

- Story 031: `docs/stories/story-031-ff-output-refinement.md` (full context)
- Implementation: `modules/portionize/portionize_ai_scan_v1/main.py` (current failed approach)
- Old pipeline: `configs/recipes/recipe-ff-unstructured-elements.yaml` (8-stage approach)
- Elements schema: `schemas.py` (UnstructuredElement schema)

---

## Your Task

Design an elegant, efficient solution that:
1. **Solves the batching problem** without recreating old pipeline complexity
2. **Handles boundary ambiguity** in a clean, AI-native way
3. **Minimizes pipeline stages** while maintaining reliability
4. **Provides specific implementation approach** (code structure, batching strategy, deduplication method)

Consider:
- Can we use AI more cleverly to avoid the problem?
- Is there a batching strategy that prevents boundary issues?
- Can we combine phases to reduce complexity?
- What's the minimal viable solution that actually works?

Provide:
1. **Solution architecture** (stages, data flow)
2. **Batching strategy** (how to split elements, how much overlap)
3. **Boundary resolution approach** (how to merge batch results)
4. **Implementation sketch** (key functions, data structures)
5. **Cost/performance estimate** (API calls, tokens, cost per book)
6. **Tradeoffs analysis** (what we gain/lose vs. current approach)

