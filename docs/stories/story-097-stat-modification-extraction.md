# Story: Stat Modification Extraction (Skill, Stamina, Luck Changes)

**Status**: Done
**Created**: 2025-12-23  
**Priority**: High  
**Parent Story**: story-006 (Enrichment pass)

---

## Goal

Extract stat modification mechanics from gamebook sections into structured JSON data. Detect when the player gains or loses SKILL, STAMINA, or LUCK points, including the amount and direction of change.

---

## Motivation

Fighting Fantasy gamebooks frequently feature stat modifications:
- **SKILL changes**: "Reduce your SKILL by 1 point", "Increase your SKILL by 2"
- **STAMINA changes**: "Lose 2 STAMINA points", "Restore 5 STAMINA points", "You lose 3 STAMINA"
- **LUCK changes**: "Lose 1 LUCK point", "Gain 2 LUCK points"
- **Permanent modifications**: Some changes affect initial values (less common)

Currently, this information is only present in plain text. Extracting it into structured data enables:
- Game engine stat tracking and automatic updates
- Proper handling of stat changes during gameplay
- Validation of stat modifications (prevent negative stats, enforce limits)
- Game state management across sections

---

## Success Criteria

- [x] **SKILL modifications detected**: Extract SKILL changes (e.g., "Reduce your SKILL by 1", "Increase SKILL by 2")
- [x] **STAMINA modifications detected**: Extract STAMINA changes (e.g., "Lose 2 STAMINA", "Restore 5 STAMINA points")
- [x] **LUCK modifications detected**: Extract LUCK changes (e.g., "Lose 1 LUCK", "Gain 2 LUCK points")
- [x] **Amount extraction**: Extract the numeric amount of change (positive for gains, negative for losses)
- [x] **Direction detection**: Detect whether modification is increase/gain or decrease/loss
- [x] **Permanent flag detection**: Identify permanent modifications (affect initial values, not just current)
- [x] **Multiple modifications supported**: Handle sections with multiple stat changes
- [x] **Structured output**: All stat modification data extracted into JSON format per section
- [x] **Generic patterns**: Detection uses semantic patterns (action verbs, stat names, numeric values), not hard-coded phrases (works across all FF books)
- [x] **No false positives**: Legitimate narrative text mentioning stats not incorrectly flagged as modifications
- [x] **Validation**: Spot-check 20-30 sections with known stat modifications to verify extraction quality

---

## Solution Approach

**New Module**: `modules/enrich/extract_stat_modifications_v1/`

**Detection Strategy:**
1. **Pattern-based detection** (regex/keyword matching):
   - Reduce/decrease patterns: "Reduce your SKILL by X", "Decrease SKILL by X", "Lose X STAMINA", "You lose X points"
   - Increase/gain patterns: "Increase your SKILL by X", "Gain X STAMINA", "Restore X STAMINA points", "Add X to your SKILL"
   - Stat patterns: "your SKILL", "your STAMINA", "your LUCK", "SKILL", "STAMINA", "LUCK"
   - Amount extraction: Numeric values after action verbs (e.g., "by 1", "by 2 points", "3 points")

2. **LLM-based extraction** (for complex/ambiguous cases):
   - Use LLM to parse stat modifications from section text
   - Extract structured JSON with stat name, amount, direction, permanent flag
   - Handle edge cases (implicit amounts, complex phrasing)

3. **Hybrid approach** (recommended):
   - Use pattern matching for fast, deterministic detection
   - Use LLM for validation and complex cases (multiple modifications, special rules)
   - Combine results with confidence scoring
4. **Global AI Audit** (post-process):
   - Perform a final batch audit over all extracted stat modifications to prune false positives and normalize phrasing, referencing the pattern established in Story 094 (Inventory Parsing).

---

## Tasks

- [x] Analyze stat modification patterns in sample sections (20-30 sections with known stat changes)
- [x] Design generic pattern detection (semantic patterns for action verbs, stats, amounts)
- [x] Implement pattern-based detection (regex/keyword matching)
- [x] Implement stat name extraction (SKILL, STAMINA, LUCK)
- [x] Implement amount extraction (numeric values, positive/negative)
- [x] Implement direction detection (increase vs decrease)
- [x] Implement permanent flag detection (affects initial values)
- [x] Implement LLM-based extraction for complex cases (optional, for validation)
- [x] Create `extract_stat_modifications_v1` module in `modules/enrich/`
- [x] Define output schema and add to `schemas.py` (may already exist in gamebook schema)
- [x] Test on sample sections (verify all stat types and amounts detected)
- [x] **Validate generality**: Test on multiple FF books to ensure no overfitting
- [x] Verify no false positives (narrative text preserved, no false modification detection)
- [x] Integrate into enrichment stage in canonical recipe
- [x] Run full pipeline and validate extraction quality
- [x] Document results and impact in work log

---

## Work Log

### 20251223-XXXX — Story created
- **Result:** Story defined.
- **Notes:** Stat modification extraction needed to parse SKILL/STAMINA/LUCK changes from sections. Must use generic semantic patterns, not hard-coded phrases, to work across all Fighting Fantasy books.
- **Next:** Analyze stat modification patterns in sample sections and design generic detection approach.

### 20251223-XXXX — Implementation and Verification
- **Result:** Success. Implemented `extract_stat_modifications_v1` module and updated core schemas.
- **Notes:** Created hybrid regex+LLM extractor following try-validate-escalate pattern with Global AI Audit pass. Updated gamebook builder to map stats to engine `statChanges` array. Verified on full book run with high precision for SKILL and STAMINA losses.
- **Outcome:** Stat modifications are now extracted into structured data.


### 20251225-1303 — Story audit for checklist and log
- **Result:** Success.
- **Notes:** Verified `## Tasks` checklist exists with actionable items; story already marked Done, no task edits required.
- **Next:** Await further instructions or new story scope.
