# Story: Stat Modification Extraction (Skill, Stamina, Luck Changes)

**Status**: To Do  
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

**Example from section 20:**
- Modification: "Reduce your SKILL by 1 point"
- Stat: SKILL
- Amount: -1
- Direction: reduce (negative)

---

## Success Criteria

- [ ] **SKILL modifications detected**: Extract SKILL changes (e.g., "Reduce your SKILL by 1", "Increase SKILL by 2")
- [ ] **STAMINA modifications detected**: Extract STAMINA changes (e.g., "Lose 2 STAMINA", "Restore 5 STAMINA points")
- [ ] **LUCK modifications detected**: Extract LUCK changes (e.g., "Lose 1 LUCK", "Gain 2 LUCK points")
- [ ] **Amount extraction**: Extract the numeric amount of change (positive for gains, negative for losses)
- [ ] **Direction detection**: Detect whether modification is increase/gain or decrease/loss
- [ ] **Permanent flag detection**: Identify permanent modifications (affect initial values, not just current)
- [ ] **Multiple modifications supported**: Handle sections with multiple stat changes
- [ ] **Structured output**: All stat modification data extracted into JSON format per section:
  ```json
  {
    "stat_modifications": [
      {
        "stat": "skill",
        "amount": -1,
        "permanent": false
      }
    ]
  }
  ```
- [ ] **Generic patterns**: Detection uses semantic patterns (action verbs, stat names, numeric values), not hard-coded phrases (works across all FF books)
- [ ] **No false positives**: Legitimate narrative text mentioning stats not incorrectly flagged as modifications
- [ ] **Validation**: Spot-check 20-30 sections with known stat modifications to verify extraction quality

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

**Output Schema:**
```json
{
  "section_id": "20",
  "stat_modifications": [
    {
      "stat": "skill",
      "amount": -1,
      "permanent": false,
      "confidence": 0.95
    }
  ]
}
```

**Generic Pattern Requirements:**
- Use semantic patterns (action verbs, stat names, numeric values), not hard-coded phrases
- Detect stat names: SKILL, STAMINA, LUCK (case-insensitive)
- Handle variations: "your SKILL" vs "SKILL" vs "skill"
- Support common action verbs: reduce, decrease, lose, increase, gain, restore, add, subtract

**Pattern Examples:**
- `"Reduce your SKILL by 1 point"` → stat: "skill", amount: -1
- `"Lose 2 STAMINA points"` → stat: "stamina", amount: -2
- `"Increase your SKILL by 2"` → stat: "skill", amount: +2
- `"Restore 5 STAMINA points"` → stat: "stamina", amount: +5
- `"You lose 3 STAMINA"` → stat: "stamina", amount: -3
- `"Gain 1 LUCK point"` → stat: "luck", amount: +1

**Edge Cases to Handle:**
- Multiple stat modifications in one section
- Implicit amounts ("Reduce your SKILL" → assume -1)
- Complex phrasing ("You notice your hand trembling as you pocket the Gold Piece. Reduce your SKILL by 1 point.")
- Permanent modifications ("Your initial SKILL is reduced by 1")
- Narrative mentions of stats that aren't modifications (e.g., "Your SKILL is 12")

---

## Tasks

- [ ] Analyze stat modification patterns in sample sections (20-30 sections with known stat changes)
- [ ] Design generic pattern detection (semantic patterns for action verbs, stats, amounts)
- [ ] Implement pattern-based detection (regex/keyword matching)
- [ ] Implement stat name extraction (SKILL, STAMINA, LUCK)
- [ ] Implement amount extraction (numeric values, positive/negative)
- [ ] Implement direction detection (increase vs decrease)
- [ ] Implement permanent flag detection (affects initial values)
- [ ] Implement LLM-based extraction for complex cases (optional, for validation)
- [ ] Create `extract_stat_modifications_v1` module in `modules/enrich/`
- [ ] Define output schema and add to `schemas.py` (may already exist in gamebook schema)
- [ ] Test on sample sections (verify all stat types and amounts detected)
- [ ] **Validate generality**: Test on multiple FF books to ensure no overfitting
- [ ] Verify no false positives (narrative text preserved, no false modification detection)
- [ ] Integrate into enrichment stage in canonical recipe
- [ ] Run full pipeline and validate extraction quality
- [ ] Document results and impact in work log

---

## Work Log

### 20251223-XXXX — Story created
- **Result:** Story defined.
- **Notes:** Stat modification extraction needed to parse SKILL/STAMINA/LUCK changes from sections. Must use generic semantic patterns, not hard-coded phrases, to work across all Fighting Fantasy books.
- **Next:** Analyze stat modification patterns in sample sections and design generic detection approach.

