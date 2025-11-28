# Story: Fighting Fantasy output refinement

**Status**: Paused  
**Owner**: TODO  
**Created**: 2025-01-27  

---

## Goal
Refine and fix issues discovered in the Fighting Fantasy output pipeline. Address quality, accuracy, and correctness problems in the modules that produce FF Engine format output (`gamebook.json`), ensuring the exported gamebook data is accurate, complete, and properly structured.

## Success Criteria / Acceptance
- All identified FF output issues are documented, prioritized, and resolved.
- Output quality improvements are validated against Fighting Fantasy gamebook standards.
- Module refinements maintain backward compatibility with existing recipes and artifacts.
- Validation passes for refined outputs with no regressions in schema compliance.

## Approach
1. **Issue collection** — Document specific problems found in FF output (text accuracy, section mapping, navigation links, combat mechanics, item handling, etc.).
2. **Root cause analysis** — Trace issues back to source modules (extract, clean, portionize, resolve, enrich, build) and identify where refinements are needed.
3. **Module refinement** — Fix identified issues in the relevant modules, prioritizing high-impact problems first.
4. **Validation & testing** — Verify fixes against Fighting Fantasy samples and ensure no regressions.

**Critical Workflow Requirement**: Before starting work on ANY issue:
1. **THOROUGHLY investigate** exactly how the issue arose in the first place
2. **Trace it back** through the pipeline stages to understand the complete flow
3. **Document the root cause** with evidence (intermediate artifacts, code paths, data transformations)
4. **THEN** design a fix based on complete understanding
5. **THEN** implement the fix

Do not skip investigation or jump to implementation. Understanding must come first.

## Tasks
- [ ] **PRIORITY 1**: Pipeline meta-analysis and structural redesign (Issue 0) - prerequisite for all other fixes
- [ ] Document all identified FF output issues (user will provide)
- [ ] Prioritize issues by severity and impact
- [ ] Trace issues to source modules
- [ ] Implement fixes for high-priority issues
- [ ] Validate fixes against FF samples
- [ ] Update recipes/modules as needed
- [ ] Document any module behavior changes
- [x] Capture current FF build baseline (recipe, command, run_id, key artifact paths) for `06 deathtrap dungeon` before changes
- [ ] Perform Issue 0 investigation: trace representative sections (e.g., 32-39, 14-17) through artifacts (`window_hypotheses`, `portions_resolved`, `portions_enriched`, `gamebook.json`) and record root causes with evidence
- [ ] Draft pipeline redesign + quality gate plan (AI utilization audit, stage order, safeguards; includes stub/duplicate/misclassification detection)
- [ ] Decide and document preferred portionizer for FF (switch to `portionize_sections_v1` vs. improved sliding) and specify recipe changes needed
- [ ] Design validation/guardrail steps to flag/stop builds when stubs, duplicated sections, or mid-sentence starts appear
- [ ] Define structured enrichment targets and extraction approach for gameplay mechanics (combat stats, items, test-your-luck, conditional links)
- [ ] Add output validation checklist/tests for FF Engine format: `sectionNum`/description presence, whitespace normalization, deduping, gameplay classification, mechanics fields
- [ ] Add driver run-safety guardrails (no append-over-old artifacts, require `--force` or new run_id, auto-clean per stage)
- [ ] Add portionize/consensus guards: fail on mock rows, page-level spans for gameplay books, mixed timestamp epochs, or missing section anchors
- [ ] Add enrich/build guards: fail on high null section_id rate, empty stubs without override, duplicate text hashes across IDs, gameplay signals in non-gameplay sections

## Issue Priority & Dependencies

**Priority #1 (Prerequisite)**: Issue 0 - Pipeline meta-analysis
- Must be completed first to inform all other fixes
- Will determine structural changes needed
- Will identify where AI should replace code
- Will design safeguards and quality gates

**Priority #2 (Core portionization fixes)**: Issues 1, 3, 8
- **Issue 1**: Multiple sections merged (blocks proper section handling)
- **Issue 3**: Narrative split at boundaries (blocks proper content flow)
- **Issue 8**: Malformed boundaries (blocks proper section detection)
- **Dependency**: These are all portionization failures - fix together after Issue 0 analysis
- **Note**: May require switching to `portionize_sections_v1` or redesigning portionization approach

**Priority #3 (Detection and validation)**: Issues 2, 5, 6
- **Issue 2**: Silent stub creation (validation/quality gate problem)
- **Issue 5**: Duplicate sections (detection/deduplication problem)
- **Issue 6**: Misclassification (detection/classification problem)
- **Dependency**: Depends on Issue 0 (safeguard design) and Priority #2 fixes (proper portionization)
- **Note**: These are about catching/detecting problems - need quality gates from Issue 0

**Priority #4 (Enrichment and extraction)**: Issue 7
- **Issue 7**: Missing gameplay mechanics extraction
- **Dependency**: Depends on Priority #2 (proper sections) and Issue 0 (may identify need for AI-based extraction)
- **Note**: May require new enrichment module or AI-based extraction approach

**Priority #5 (Formatting and polish)**: Issue 4
- **Issue 4**: Section formatting improvements (sectionNum, descriptions, newlines)
- **Dependency**: Depends on all above (need proper sections first)
- **Note**: This is polish/UX improvement, not a correctness issue

**Implementation Order**:
1. Issue 0 (meta-analysis) → informs everything
2. Issues 1, 3, 8 (portionization) → fix core data structure problems
3. Issues 2, 5, 6 (validation/detection) → add safeguards and fix detection
4. Issue 7 (enrichment) → extract missing mechanics
5. Issue 4 (formatting) → polish output format

**Workflow for Each Issue**:
1. **Investigate thoroughly** - Trace the issue through pipeline stages, examine intermediate artifacts, understand complete data flow
2. **Document root cause** - With evidence showing exactly how the problem was introduced
3. **Design fix** - Based on complete understanding, not assumptions
4. **Implement** - Apply the fix with confidence that it addresses the root cause
5. **Validate** - Verify the fix resolves the issue and doesn't introduce regressions

## Notes
- Related to Story 030 (FF Engine format export) which established the current export pipeline.
- Focus on quality and correctness rather than new features.
- Issues may span multiple stages: OCR/extract → clean → portionize → resolve → enrich → build.

## Issues Identified

### Issue 0: Pipeline meta-analysis and structural redesign (PREREQUISITE)
**Severity**: Critical  
**Priority**: #1 - Must be done first to inform all other fixes

**Goal**: Understand how these quality failures occurred and redesign the pipeline to make them structurally impossible.

**Analysis Questions**:
1. **How did these issues creep in?**
   - Why did portionization create page-level portions instead of section-level?
   - Why did the system silently create 291 stubs without warning?
   - Why are duplicates and misclassifications not caught?
   - What validation/checks are missing in the pipeline?

2. **Are we underutilizing AI capabilities?**
   - Are we using code/regex for tasks better suited to AI API calls?
   - Example: Section detection uses regex `^\s*(\d{1,4})\b` - should this be an AI call that understands context?
   - Example: Continuation detection relies on `continuation_of` field - is the LLM prompt effective?
   - Example: Gameplay mechanics extraction (combat, items) - should be AI-driven, not pattern matching
   - Are we trying to solve hard problems with code when AI would be more robust?

3. **Is the pipeline structure/order wrong?**
   - Are we processing in an order that creates these problems?
   - Should section detection happen earlier/later?
   - Should validation happen at each stage, not just at the end?
   - Are stages too independent (no feedback loops)?

4. **What safeguards are missing?**
   - How can we make errors blindingly obvious early?
   - Should each stage validate its output before passing to next?
   - Should we have "quality gates" that fail loudly on obvious problems?
   - How do we prevent "confidently wrong" outputs?
5. **Are we under-leveraging AI where it’s strongest?**
   - Are we writing complex code to do things an AI API could trivially handle (e.g., boundary detection, classification, validation-by-cross-check)?
   - Are we making single high-stakes calls and trusting them, instead of sampling multiple calls and reconciling with a second AI vote/arbiter?
   - For any high-impact stage, are we allowing AI ensemble/consensus patterns (N identical calls + AI arbiter) before falling back to heuristics?

**Required Deliverables**:
1. **Root cause analysis** - Document how each issue type was able to occur
   - For each issue (1-8), trace through the pipeline stages to understand exactly how it arose
   - Examine intermediate artifacts at each stage to see where the problem was introduced
   - Document the complete data flow and transformations
2. **AI utilization audit** - Identify where we're using code instead of AI, and where AI would be better
3. **Pipeline structure review** - Evaluate stage order, dependencies, feedback loops
4. **Safeguard design** - Design validation/quality gates that catch these issues early
5. **Redesign proposal** - Structural changes to make these failures impossible

**Investigation Methodology**:
- Before proposing any fix, thoroughly investigate how the issue arose
- Trace data through each pipeline stage (extract → clean → portionize → resolve → enrich → build)
- Examine intermediate artifacts (window_hypotheses.jsonl, portions_resolved.jsonl, portions_enriched.jsonl, etc.)
- Understand the complete flow before designing a solution

**Success Criteria**:
- Pipeline redesign makes current failure modes structurally impossible
- Quality gates catch issues at the stage where they occur
- AI is used appropriately for complex pattern recognition/understanding tasks
- System fails loudly and clearly when quality is compromised
- No "silent failures" - all problems surface immediately

**Note**: This analysis will inform how Issues 1-8 are fixed. Don't just patch symptoms - fix the underlying structural problems.

### Issue 1: Multiple sections merged into single entries
**Severity**: High  
**Example**: Section "37" in gamebook.json contains sections 37, 38, and 39 all merged together.

**Root Cause Analysis**:
- `portionize_sliding_v1` creates page-level portions (e.g., P025 for page 25) rather than section-level portions
- `section_enrich_v1` detects only the first section number (37) in the text and assigns it as `section_id`
- `build_ff_engine_v1` uses that single `section_id` but includes all text from the entire page span
- Result: One gamebook section entry contains multiple numbered sections (37, 38, 39)

**Affected Modules**:
- `portionize_sliding_v1` - creates page-level portions instead of splitting on section numbers
- `section_enrich_v1` - only detects first section number, doesn't split portions
- `build_ff_engine_v1` - builds one section per portion, doesn't split multi-section portions

**Solution**:
- **Recommended**: Switch FF recipe from `portionize_sliding_v1` to `portionize_sections_v1`
  - `portionize_sections_v1` is designed to split on section number anchors (regex: `(?m)^\s*(\d{1,4})\b`)
  - It already handles multiple sections per page by detecting section numbers at line starts
  - Already used in other recipes (`recipe-ocr-enrich-sections-*.yaml`)
  - This will create separate portions for each section (37, 38, 39) instead of one page-level portion (P025)
- **Alternative**: Add post-processing adapter to split multi-section portions, but this is more complex and less efficient

### Issue 2: Silent stub creation hides portionization failures
**Severity**: High  
**Example**: Section 36 is created as an empty stub, but it actually exists merged into section 32 (which contains sections 32, 33, 34, 35, 36 all together).

**Root Cause Analysis**:
- `build_ff_engine_v1` silently creates empty stub sections for any target references that don't have corresponding sections
- Stubs are created to "satisfy validator" (prevent validation errors)
- However, many "missing" sections actually exist but are merged into other sections due to portionization failures
- The system treats stub creation as normal operation, hiding the fact that parsing/portionization failed
- Example: Section 36 is referenced but missing → stub created. Reality: Section 36 exists in section 32's text but wasn't split out.

**Affected Modules**:
- `build_ff_engine_v1` - creates stubs silently without warning or diagnosis
- No feedback loop to detect that "missing" sections might actually be merged elsewhere

**Problem with Current Approach**:
- Stubs mask portionization failures instead of surfacing them
- AI-led process should self-diagnose and detect when it's producing bad output
- Silent stub creation is a code smell - hiding failures instead of fixing them
- Validator passes, but output quality is compromised

**Solution Options**:
1. **Make stubs a hard error/warning** - Fail validation or emit high-priority warning when stubs are needed
2. **Pre-stub diagnosis** - Before creating stub, scan all existing section text for the missing section number; if found, flag as merged section failure
3. **Self-correction loop** - When stubs needed, re-run portionization with targeted hints to find the missing sections
4. **Prominent warnings** - At minimum, log high-priority warnings that output quality is compromised when stubs are created
5. **Stub provenance enhancement** - Mark stubs with confidence that they're actually missing vs. likely merged (requires diagnosis step)

**Recommended Approach**:
- Add pre-stub diagnosis: scan section text for missing section numbers
- If found merged, emit high-priority warning with details (which section contains it, what the merged text is)
- Consider making stub creation a validation failure or require explicit override
- Add feedback mechanism to portionization stage about missing sections

### Issue 3: Portionizer splits continuous narrative at page boundaries
**Severity**: High  
**Example**: Sections P012, P013, P014, P015 are one continuous narrative block (intro/background story) incorrectly split into four separate portions at page boundaries.

**Root Cause Analysis**:
- `portionize_sliding_v1` uses LLM API calls (OpenAI) with sliding window approach (window=8, stride=1)
- LLM is creating one portion per page instead of recognizing continuous narrative flow
- Text clearly continues across pages (e.g., "seeming to scream..." is mid-sentence, "attracted to it, not for the rewards..." is mid-sentence)
- LLM prompt says "If a span clearly continues an earlier portion mentioned in 'prior', set continuation_of" but:
  - Each window processes independently
  - LLM is being too conservative, creating page-level portions
  - `continuation_of` is not being set (all null)
- Consensus stage groups by identical spans - since each is a different page span, they don't get merged
- Result: One continuous narrative block split into multiple portions at arbitrary page boundaries

**Affected Modules**:
- `portionize_sliding_v1` - LLM prompt/approach not detecting continuations properly
- `consensus_vote_v1` - Only merges identical spans, doesn't merge adjacent continuations
- System prompt says "Stay generic; do not assume any series-specific structure" which may be causing over-conservative splitting

**Investigation Needed**:
1. Check if this was a mocked run (window_hypotheses show "notes": "mock")
2. Verify LLM is actually being called vs. fallback behavior
3. Review LLM prompt effectiveness for detecting narrative continuations
4. Check if windowing approach is causing page-boundary bias
5. Evaluate if different book types need different portionization strategies

**Solution Options**:
1. **Improve LLM prompt** - Make continuation detection more explicit and provide examples
2. **Post-process merging** - Add stage to merge adjacent portions with `continuation_of` relationships
3. **Book-type-specific portionizers** - Different strategies for novels vs. gamebooks vs. reference books
4. **Larger context windows** - Increase window size or add overlap analysis
5. **Continuation-aware consensus** - Modify consensus to merge portions with continuation relationships
6. **Validation feedback** - Detect when portions start mid-sentence and flag as errors

**User Insight**:
- "A novel is extremely easy to portionize compared to something like these FF books that have all sorts of different content types within them"
- Need different pipeline styles for different book types
- AI-led process should detect obvious failures (sections starting mid-sentence)

### Issue 4: Gameplay section formatting and metadata improvements
**Severity**: Medium (feature request / polish)  
**Example**: Section 12 has section number embedded in text, no description, and contains artificial newlines.

**Current Problems**:
1. **Section number embedded in text** - Section number (e.g., "12") is included at the start of `clean_text`, making it hard to render separately in UI
2. **No section description** - Gameplay sections lack succinct AI-generated descriptions (e.g., "Crazy Old Riddler" for section 12)
3. **Section number not as separate property** - Currently only available via `id` field, but should be explicit `sectionNum` property for numbered gameplay sections
4. **Artificial newlines in clean_text** - Text contains `\n` characters that break rendering in web/PDF/app contexts; should flow naturally to container

**Example Current Output**:
```json
{
  "id": "12",
  "text": "12\nThe door opens into a large, candle-lit room filled\nwith the most extraordinarily lifelike statues...",
  "clean_text": "12\nThe door opens into a large, candle-lit room filled\nwith the most extraordinarily lifelike statues..."
}
```

**Desired Output**:
```json
{
  "id": "12",
  "sectionNum": 12,
  "description": "Crazy Old Riddler",
  "text": "The door opens into a large, candle-lit room filled with the most extraordinarily lifelike statues...",
  "clean_text": "The door opens into a large, candle-lit room filled with the most extraordinarily lifelike statues..."
}
```

**Affected Modules**:
- `section_enrich_v1` - Should extract section number and strip from text
- `build_ff_engine_v1` - Should add `sectionNum` property, add description field, strip section numbers and newlines from text
- May need new enrichment stage or enhance existing one to generate descriptions

**Solution Approach**:
1. **Extract section number** - Parse section number from text start, add as `sectionNum` property (integer) for numbered gameplay sections
2. **Strip section number from text** - Remove leading section number and newline from `clean_text` and `text` fields
3. **Generate descriptions** - Add LLM call to generate succinct descriptions for gameplay sections (1-3 words, e.g., "Crazy Old Riddler", "Giant Fly Encounter")
4. **Normalize whitespace** - Remove artificial newlines from `clean_text`, replace with spaces or let text flow naturally
5. **Schema update** - Ensure FF Engine schema supports `sectionNum` and `description` fields (or add to provenance if schema doesn't allow)

**Implementation Notes**:
- Section number extraction: Use regex to detect leading number pattern (already done in `section_enrich_v1` but needs to be stripped from text)
- Description generation: Could be done in `section_enrich_v1` or new enrichment stage, or in `build_ff_engine_v1` when assembling sections
- Text normalization: Strip leading section number pattern, normalize newlines to spaces (or preserve only paragraph breaks if needed)
- Only apply to numbered gameplay sections (`isGameplaySection: true` and `id` is numeric)

### Issue 5: Duplicate sections with different IDs
**Severity**: High  
**Example**: Section 37 appears twice - once as `"37"` (numeric ID) and once as `"P025"` (portion ID), both containing the same merged text (sections 37, 38, 39).

**Root Cause Analysis**:
- `build_ff_engine_v1` creates sections from enriched portions
- When a portion has a `section_id` (e.g., "37"), it creates section with that ID
- But the same portion also gets included as a section with its `portion_id` (e.g., "P025")
- Result: Duplicate entries for the same content with different IDs
- Example: Portion P025 has `section_id: "37"` → creates both `"37"` and `"P025"` sections

**Affected Modules**:
- `build_ff_engine_v1` - should prefer `section_id` over `portion_id` when both exist, or dedupe by content
- May also be related to portionization creating multiple portions for same content

**Problem**:
- Duplicate sections waste space and create confusion
- Navigation links may point to wrong ID
- Validator may not catch this if both IDs are valid

**Solution Options**:
1. **Prefer section_id** - When building sections, if `section_id` exists and is numeric, use that; only use `portion_id` as fallback
2. **Dedupe by content** - Before finalizing sections, check for duplicate content and merge/remove duplicates
3. **Track source** - Mark which sections came from `section_id` vs `portion_id` to avoid conflicts
4. **Validation check** - Add validation step to detect duplicate content across different IDs

### Issue 6: Misclassification of gameplay sections
**Severity**: Medium  
**Example**: Section `P025` contains gameplay sections 37, 38, 39 with navigation links and combat info ("GIANT FLY SKILL 7 STAMINA 8"), but is marked `isGameplaySection: false` and `type: "template"`.

**Root Cause Analysis**:
- `build_ff_engine_v1` uses `classify_type()` and `is_gameplay()` functions to determine section type
- Classification logic may be too conservative or not detecting gameplay content properly
- Portions with P-prefixed IDs may be defaulting to non-gameplay types
- Function checks for `section_id.isdigit()` but P-prefixed portions don't have numeric section_id

**Affected Modules**:
- `build_ff_engine_v1` - `classify_type()` and `is_gameplay()` functions
- Classification logic doesn't properly detect gameplay content in P-prefixed portions

**Problem**:
- Gameplay sections marked as non-gameplay break filtering/rendering logic
- Type "template" is incorrect for actual gameplay content
- May affect validation or downstream processing

**Solution Options**:
1. **Improve gameplay detection** - Check for navigation links, combat info, choices, etc. regardless of ID format
2. **Content-based classification** - Analyze text content for gameplay indicators (combat stats, "Turn to", choices, etc.)
3. **Fix classification logic** - Don't rely solely on numeric section_id; check for gameplay signals in the content
4. **Post-classification review** - Add validation step to flag sections with gameplay content but wrong type

### Issue 7: Missing gameplay mechanics extraction
**Severity**: High  
**Example**: Section 39 contains "GIANT FLY SKILL 7 STAMINA 8" but no structured `combat` field. Section 16 has gem puzzle table but no structured `items` or conditional navigation data.

**Root Cause Analysis**:
- `section_enrich_v1` uses heuristics to detect targets but doesn't extract structured gameplay mechanics
- Combat information (SKILL/STAMINA stats) is in text but not parsed into `combat` object
- Item checks, test your luck, stat modifications are not being extracted
- `build_ff_engine_v1` expects these fields but they're not being populated by enrichment stage

**Affected Modules**:
- `section_enrich_v1` - Only detects section_id and targets, doesn't extract combat/items/test_luck
- May need more sophisticated enrichment module or LLM-based extraction

**Problem**:
- Rich gameplay mechanics are lost - combat stats, item checks, conditional navigation
- Output is less useful for game engines that need structured data
- Text parsing required downstream instead of clean structured data

**Solution Options**:
1. **Enhanced enrichment module** - Add LLM-based extraction of combat stats, items, test your luck, stat modifications
2. **Pattern-based extraction** - Use regex/patterns to detect "SKILL X STAMINA Y" format, item check patterns, etc.
3. **Multi-stage enrichment** - Separate enrichment passes for different mechanics (combat, items, navigation)
4. **Schema-aware extraction** - Extract based on FF Engine schema requirements

### Issue 8: Malformed section boundaries
**Severity**: Medium  
**Example**: Section 14 text starts with `"14-15 16-17\n\npainfully dry..."` which appears to be continuation text from section 13, not a proper section 14 start.

**Root Cause Analysis**:
- Section boundary detection is incorrect - section 14 is starting mid-content
- May be related to merged sections issue - section 13's text is being split incorrectly
- The "14-15 16-17" header suggests multiple sections were detected but boundaries are wrong
- Text "painfully dry and you feel a little dizzy" appears to continue from section 13's "Your throat is" ending

**Affected Modules**:
- `portionize_sections_v1` or portionization stage - incorrect boundary detection
- `section_enrich_v1` - may be assigning wrong section_id to text spans
- `build_ff_engine_v1` - using incorrect text boundaries

**Problem**:
- Sections start mid-sentence or mid-thought
- Content is fragmented incorrectly
- Makes sections confusing or unreadable

**Solution Options**:
1. **Improve boundary detection** - Better logic to find actual section starts (not just numbers in text)
2. **Context-aware splitting** - Check for sentence/paragraph boundaries when splitting sections
3. **Validation** - Detect sections that start mid-sentence and flag as errors
4. **Post-processing** - Merge sections that are clearly continuations

## Work Log
- 2025-01-27 — Story created to track FF output refinement issues. Awaiting user input on specific problems to address.
- 2025-01-27 — **Issue 1 documented**: Multiple sections (37, 38, 39) merged into single section entry. Root cause: `portionize_sliding_v1` creates page-level portions; `section_enrich_v1` only detects first section number; `build_ff_engine_v1` includes all text. 
  - **Analysis**: Page 25 clean_text contains sections 37, 38, 39 separated by newlines. `portionize_sliding_v1` creates one portion (P025) for entire page. `section_enrich_v1` detects only first section (37). `build_ff_engine_v1` uses section_id "37" but includes all page text.
  - **Solution identified**: Switch recipe to use `portionize_sections_v1` which splits on section number anchors at line starts. This module already exists and is used in other recipes.
- 2025-01-27 — **Issue 2 documented**: Silent stub creation hides portionization failures. Empty stubs are created for "missing" sections, but many actually exist merged into other sections (e.g., section 36 merged into section 32). 
  - **Analysis**: `build_ff_engine_v1` silently creates stubs to satisfy validator, masking portionization failures. Section 36 is referenced but missing → stub created. Reality: Section 36 exists in section 32's text (along with 32, 33, 34, 35, 36 all merged). 
  - **Problem**: AI-led process should self-diagnose and surface issues, not hide them. Silent stub creation is a code smell.
  - **Solution options**: Pre-stub diagnosis (scan for merged sections), make stubs warnings/errors, add self-correction feedback loop, or at minimum prominent warnings when output quality is compromised.
- 2025-01-27 — **Issue 3 documented**: Portionizer splits continuous narrative at page boundaries. Sections P012-P015 are one continuous narrative block incorrectly split into four portions.
  - **Analysis**: `portionize_sliding_v1` uses LLM API calls but creates one portion per page instead of recognizing narrative flow. Text clearly continues across pages (mid-sentence starts like "seeming to scream...", "attracted to it, not for..."). LLM should detect continuations via `continuation_of` but all are null. Consensus stage doesn't merge continuations, only identical spans.
  - **Investigation needed**: Check if run was mocked, verify LLM calls, review prompt effectiveness, evaluate windowing approach, consider book-type-specific strategies.
  - **User insight**: Different book types need different pipeline styles. Novels are easy; FF books have mixed content types. AI should detect obvious failures (sections starting mid-sentence).
- 2025-01-27 — **Issue 4 documented**: Gameplay section formatting and metadata improvements (feature request).
  - **Problems**: Section numbers embedded in text, no descriptions, artificial newlines break rendering, section number not as separate property.
  - **Requirements**: Extract `sectionNum` as integer property, generate succinct AI descriptions, strip section numbers and newlines from `clean_text`, normalize whitespace for proper rendering.
  - **Example**: Section 12 should have `sectionNum: 12`, `description: "Crazy Old Riddler"`, and clean text without leading "12\n" or artificial newlines.
- 2025-01-27 — **Issues 5-8 documented**: Additional quality issues found during file review.
  - **Issue 5**: Duplicate sections - Section 37 appears as both `"37"` and `"P025"` with same content. `build_ff_engine_v1` should prefer `section_id` over `portion_id` or dedupe.
  - **Issue 6**: Misclassification - `P025` contains gameplay (sections 37-39, combat, navigation) but marked `isGameplaySection: false`, `type: "template"`. Classification logic needs improvement.
  - **Issue 7**: Missing mechanics extraction - Combat stats ("GIANT FLY SKILL 7 STAMINA 8"), items, test your luck not extracted into structured fields. Need enhanced enrichment.
  - **Issue 8**: Malformed boundaries - Section 14 starts with continuation text from section 13. Boundary detection is incorrect, sections start mid-content.
- 2025-01-27 — **Issue 0 added (Priority #1)**: Pipeline meta-analysis and structural redesign.
  - **Goal**: Understand root causes and redesign pipeline to make failures structurally impossible.
  - **Key questions**: How did issues creep in? Are we underutilizing AI? Is pipeline structure wrong? What safeguards are missing?
  - **Critical**: Must be done first to inform all other fixes. Don't just patch symptoms - fix underlying structural problems.
  - **Deliverables**: Root cause analysis, AI utilization audit, pipeline structure review, safeguard design, redesign proposal.
- 20251128-1514 — Reviewed story format and expanded task checklist for actionable coverage of Issue 0 and downstream fixes.
  - **Result:** Success.
  - **Notes:** Verified tasks section existed and added baseline capture, artifact tracing, redesign/guardrail planning, portionizer decision, enrichment targets, and validation checklist tasks to make work testable.
  - **Next:** Capture current FF baseline run_id and artifacts, then begin Issue 0 trace for sections 32-39 and 14-17.
- 20251128-1518 — Captured FF baseline and began Issue 0 trace (sections 32–39, 14–17).
  - **Result:** Success (baseline captured) / Partial (trace ongoing).
  - **Baseline:** run_id `deathtrap-ff-engine`, recipe `configs/recipes/recipe-ff-engine.yaml`, rerun cmd: `python driver.py --recipe configs/recipes/recipe-ff-engine.yaml --run-id deathtrap-ff-engine`. Key artifacts: `output/runs/deathtrap-ff-engine/{window_hypotheses.jsonl,portions_resolved.jsonl,portions_enriched.jsonl,gamebook.json}`.
  - **Findings:** `window_hypotheses` entries are page-level with `notes: "mock"` and `type: "page"` → `portionize_sliding_v1` ran in mock/page-only mode (no LLM/section detection), explaining merged sections and missing continuations. Page 25 clean text contains sections 37–39; enrichment left `section_id` null; `gamebook.json` shows P025 (template, non-gameplay) plus stub sections 38/39 with empty text and duplicate section 37. Page 32 content includes 32–36 merged; stubs 33–36 empty. Pages 14–17: P014–P017 page-level portions; only P016 carries `section_id: 1`; P017 holds text for sections 3–4 but no `section_id`, illustrating narrative splits at page boundaries and missing numbering.
  - **Next:** Confirm why `portionize_sliding_v1` produced `notes: "mock"` (config vs. fallback); inspect module logic and run params; continue tracing additional sections to map where stubs/duplicates originate; propose quality-gate checks for mock/page-level outputs.
- 20251128-1523 — Traced mock artifacts cause for Issue 0 (sections 32–39, 14–17).
  - **Result:** Success (root cause identified).
  - **Notes:** `window_hypotheses.jsonl` contains two populations: 113 mock page-level rows (created_at ~2025-11-28T00:26:21Z, `notes: "mock"`, `type: "page"`, `confidence: 1.0`, `portion_id` P###) plus 726 real LLM spans (created_at ~07:01Z). The file was not cleaned before the later real run (driver only removes artifacts when `--force` is used). Because module appends, leftover mock rows survived and carried perfect confidence, so `consensus_vote_v1` selected them, leading to page-level portions (e.g., P025) and triggering merged sections, stubs, and misclassification. Evidence paths: `output/runs/deathtrap-ff-engine/window_hypotheses.jsonl` (mock+real mix), mock rows match `driver.py:mock_portionize` schema; real LLM row example: `portion_id: front_cover`, `created_at: 07:01:15Z`. Sections 37–39 and 32–36 failures directly trace to these mock page spans outcompeting true section spans.
  - **Next:** Guardrails to design: (1) auto-clean or overwrite portion outputs when rerunning a stage; (2) pipeline check to fail if any `notes=="mock"` or `type=="page"` spans originate from mock generator; (3) optionally enforce `--force` when rerunning with same run_id; (4) continue tracing other sections for residual non-mock failures.
- 20251128-1535 — Architecture discussion + guardrail plan added to tasks.
  - **Result:** Success (plan updated).
  - **Notes:** Agreed direction: keep DAG but enforce immutability/idempotence; add stage-level contracts and gates. Added tasks for driver run-safety, portionize/consensus guards (mock/page-level/mixed timestamps/missing anchors), enrich/build guards (section_id null-rate, stubs, duplicate text hashes, gameplay misclass). Also aligned on assumption of interrupted/batched runs; guardrails must work with resume logic.
  - **Next:** Draft short RFC on “detect + shape” portionize v2 vs `portionize_sections_v1`, plus resume-safe artifact handling; then implement guardrails.
- 20251128-1535 — Continued Issue 0 tracing beyond pages 14–39.
  - **Result:** Success (additional evidence gathered).
  - **Notes:** For page 25 there are 9 non-mock LLM spans (e.g., `portion_id: 32-39`, `P32-39`, `P025-030`) with confidence ~0.9–1.0, covering sections 32–39, yet consensus picked the 1.0-confidence mock page span P025, showing the mock rows overshadowed valid LLM proposals. `gamebook.json` has 293 empty sections (stubs), indicating widespread fallout from mock dominance. Page 50 example (portion `P144-147`) shows a good non-mock span with `section_id: 144`, so later pages can work when mock rows don’t block them.
  - **Next:** Trace a few more randomly sampled pages to confirm no residual non-mock failures after removing mock rows would remain; then prioritize implementing guardrails to prevent mixed/mock inputs from reaching consensus.
- 20251128-1535 — Random sampling across book to assess mock contamination scope.
  - **Result:** Success (quantified contamination).
  - **Notes:** `portions_resolved.jsonl` has 106 rows; 42 (≈40%) originate from mock hypotheses (portion_ids P###, type=page). Example pages: 45→P045 (mock); 60→S007 (non-mock); 75→S019 (non-mock); 90→S034 (non-mock); 105→S046 (non-mock). Mock influence is concentrated early and mid-book (e.g., P001, P003, P004, P016, P017, P025), while many later pages select non-mock spans. This confirms that removing/preventing mock rows should recover substantial coverage without further LLM changes.
  - **Next:** Proceed to implement guardrails (driver force/clean + stage validators) and re-run to verify mock-free consensus; then re-evaluate portionization quality on pages previously dominated by mock spans.
- 20251128-1546 — Added AI-leverage warning to Issue 0.
  - **Result:** Success.
  - **Notes:** Issue 0 analysis now explicitly asks whether we’re overcoding what AI can do, and whether single high-stakes calls are being trusted instead of using AI ensemble/arbiter patterns. Emphasizes designing stages to lean on AI strengths (contextual boundary detection, classification, validation) with multi-call reconciliation before resorting to heuristics.
  - **Next:** Carry this lens into the guardrail design/RFC and upcoming portionize redesign.
- 20251128-1555 — Mock-free recomposition run (`deathtrap-ff-engine-nomock`) to isolate non-mock issues.
  - **Result:** Success (run produced outputs) / Findings (issues persist).
  - **What we did:** Filtered `window_hypotheses` to drop mock rows; re-ran consensus → dedupe → normalize → resolve → enrich → build into new run dir `output/runs/deathtrap-ff-engine-nomock/` (no LLM calls). Outputs: 100 portions locked; gamebook has 387 sections.
  - **Findings:** 288 sections still empty; sections 37–39 still missing text (no `section_id` for those spans). Portion `32-39` spans pages 25–29 with `section_id=32`, so enrich still only captures first anchor. Early pages 14–15 are covered by portion `S2` with `section_id=None`; portion `S001` spans pages 16–17 with `section_id=1`, indicating continued mis-boundaries. This shows that even without mocks, `portionize_sliding_v1`+`section_enrich_v1` fail to split multi-section spans and assign IDs. Mock removal alone is insufficient; we need a section-aware portionizer/enricher.
  - **Next:** Decide on replacement (e.g., `portionize_sections_v1` or detect+shape v2) and add guardrails; re-run with section-aware portionizer to measure improvement before coding fixes.
- 20251128-1634 — Paused per user direction pending possible architectural overhaul (switch to Unstructured intake).
  - **Result:** Success.
  - **Notes:** Story status set to *Paused*; pending decisions on new architecture that may supersede current plan and guardrails.
  - **Next:** Resume after intake/architecture direction is decided; re-evaluate plan and portionizer choice against new stack.
