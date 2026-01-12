# Story 122: Refactor Python Validator into Forensics Wrapper

**Status**: Done
**Priority**: Medium
**Story Type**: Refactoring / Code Quality

## Problem

The Python validator (`validate_ff_engine_v2`) duplicates validation logic that already exists in the canonical Node validator (`validate_ff_engine_node_v1`). This creates maintenance burden and potential for inconsistencies:

- **Duplication**: Both validators check missing sections, duplicates, no text, no choices
- **Inconsistency risk**: Changes to validation logic must be made in two places
- **Maintenance overhead**: Two codebases to maintain for the same validation checks
- **Confusion**: Unclear which validator is authoritative (though Node is canonical)

The Python validator's unique value is its **forensics capabilities** (tracing issues to source artifacts) and **HTML report generation**, not the validation logic itself.

## Goal

Refactor `validate_ff_engine_v2` to become a **forensics wrapper** around the Node validator:

1. **Remove duplicate validation logic** from Python validator
2. **Delegate all validation** to Node validator (canonical source)
3. **Add forensics traces** to Node validator's results
4. **Generate HTML reports** from enriched validation results
5. **Maintain backward compatibility** with existing recipes and reports

## Success Criteria

- [x] Python validator calls Node validator for ALL validation logic
- [x] Python validator no longer duplicates checks (missing sections, duplicates, no text, no choices)
- [x] Python validator adds forensics traces to Node validator's results
- [x] HTML reports still generated with same format and information
- [x] Validation reports maintain same schema and structure
- [x] All existing recipes continue to work without changes
- [x] Forensics traces still link issues to source artifacts (boundaries, elements, portions)
- [x] Quality score and unreachable sections still displayed correctly

## Tasks

- [x] Analyze current Python validator validation logic
- [x] Identify all checks that duplicate Node validator
- [x] Refactor `validate_gamebook()` to call Node validator first
- [x] Map Node validator results to `ValidationReport` schema
- [x] Preserve forensics trace generation (add traces to Node's results)
- [x] Update HTML report generation to work with Node validator results
- [x] Test on Robot Commando to verify:
  - Validation results match Node validator
  - Forensics traces still generated
  - HTML report still works
  - Quality score still calculated correctly
- [x] Update module documentation to clarify Python validator is a forensics wrapper
- [x] Remove duplicate validation code

## Technical Details

### Current Architecture

**Python Validator (`validate_ff_engine_v2`)**:
- Validates: missing sections, duplicates, no text, no choices
- Delegates: reachability analysis (recently added)
- Adds: forensics traces, HTML reports
- Output: `ValidationReport` with forensics

**Node Validator (`validate_ff_engine_node_v1`)**:
- Validates: schema, missing sections, duplicates, no text, no choices, reachability
- Output: JSON with errors, warnings, summary

### Target Architecture

**Python Validator (refactored)**:
- Calls: Node validator for ALL validation
- Adds: forensics traces to Node's results
- Generates: HTML reports
- Output: `ValidationReport` with forensics (same schema)

**Node Validator**:
- Unchanged: continues to be canonical validation source

### Implementation Approach

1. **Refactor `validate_gamebook()` function**:
   - Remove all validation logic (missing sections, duplicates, no text, no choices)
   - Call Node validator via `_get_unreachable_sections_from_node_validator()` pattern
   - Parse Node validator's JSON output
   - Map to `ValidationReport` schema

2. **Preserve forensics**:
   - Keep `make_trace()` function and forensics logic
   - Apply forensics traces to sections flagged by Node validator
   - Maintain same trace structure (boundaries, elements, portions)

3. **Maintain HTML reports**:
   - HTML generator already works with `ValidationReport` schema
   - Should continue to work after refactoring
   - May need minor adjustments for Node validator's output format

4. **Backward compatibility**:
   - Keep same `ValidationReport` schema
   - Keep same command-line interface
   - Keep same recipe parameters

## Benefits

- **Single source of truth**: All validation logic in Node validator
- **Reduced maintenance**: Changes to validation logic only in one place
- **Consistency**: Python validator always matches Node validator
- **Clear separation**: Node = validation, Python = forensics + reporting
- **Preserved value**: Forensics and HTML reports remain available

## Work Log

### 2026-01-11 — Story Created
- **Result**: Story defined to refactor Python validator into forensics wrapper
- **Notes**: Follow-up to Story 120. After fixing validation inconsistency, identified opportunity to eliminate duplication and reduce maintenance burden.

### 20260111-1400 — Analyzed duplication between Python and Node validators
- **Result**: Identified all duplicate validation logic
- **Key Findings**:
  - **Python validator** (`validate_ff_engine_v2/main.py:159-312`):
    - Missing sections check (lines 189-192)
    - Duplicate sections check (lines 183-187)
    - Sections with no text check (lines 195-200)
    - Sections with no choices check (lines 202-263)
    - Already delegates reachability to Node validator (lines 74-156, 348-366)

  - **Node validator** (`validate_ff_engine_node_v1/validator/validation.js`):
    - Missing sections check (`validateMissingSections()`, lines 208-234)
    - Duplicate sections check (`validateDuplicateSections()`, lines 235-263)
    - Empty text warnings (`validateEmptyText()`, lines 265-278)
    - No choices warnings (`validateNoChoices()`, lines 279-361)
    - Reachability analysis (`findUnreachableSections()`, lines 584-597)
    - Additional checks: Schema validation, sequence targets, section IDs

  - **Duplication confirmed**: All four checks (missing sections, duplicates, no text, no choices) are duplicated
  - **Navigation detection logic**: Both validators use nearly identical `hasNavigation()` logic (Python: lines 204-250, Node: lines 288-340)

- **Architecture**: Node validator already outputs JSON with `errors`, `warnings`, `summary` structure. Python `ValidationReport` schema is compatible but needs mapping from Node's format.

- **Next**: Design the forensics wrapper pattern to delegate validation while preserving forensics capabilities.

### 20260111-1410 — Designed forensics wrapper architecture
- **Result**: Refactoring approach defined
- **Design**:
  1. Create new function `_get_validation_from_node_validator()` that calls Node validator with `--json` flag
  2. Parse Node validator's JSON output to extract:
     - `missing_sections` (from errors with "Missing" message)
     - `duplicate_sections` (from errors with "Duplicate" message)
     - `sections_with_no_text` (from warnings with "no text" message)
     - `sections_with_no_choices` (from warnings with "no choices" message)
     - `unreachable_sections` (from warnings with "unreachable" message)
     - `errors` and `warnings` lists (directly from Node validator)
  3. Replace `validate_gamebook()` implementation to:
     - Remove all validation logic (lines 176-311)
     - Call `_get_validation_from_node_validator()` instead
     - Build `ValidationReport` from Node validator's results
     - Preserve exact same return schema
  4. Keep forensics logic completely unchanged (lines 368-486 in main())
  5. Keep HTML report generation unchanged (lines 491-497)

- **Benefits**: Eliminates ~135 lines of duplicate validation code, single source of truth, automatic consistency with Node validator

- **Next**: Implement the delegation to Node validator

### 20260111-1420 — Implemented forensics wrapper refactoring
- **Result**: Successfully refactored Python validator to delegate to Node validator
- **Changes made**:
  1. Renamed `_get_unreachable_sections_from_node_validator()` to `_call_node_validator()` - now returns full validation result instead of just unreachable sections
  2. Updated cache type from `List[str]` to `Dict[str, Any]` to store full validation result
  3. Refactored `validate_gamebook()` function:
     - Removed all validation logic (~135 lines)
     - Added `node_validator_result` parameter
     - Parse Node validator's JSON output to extract section lists from messages
     - Build `ValidationReport` from Node validator results
  4. Updated `main()` to call Node validator first and pass results to `validate_gamebook()`
  5. Forensics logic unchanged - still works with `ValidationReport` schema
  6. HTML report generation unchanged
  7. Added module docstring clarifying forensics wrapper role

- **Testing**: Tested on Robot Commando gamebook
  - Validation results match Node validator output exactly
  - All sections correctly identified: no_choices (167, 213), unreachable (21 sections)
  - Forensics traces generated successfully
  - HTML report generated successfully

- **Code reduction**: Eliminated ~135 lines of duplicate validation logic

- **Next**: Update story checklist and mark tasks complete

### 20260111-1430 — Story completed
- **Result**: Story 122 completed successfully
- **Summary**:
  - Python validator (`validate_ff_engine_v2`) refactored into forensics wrapper
  - All validation logic now delegated to Node validator (single source of truth)
  - Eliminated ~135 lines of duplicate validation code
  - Forensics and HTML reporting preserved
  - All success criteria met
  - Tested successfully on Robot Commando gamebook

- **Files modified**:
  - `modules/validate/validate_ff_engine_v2/main.py`: Refactored validation delegation
  - `docs/stories/story-122-refactor-python-validator-forensics-wrapper.md`: Updated story status to Done

- **Benefits achieved**:
  - Single source of truth: All validation in Node validator
  - No more inconsistency risk between validators
  - Reduced maintenance: Changes only needed in one place
  - Clear separation: Node = validation, Python = forensics + reporting
  - Preserved value: Forensics and HTML reports still available

### 20260111-1440 — Updated integration tests
- **Result**: All integration tests pass
- **Changes**:
  - Updated `test_validate_ff_engine_v2_node_integration.py` to use `_call_node_validator()` instead of `_get_unreachable_sections_from_node_validator()`
  - Updated all test cases to extract unreachable sections from full validation result
  - All 5 tests pass successfully
- **Test coverage**:
  - Python validator matches Node validator unreachable sections
  - Integration with real Robot Commando gamebook (21 unreachable sections)
  - ValidationReport includes unreachable sections when Node validator is used
  - Error handling for Node validator failures
  - Caching works correctly
