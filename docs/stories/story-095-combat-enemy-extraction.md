# Story: Combat and Enemy Extraction

**Status**: To Do  
**Created**: 2025-12-23  
**Priority**: High  
**Parent Story**: story-006 (Enrichment pass)

---

## Goal

Extract combat encounter information from gamebook sections into structured JSON data. Detect enemy names, SKILL scores, STAMINA scores, and combat outcomes (win/loss conditions and target sections).

---

## Motivation

Fighting Fantasy gamebooks frequently feature combat encounters:
- Enemies with stat blocks (e.g., "SKELETON WARRIOR SKILL 8 STAMINA 6")
- Combat outcomes ("If you win, turn to 71")
- Multiple enemies in a single section
- Special combat rules (escape options, special abilities)

Currently, this information is only present in plain text. Extracting it into structured data enables:
- Game engine combat system integration
- Automatic stat tracking and combat resolution
- Combat outcome navigation (win/loss paths)
- Enemy database building for game mechanics

**Example from section 331:**
- Enemy: "SKELETON WARRIOR"
- SKILL: 8
- STAMINA: 6
- Outcome: "If you win, turn to 71"

---

## Success Criteria

- [ ] **Enemy names detected**: Extract enemy/creature names from combat stat blocks
- [ ] **SKILL scores detected**: Extract SKILL values (e.g., "SKILL 8")
- [ ] **STAMINA scores detected**: Extract STAMINA values (e.g., "STAMINA 6")
- [ ] **Combat outcomes detected**: Extract win/loss conditions and target sections (e.g., "If you win, turn to 71")
- [ ] **Multiple enemies supported**: Handle sections with multiple combat encounters
- [ ] **Structured output**: All combat data extracted into JSON format per section:
  ```json
  {
    "combat": [
      {
        "enemy": "SKELETON WARRIOR",
        "skill": 8,
        "stamina": 6,
        "win_section": "71",
        "loss_section": null
      }
    ]
  }
  ```
- [ ] **Generic patterns**: Detection uses structural patterns (SKILL/STAMINA keywords, numeric values), not hard-coded enemy names (works across all FF books)
- [ ] **No false positives**: Legitimate narrative text mentioning SKILL/STAMINA not incorrectly flagged as combat
- [ ] **Validation**: Spot-check 20-30 sections with known combat encounters to verify extraction quality

---

## Solution Approach

**New Module**: `modules/enrich/extract_combat_v1/`

**Detection Strategy:**
1. **Pattern-based detection** (regex/keyword matching for stat blocks):
   - Stat block pattern: `[ENEMY NAME] SKILL [NUMBER] STAMINA [NUMBER]`
   - Variations: "SKILL X STAMINA Y", "SKILL: X STAMINA: Y", "SKILL X, STAMINA Y"
   - Enemy name extraction: Text before "SKILL" keyword (typically all caps, 2-50 chars)
   - Outcome patterns: "If you win, turn to X", "If you lose, turn to Y", "If you defeat", "If you are defeated"

2. **LLM-based extraction** (for complex/ambiguous cases):
   - Use LLM to parse combat encounters from section text
   - Extract structured JSON with enemy names, stats, outcomes
   - Handle edge cases (implicit enemies, complex combat rules)

3. **Hybrid approach** (recommended):
   - Use pattern matching for fast, deterministic detection of stat blocks
   - Use LLM for validation and complex cases (multiple enemies, special rules)
   - Combine results with confidence scoring

**Output Schema:**
```json
{
  "section_id": "331",
  "combat": [
    {
      "enemy": "SKELETON WARRIOR",
      "skill": 8,
      "stamina": 6,
      "win_section": "71",
      "loss_section": null,
      "escape_section": null,
      "special_rules": null,
      "confidence": 0.95
    }
  ]
}
```

**Generic Pattern Requirements:**
- Use structural patterns (SKILL/STAMINA keywords, numeric values), not specific enemy names
- Detect enemy names from context (text before SKILL keyword, typically all caps)
- Handle variations: "SKILL 8 STAMINA 6" vs "SKILL: 8 STAMINA: 6" vs "SKILL 8, STAMINA 6"
- Support optional fields: LUCK scores, escape sections, special combat rules

**Pattern Examples:**
- `"SKELETON WARRIOR SKILL 8 STAMINA 6"` → enemy: "SKELETON WARRIOR", skill: 8, stamina: 6
- `"ORC SKILL 7 STAMINA 9"` → enemy: "ORC", skill: 7, stamina: 9
- `"MANTICORE SKILL 11 STAMINA 11"` → enemy: "MANTICORE", skill: 11, stamina: 11
- `"If you win, turn to 71"` → win_section: "71"
- `"If you lose, turn to 200"` → loss_section: "200"

**Edge Cases to Handle:**
- Multiple enemies in one section
- Enemies with LUCK scores
- Escape options ("If you wish to escape, turn to X")
- Special combat rules ("You must fight two rounds", "You fight with -2 SKILL")
- Narrative mentions of SKILL/STAMINA that aren't combat (e.g., "Your SKILL is 12")

---

## Tasks

- [ ] Analyze combat patterns in sample sections (20-30 sections with known combat encounters)
- [ ] Design generic pattern detection (structural patterns for SKILL/STAMINA, not enemy-specific)
- [ ] Implement pattern-based detection (regex/keyword matching for stat blocks)
- [ ] Implement enemy name extraction (text before SKILL keyword)
- [ ] Implement outcome detection (win/loss/escape target sections)
- [ ] Implement LLM-based extraction for complex cases (optional, for validation)
- [ ] Create `extract_combat_v1` module in `modules/enrich/`
- [ ] Define output schema and add to `schemas.py`
- [ ] Test on sample sections (verify all stat types and outcomes detected)
- [ ] **Validate generality**: Test on multiple FF books to ensure no overfitting
- [ ] Verify no false positives (narrative text preserved, no false combat detection)
- [ ] Integrate into enrichment stage in canonical recipe
- [ ] Run full pipeline and validate extraction quality
- [ ] Document results and impact in work log

---

## Work Log

### 20251223-XXXX — Story created
- **Result:** Story defined.
- **Notes:** Combat extraction needed to parse enemy stat blocks (SKILL/STAMINA) and combat outcomes from sections. Must use generic structural patterns, not hard-coded enemy names, to work across all Fighting Fantasy books.
- **Next:** Analyze combat patterns in sample sections and design generic detection approach.

