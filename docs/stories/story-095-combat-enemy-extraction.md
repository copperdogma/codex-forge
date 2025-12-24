# Story: Combat and Enemy Extraction

**Status**: Done
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

- [x] **Enemy names detected**: Extract enemy/creature names from combat stat blocks
- [x] **SKILL scores detected**: Extract SKILL values (e.g., "SKILL 8")
- [x] **STAMINA scores detected**: Extract STAMINA values (e.g., "STAMINA 6")
- [x] **Combat outcomes detected**: Extract win/loss conditions and target sections (e.g., "If you win, turn to 71")
- [x] **Multiple enemies supported**: Handle sections with multiple combat encounters
- [x] **Structured output**: All combat data extracted into JSON format per section
- [x] **Generic patterns**: Detection uses structural patterns (SKILL/STAMINA keywords, numeric values), not hard-coded enemy names (works across all FF books)
- [x] **No false positives**: Legitimate narrative text mentioning SKILL/STAMINA not incorrectly flagged as combat
- [x] **Validation**: Spot-check 20-30 sections with known combat encounters to verify extraction quality

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

- [x] Define output schema and add to `schemas.py`
- [x] Update gamebook schema in `modules/validate/validate_ff_engine_node_v1/validator/gamebook-schema.json`
- [x] Create `extract_combat_v1` module in `modules/enrich/`
- [x] Implement pattern-based detection (regex/keyword matching for stat blocks)
- [x] Implement enemy name extraction (text before SKILL keyword)
- [x] Implement outcome detection (win/loss/escape target sections)
- [x] Implement LLM-based extraction for complex cases (optional, for validation)
- [x] Update `build_ff_engine_with_issues_v1` to handle multiple combat encounters
- [x] Implement try-validate-escalate approach with stat range checks
- [x] Analyze combat patterns in sample sections (20-30 sections with known combat encounters)
- [x] Test on sample sections (verify all stat types and outcomes detected)
- [x] **Validate generality**: Test on multiple FF books to ensure no overfitting
- [x] Verify no false positives (narrative text preserved, no false combat detection)
- [x] Integrate into enrichment stage in canonical recipe
- [x] Run full pipeline and validate extraction quality
- [x] Document results and impact in work log

---

## Work Log

### 20251223-XXXX — Schema and Module Implementation
- **Result:** Implemented `extract_combat_v1` module and updated core schemas.
- **Notes:** Enhanced `schemas.py` and `gamebook-schema.json` to support multiple enemies per section and flatter combat structure. Created hybrid regex+LLM extractor. Updated `build_ff_engine_with_issues_v1` to output the new format.
- **Next:** Analyze real-world patterns and test on sample sections.

### 20251223-XXXX — Try-Validate-Escalate Refinement
- **Result:** Refined module to follow try-validate-escalate pattern.
- **Notes:** Added realistic stat range checks (SKILL 1-15, STAMINA 1-40). Regex handles standard blocks; AI escalates on range failures, missing stats, multiple enemies, or special rules mentions.
- **Next:** Full book validation run.

### 20251223-XXXX — Full Book Validation and Refinement
- **Result:** Success. Validated extraction across all 400 sections of "Deathtrap Dungeon".
- **Notes:** Improved AI prompt to handle table-based stat blocks (e.g., Section 91 Orcs). Implemented HTML-source fallback for AI when plain text is sparse. Successfully extracted 32 combat encounters with high precision.

### 20251223-XXXX — Integration UX and Smoke Verification
- **Result:** Success.
- **Notes:** Updated `driver.py` to ensure `gamebook.json` and `validation_report.json` always land in the run root, even for `export` or `validate` stages. Verified `make smoke` passes with the new combat stage integrated and artifacts in correct locations.
- **Outcome:** Story 095 complete.

