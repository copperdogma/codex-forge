# Story 119: Robot Commando Missing Choices Investigation

**Status**: Done  
**Priority**: High  
**Story Type**: Bug Investigation

## Problem

Robot Commando has a large number of sections marked as having no choices, but manual spot checks suggest many of these sections actually do have choices in the text. This indicates a potential bug in choice extraction, validation, or the final gamebook assembly.

## User Report

- **Observation**: Many sections in Robot Commando are marked as having no choices
- **Suspicion**: Manual spot checks show these sections actually contain choices (e.g., "turn to X" references)
- **Question**: Did the no-choice validation step run? Did it confirm they legitimately have no choices?

## Investigation Goals

1. **Verify validation ran**: Check if `validate_choice_completeness_v1` and related validation modules executed
2. **Count missing choices**: Quantify how many sections are marked as having no choices
3. **Sample verification**: Manually check a sample of "no choice" sections to verify if they actually have choices
4. **Trace extraction pipeline**: Review choice extraction artifacts to see where choices might be getting lost
5. **Identify root cause**: Determine if the issue is in:
   - Choice extraction (`extract_choices_relaxed_v1`)
   - Choice repair (`choices_repair_relaxed_v1`)
   - Choice validation (`validate_choice_links_v1`)
   - Final gamebook assembly (`build_ff_engine_with_issues_v1`)
   - Sequence ordering (`order_sequence_v1`)

## Acceptance Criteria

- [x] Validation reports reviewed to confirm validation steps ran
- [x] Count of sections with no choices documented
- [x] Sample of "no choice" sections manually verified (at least 10 sections)
- [x] Root cause identified (extraction, repair, validation, or assembly)
- [x] Fix implemented and verified
- [x] Robot Commando re-run with correct choice extraction

## Tasks

- [x] Review validation reports (`validation_report.json`, `choice_completeness_report.json`)
- [x] Count sections with no choices in final gamebook
- [x] Sample check: Manually verify 10+ sections marked as "no choices" actually have choices
- [x] Trace choice extraction pipeline: Check artifacts from:
  - `extract_choices_relaxed_v1` → `portions_with_choices.jsonl`
  - `choices_repair_relaxed_v1` → `portions_with_choices_repaired.jsonl`
  - `validate_choice_links_v1` → `portions_with_choices_validated.jsonl`
  - `order_sequence_v1` → check if choices are preserved in sequence
- [x] Compare choice extraction between Robot Commando and working books (e.g., Deathtrap Dungeon)
- [x] Identify root cause and fix
- [x] Re-run Robot Commando pipeline and verify choices are correctly extracted

## Work Log

### 2026-01-11 — Root cause identified and fixed
- **Validation confirmed**: `validate_ff_engine_v2` ran and flagged 57 sections (14.2%) as having no choices
- **Critical discovery**: ALL flagged sections have "turn to" references in their text, but validation marks them as having no choices
- **Root cause**: Validation logic bug in `validate_ff_engine_v2` and `validate_ff_engine_node_v1`
  - Validation only checks for `kind == 'choice'` events in sequence
  - But many sections have conditional navigation via `stat_check` events (e.g., "Roll dice, if <= SKILL turn to 316, else turn to 379")
  - These `stat_check` events have `pass`/`fail` outcomes with `targetSection` - they ARE choices, just conditional ones
  - Example: Section 12 has a `stat_check` event with `pass.targetSection=316` and `fail.targetSection=379`, but validation doesn't recognize this as a choice
- **Impact**: 57 sections incorrectly flagged as "dead ends" when they actually have conditional navigation
- **Fix implemented**: 
  - Updated `validate_ff_engine_v2/main.py` to recognize conditional events (`stat_check`, `test_luck`, `item_check`, `state_check`, `combat`, `stat_change`, `death`) with `targetSection` outcomes as navigation
  - Updated `validate_ff_engine_node_v1/validator/validation.js` with same logic
  - Rebuilt Node validator bundle
  - Added comprehensive tests in `tests/test_validate_ff_engine_v2_navigation.py`
- **Results**: 
  - Before fix: 57 sections flagged
  - After fix: 1 section flagged (section 167 - likely legitimate dead end)
  - Reduction: 56 sections (98.2% reduction)
  - Section 12 and all other conditional navigation sections now correctly recognized
  - Both Python and Node validators updated and tested
- **Tests added**: `tests/test_validate_ff_engine_v2_navigation.py` with comprehensive test coverage
- **Manual validation**: Verified on Robot Commando - all previously flagged sections with conditional navigation now correctly recognized

### 2026-01-11 — Section 167 bug identified
- **Finding**: Section 167 has choices in portion data but they're missing in final gamebook
- **Root cause**: Section 167's portion HTML spans pages 111-112 and includes a page break marker `<p class="page-number">168</p>` followed by continuation text with choices ("You may take one... turn to 247/376")
- **Issue**: The final gamebook's `presentation_html` for section 167 is truncated - it stops BEFORE the page break marker, losing the continuation text and choices
- **Impact**: Section 167 has empty sequence `[]` instead of 2 choices, causing it to be flagged as having no navigation
- **Fix required**: Investigate where HTML is being split. Likely cause is in boundary detection or HTML extraction/splitting logic that incorrectly truncates content at page-number markers. The portion's `raw_html` includes the full content, but it's being lost during gamebook assembly.
- **Requirements**: 
  - Fix boundary detection or HTML extraction to preserve full content through page breaks
  - Ensure choices in continuation text are included in section 167's sequence
  - Add tests to verify content spanning page breaks is preserved
  - Verify fix on Robot Commando section 167
- **Root cause identified**: 
  - `_code_repair_html()` in `detect_boundaries_html_loop_v1` incorrectly converts page-number markers to h2 headers
  - Page 112 has a page-number marker `<p class="page-number">168</p>` at p112-b1 and an actual h2 header `<h2>168</h2>` at p112-b7
  - The repair logic converts the page-number marker to h2, creating a duplicate h2 header
  - `detect_boundaries_html_v1` then detects both h2 headers and picks the wrong one (the converted page-number marker)
  - This causes section 167's boundary to end at p112-b1 instead of p112-b7, truncating the HTML
- **Fix implemented**: 
  - Updated `_code_repair_html()` in `modules/portionize/detect_boundaries_html_loop_v1/main.py` to never convert page-number markers to h2 headers
  - Page-number markers are page numbers, not section headers, so they should never be converted to h2
  - The fix prevents the creation of duplicate h2 headers that cause boundary detection to pick the wrong one
  - **Code change**: Line 147 now always skips conversion of page-number markers (`if "page-number" in pattern: continue`)
- **Tests added**: 
  - Created `tests/test_detect_boundaries_html_loop_v1_page_number.py` with 3 test cases:
    1. Page-number marker with existing h2 should NOT be converted
    2. Page-number marker without h2 should NOT be converted (they're page numbers, not headers)
    3. Plain `<p>` tags (not page-number markers) should still be converted when appropriate
  - All tests pass, confirming the fix works correctly
- **Verification**: 
  - Unit test confirms fix prevents page-number marker conversion
  - Pipeline test completed: Re-ran `html_repair_loop` → `html_to_blocks` → `detect_boundaries_html` → `portionize_html_extract`
  - **Results**:
    - ✅ Page-number marker preserved: Page 112's repaired HTML keeps `<p class="page-number">168</p>` (not converted to h2)
    - ✅ Boundary correct: Section 167's boundary ends at `p112-b7` (where section 168 actually starts) instead of `p112-b1` (page-number marker)
    - ✅ HTML no longer truncated: Section 167's HTML is 1132 chars (full length) instead of 654 chars (truncated)
  - **Fix verified**: The code change successfully prevents page-number markers from being converted to h2 headers, fixing the boundary detection issue
  - **Full pipeline re-run completed**: 
    - Rebuilt gamebook from `html_repair_loop` onwards with fixed boundaries
    - Fixed `driver.py` bug where `--output-dir` wasn't appending `run_id` correctly
    - Final validation report shows 0 sections with no choices (down from 57)
    - Section 167 verified to have choices in final gamebook
    - All fixes verified and working correctly
  - **Testing infrastructure**: Added `pytest>=7.0.0` to `requirements.txt` and verified all 14 test cases pass
  - **Documentation**: Added module-level docstring to `_code_repair_html()` explaining the Story 119 fix

### 2026-01-11 — Story created
- **Issue reported**: User noticed many sections in Robot Commando marked as having no choices
- **Initial investigation**: Need to verify validation ran and check sample sections
