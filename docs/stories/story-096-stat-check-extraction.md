# Story: Stat Check Extraction (Skill, Luck, and Dice Rolls)

**Status**: To Do  
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

- [ ] **Dice roll requirements detected**: Extract dice roll instructions (e.g., "Roll two dice", "Roll one die", "Roll 2d6")
- [ ] **Stat type detected**: Extract which stat is being checked (SKILL, LUCK, STAMINA)
- [ ] **Comparison logic detected**: Extract comparison operators (≤, <, ≥, >, =, same as or less than, greater than)
- [ ] **Pass outcomes detected**: Extract target section for pass condition (e.g., "turn to 55")
- [ ] **Fail outcomes detected**: Extract target section for fail condition (e.g., "turn to 202")
- [ ] **Test Your Luck special handling**: Detect "Test your Luck" mechanics (always 2d6, reduces LUCK by 1)
- [ ] **Structured output**: All stat check data extracted into JSON format per section:
  ```json
  {
    "stat_checks": [
      {
        "stat": "SKILL",
        "dice_roll": "2d6",
        "pass_condition": "total <= SKILL",
        "pass_section": "55",
        "fail_condition": "total > SKILL",
        "fail_section": "202"
      }
    ],
    "test_your_luck": [
      {
        "lucky_section": "100",
        "unlucky_section": "200"
      }
    ]
  }
  ```
- [ ] **Generic patterns**: Detection uses semantic patterns (dice roll phrases, stat names, comparison operators), not hard-coded section numbers (works across all FF books)
- [ ] **No false positives**: Legitimate narrative text mentioning dice/stats not incorrectly flagged as stat checks
- [ ] **Validation**: Spot-check 20-30 sections with known stat checks to verify extraction quality

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

**Output Schema:**
```json
{
  "section_id": "18",
  "stat_checks": [
    {
      "stat": "SKILL",
      "dice_roll": "2d6",
      "dice_count": 2,
      "dice_sides": 6,
      "pass_condition": "total <= stat",
      "pass_section": "55",
      "fail_condition": "total > stat",
      "fail_section": "202",
      "confidence": 0.95
    }
  ],
  "test_your_luck": [
    {
      "lucky_section": "100",
      "unlucky_section": "200",
      "confidence": 0.95
    }
  ]
}
```

**Generic Pattern Requirements:**
- Use semantic patterns (dice roll phrases, stat names, comparison operators), not specific section numbers
- Detect dice roll format: "Roll N dice" → N dice, 6-sided (default)
- Handle variations: "Roll two dice" vs "Roll 2 dice" vs "Roll 2d6"
- Support common comparisons: ≤, <, ≥, >, =, "same as or less than", "greater than"

**Pattern Examples:**
- `"Roll two dice. If the total is the same as or less than your SKILL, turn to 55. If the total is greater than your SKILL, turn to 202."`
  → stat: "SKILL", dice: "2d6", pass: "55" (≤), fail: "202" (>)
- `"Test your Luck. If you are lucky, turn to 100. If you are unlucky, turn to 200."`
  → test_your_luck: lucky="100", unlucky="200"
- `"Roll one die. If you roll 1-3, turn to 50. If you roll 4-6, turn to 75."`
  → stat: null (custom dice check), dice: "1d6", pass: "50" (1-3), fail: "75" (4-6)

**Edge Cases to Handle:**
- Multiple stat checks in one section
- Implicit dice counts ("Roll dice" → assume 2d6)
- Custom dice ranges ("Roll 1-3", "Roll 4-6")
- Complex conditions ("Roll two dice and add your SKILL")
- Test Your Luck variations ("Test your Luck", "you must test your luck", "Test Your Luck")
- Narrative mentions of dice/stats that aren't checks

---

## Tasks

- [ ] Analyze stat check patterns in sample sections (20-30 sections with known stat checks)
- [ ] Design generic pattern detection (semantic patterns for dice rolls, stats, comparisons)
- [ ] Implement pattern-based detection (regex/keyword matching)
- [ ] Implement dice roll parsing (extract dice count and sides)
- [ ] Implement comparison logic extraction (pass/fail conditions)
- [ ] Implement outcome detection (target sections for pass/fail)
- [ ] Implement Test Your Luck special handling (always 2d6, reduces LUCK)
- [ ] Implement LLM-based extraction for complex cases (optional, for validation)
- [ ] Create `extract_stat_checks_v1` module in `modules/enrich/`
- [ ] Define output schema and add to `schemas.py`
- [ ] Test on sample sections (verify all stat types and outcomes detected)
- [ ] **Validate generality**: Test on multiple FF books to ensure no overfitting
- [ ] Verify no false positives (narrative text preserved, no false stat check detection)
- [ ] Integrate into enrichment stage in canonical recipe
- [ ] Run full pipeline and validate extraction quality
- [ ] Document results and impact in work log

---

## Work Log

### 20251223-XXXX — Story created
- **Result:** Story defined.
- **Notes:** Stat check extraction needed to parse dice roll mechanics, stat comparisons (SKILL/LUCK/STAMINA), and conditional outcomes from sections. Must use generic semantic patterns, not hard-coded section numbers, to work across all Fighting Fantasy books.
- **Next:** Analyze stat check patterns in sample sections and design generic detection approach.

