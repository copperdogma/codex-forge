# Story: Stat Check Extraction (Skill, Luck, and Dice Rolls)

**Status**: Done
**Created**: 2025-12-23  
**Priority**: High  
**Parent Story**: story-006 (Enrichment pass)

---

## Goal

Extract stat check mechanics from gamebook sections into structured JSON data. Detect dice roll requirements, stat comparisons (SKILL, LUCK, STAMINA), and conditional outcomes based on pass/fail results.

---

## Motivation

Fighting Fantasy gamebooks frequently feature stat checks that require dice rolls:
- **SKILL checks**: "Roll two dice. If the total is the same as or less than your SKILL, turn to 55. If the total is greater than your SKILL, turn to 202."
- **LUCK tests**: "Test your Luck. If you are lucky, turn to 100. If you are unlucky, turn to 200."
- **STAMINA checks**: Less common, but may appear in some books
- **Custom dice rolls**: Various dice combinations with stat comparisons

Currently, this information is only present in plain text. Extracting it into structured data enables:
- Game engine stat check system integration
- Automatic dice roll resolution and stat comparison
- Conditional navigation based on pass/fail outcomes
- Proper handling of "Test Your Luck" mechanics (which reduce LUCK by 1)

**Example from section 18:**
- Dice roll: "Roll two dice"
- Stat: SKILL
- Pass condition: "total is the same as or less than your SKILL" → turn to 55
- Fail condition: "total is greater than your SKILL" → turn to 202

---

## Success Criteria

- [x] **Dice roll requirements detected**: Extract dice roll instructions (e.g., "Roll two dice", "Roll one die", "Roll 2d6")
- [x] **Stat type detected**: Extract which stat is being checked (SKILL, LUCK, STAMINA)
- [x] **Comparison logic detected**: Extract comparison operators (≤, <, ≥, >, =, same as or less than, greater than)
- [x] **Pass outcomes detected**: Extract target section for pass condition (e.g., "turn to 55")
- [x] **Fail outcomes detected**: Extract target section for fail condition (e.g., "turn to 202")
- [x] **Test Your Luck special handling**: Detect "Test your Luck" mechanics (always 2d6, reduces LUCK by 1)
- [x] **Structured output**: All stat check data extracted into JSON format per section
- [x] **Generic patterns**: Detection uses semantic patterns (dice roll phrases, stat names, comparison operators), not hard-coded section numbers (works across all FF books)
- [x] **No false positives**: Legitimate narrative text mentioning dice/stats not incorrectly flagged as stat checks
- [x] **Validation**: Spot-check 20-30 sections with known stat checks to verify extraction quality

---

## Solution Approach

**New Module**: `modules/enrich/extract_stat_checks_v1/`

**Detection Strategy:**
1. **Pattern-based detection** (regex/keyword matching):
   - Dice roll patterns: "Roll two dice", "Roll one die", "Roll 2 dice", "Roll 1 die", "Roll 2d6"
   - Stat patterns: "your SKILL", "your LUCK", "your STAMINA"
   - Comparison patterns: "same as or less than", "less than or equal to", "greater than", "more than", "equal to"
   - Outcome patterns: "turn to X", "go to X", "refer to X"

2. **LLM-based extraction** (for complex/ambiguous cases):
   - Use LLM to parse stat check mechanics from section text
   - Extract structured JSON with dice rolls, stats, comparisons, outcomes
   - Handle edge cases (implicit dice counts, complex conditions)

3. **Hybrid approach** (recommended):
   - Use pattern matching for fast, deterministic detection
   - Use LLM for validation and complex cases (multiple checks, special rules)
   - Combine results with confidence scoring
4. **Global AI Audit** (post-process):
   - Perform a final batch audit over all extracted stat checks to prune false positives and ensure logical consistency, referencing the pattern established in Story 094 (Inventory Parsing).

---

## Tasks

- [x] Analyze stat check patterns in sample sections (20-30 sections with known stat checks)
- [x] Design generic pattern detection (semantic patterns for dice rolls, stats, comparisons)
- [x] Implement pattern-based detection (regex/keyword matching)
- [x] Implement dice roll parsing (extract dice count and sides)
- [x] Implement comparison logic extraction (pass/fail conditions)
- [x] Implement outcome detection (target sections for pass/fail)
- [x] Implement Test Your Luck special handling (always 2d6, reduces LUCK)
- [x] Implement LLM-based extraction for complex cases (optional, for validation)
- [x] Create `extract_stat_checks_v1` module in `modules/enrich/`
- [x] Define output schema and add to `schemas.py`
- [x] Test on sample sections (verify all stat types and outcomes detected)
- [x] **Validate generality**: Test on multiple FF books to ensure no overfitting
- [x] Verify no false positives (narrative text preserved, no false stat check detection)
- [x] Integrate into enrichment stage in canonical recipe
- [x] Run full pipeline and validate extraction quality
- [x] Document results and impact in work log

---

## Work Log

### 20251223-XXXX — Story created
- **Result:** Story defined.
- **Notes:** Stat check extraction needed to parse dice roll mechanics, stat comparisons (SKILL/LUCK/STAMINA), and conditional outcomes from sections. Must use generic semantic patterns, not hard-coded section numbers, to work across all Fighting Fantasy books.
- **Next:** Analyze stat check patterns in sample sections and design generic detection approach.

### 20251223-XXXX — Implementation and Verification
- **Result:** Success. Implemented `extract_stat_checks_v1` module and updated core schemas.
- **Notes:** Created hybrid regex+LLM extractor following try-validate-escalate pattern with Global AI Audit pass. Updated gamebook builder to map stats to engine `diceChecks` and `testYourLuck` arrays. Verified on full book run with 27 Luck tests and 8 complex Stat Checks extracted.
- **Outcome:** Stat checks and "Test Your Luck" mechanics are now extracted into structured data.

