# Story 122: Refactor Python Validator into Forensics Wrapper

**Status**: To Do  
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

- [ ] Python validator calls Node validator for ALL validation logic
- [ ] Python validator no longer duplicates checks (missing sections, duplicates, no text, no choices)
- [ ] Python validator adds forensics traces to Node validator's results
- [ ] HTML reports still generated with same format and information
- [ ] Validation reports maintain same schema and structure
- [ ] All existing recipes continue to work without changes
- [ ] Forensics traces still link issues to source artifacts (boundaries, elements, portions)
- [ ] Quality score and unreachable sections still displayed correctly

## Tasks

- [ ] Analyze current Python validator validation logic
- [ ] Identify all checks that duplicate Node validator
- [ ] Refactor `validate_gamebook()` to call Node validator first
- [ ] Map Node validator results to `ValidationReport` schema
- [ ] Preserve forensics trace generation (add traces to Node's results)
- [ ] Update HTML report generation to work with Node validator results
- [ ] Test on Robot Commando to verify:
  - Validation results match Node validator
  - Forensics traces still generated
  - HTML report still works
  - Quality score still calculated correctly
- [ ] Update module documentation to clarify Python validator is a forensics wrapper
- [ ] Remove duplicate validation code

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
