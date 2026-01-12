# Story 121: Robot Commando Unreachable Sections Investigation

**Status**: To Do  
**Priority**: High  
**Story Type**: Bug Investigation / Quality Fix

## Problem

Robot Commando has 21 gameplay sections that are unreachable from the start section "background". This represents 5.2% of all gameplay sections (21 out of 401), which is a significant quality issue that needs investigation.

## User Report

- **Observation**: Validation report shows 21 unreachable sections
- **Quality Score**: 78/100 (warning level) due to unreachable sections
- **Question**: Are these legitimate unreachable sections (dead ends, alternative paths) or code errors (missing choice links)?

## Investigation Goals

1. **Identify unreachable sections**: List all 21 unreachable section IDs
2. **Categorize sections**: Determine if each is:
   - Legitimate dead end (intentional game design)
   - Missing choice link (code error - section should be reachable)
   - Alternative path (should be reachable via conditional navigation)
   - Orphaned section (never referenced, extraction error)
3. **Trace source**: For each unreachable section, trace back to:
   - Where it should be referenced (upstream sections)
   - Why it's not being reached (missing choice, broken link, etc.)
   - Original text/HTML to verify if choice exists in source
4. **Root cause analysis**: Determine if issue is:
   - Choice extraction bug (choices not extracted from text)
   - Choice linking bug (choices extracted but not linked correctly)
   - Boundary detection bug (section boundaries incorrect, content split)
   - Sequence ordering bug (choices exist but in wrong order/position)
   - Legitimate game design (sections intentionally unreachable)

## Acceptance Criteria

- [ ] All 21 unreachable sections identified and documented
- [ ] Each section categorized (legitimate vs. code error)
- [ ] Root cause identified for code error sections
- [ ] Fix implemented for code error sections
- [ ] Verification: Re-run validation, confirm unreachable count reduced
- [ ] Quality score improved (target: 90+ for "good" status)

## Tasks

- [ ] Extract list of 21 unreachable section IDs from validation report
- [ ] For each unreachable section:
  - [ ] Check if it's referenced in any upstream section's choices/conditional events
  - [ ] Check original portion HTML/text for "turn to X" references
  - [ ] Check if section has incoming references that should make it reachable
  - [ ] Categorize as legitimate or code error
- [ ] Identify patterns:
  - [ ] Are unreachable sections clustered (e.g., all in a certain range)?
  - [ ] Do they share common characteristics (e.g., all have specific content type)?
  - [ ] Are they all missing the same type of choice link?
- [ ] For code error sections:
  - [ ] Trace through choice extraction pipeline artifacts
  - [ ] Identify where choice link was lost (extraction, repair, validation, assembly)
  - [ ] Implement fix
- [ ] Test fix:
  - [ ] Re-run validation
  - [ ] Verify unreachable count reduced
  - [ ] Verify quality score improved
  - [ ] Manual spot-check of fixed sections

## Technical Details

### Current State

**Unreachable Sections (from validation report)**:
- Section IDs: 7, 22, 53, 76, 100, 111, 140, 158, 173, 200, 214, 222, 242, 253, 297, 314, 330, 338, 355, 377, 388
- Total: 21 sections
- Start section: "background" → points to section 1

**Validation Context**:
- Total sections: 401
- Reachable sections: 380
- Unreachable sections: 21 (5.2%)
- Quality score: 78/100 (warning level)

### Investigation Approach

1. **Graph Analysis**: Build reachability graph from "background" and identify which sections have zero incoming edges
2. **Text Analysis**: For each unreachable section, search upstream sections' text/HTML for references
3. **Artifact Tracing**: Check intermediate artifacts (portions, choices, sequences) to see where links are lost
4. **Pattern Detection**: Look for common patterns in unreachable sections (page ranges, content types, etc.)

### Expected Outcomes

**If code errors**:
- Fix choice extraction/linking bugs
- Re-run pipeline
- Unreachable count should drop significantly (ideally to 0, or only legitimate dead ends)

**If legitimate**:
- Document which sections are intentionally unreachable
- Consider if they should be marked differently (e.g., `end_game: true` or special flag)
- Update validation to distinguish between legitimate and problematic unreachable sections

## Work Log

### 2026-01-11 — Story Created
- **Result**: Story defined to investigate 21 unreachable sections in Robot Commando
- **Notes**: This is a follow-up to Story 120 (validation inconsistency fix). Now that we can see unreachable sections, we need to investigate if they're legitimate or code errors.
