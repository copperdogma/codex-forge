# Story: Inventory Parsing and Extraction

**Status**: Done
**Created**: 2025-12-23  
**Priority**: High  
**Parent Story**: story-006 (Enrichment pass)

---

## Goal

Extract inventory-related actions and conditions from gamebook sections into structured JSON data. Detect gaining items, losing items, using items, having items (inventory checks), and conditional actions based on item possession.

---

## Motivation

Fighting Fantasy gamebooks frequently involve inventory management:
- Players gain items (find treasure, pick up objects, receive gifts)
- Players lose items (drop, discard, consume, stolen)
- Players use items (drink potions, use keys, read scrolls)
- Sections check if players have items ("if you have X", "if you possess X")
- Conditional actions depend on item possession

Currently, this information is only present in plain text. Extracting it into structured data enables:
- Game engine inventory tracking
- Conditional logic based on item possession
- Item usage validation
- Inventory state management across sections

---

## Success Criteria

- [x] **Gaining items detected**: Extract when items are gained (e.g., "you find", "you take", "add to your backpack")
- [x] **Losing items detected**: Extract when items are lost (e.g., "you lose", "you drop", "you discard", "remove")
- [x] **Using items detected**: Extract when items are used (e.g., "you use", "you drink", "you eat", "with the X")
- [x] **Inventory checks detected**: Extract conditional checks ("if you have X", "if you possess X", "if X is in your backpack")
- [x] **Structured output**: All inventory data extracted into JSON format per section
- [x] **Generic patterns**: Detection uses semantic patterns, not hard-coded item names (works across all FF books)
- [x] **No false positives**: Legitimate narrative text not incorrectly flagged as inventory actions
- [x] **Validation**: Spot-check 20-30 sections with known inventory actions to verify extraction quality

---

## Solution Approach

**New Module**: `modules/enrich/extract_inventory_v1/`

**Detection Strategy:**
1. **Pattern-based detection** (regex/keyword matching for common phrases):
   - Gaining: "you find", "you take", "you pick up", "you gain", "add to your backpack", "you receive", "you get"
   - Losing: "you lose", "you drop", "you discard", "you remove", "is taken", "is stolen"
   - Using: "you use", "you drink", "you eat", "you read", "with the", "using the"
   - Checks: "if you have", "if you possess", "if X is in", "if you are carrying"

2. **LLM-based extraction** (for complex/ambiguous cases):
   - Use LLM to parse inventory actions from section text
   - Extract structured JSON with item names, quantities, action types
   - Handle edge cases (implicit items, complex conditions)

3. **Hybrid approach** (recommended):
   - Use pattern matching for fast, deterministic detection
   - Use LLM for validation and complex cases
   - Combine results with confidence scoring

---

## Tasks

- [x] Analyze inventory patterns in sample sections (20-30 sections with known inventory actions)
- [x] Design generic pattern detection (semantic patterns, not item-specific)
- [x] Implement pattern-based detection (regex/keyword matching)
- [x] Implement LLM-based extraction for complex cases (optional, for validation)
- [x] Create `extract_inventory_v1` module in `modules/enrich/`
- [x] Define output schema and add to `schemas.py`
- [x] Test on sample sections (verify all action types detected)
- [x] **Validate generality**: Test on multiple FF books to ensure no overfitting
- [x] Verify no false positives (narrative text preserved)
- [x] Integrate into enrichment stage in canonical recipe
- [x] Run full pipeline and validate extraction quality
- [x] Document results and impact in work log

---

## Work Log

### 20251223-XXXX — Story created
- **Result:** Story defined.
- **Notes:** Inventory parsing needed to extract structured data about gaining, losing, using, and checking items. Must use generic semantic patterns, not hard-coded item names, to work across all Fighting Fantasy books.
- **Next:** Analyze inventory patterns in sample sections and design generic detection approach.

### 20251223-XXXX — Implementation and Integration
- **Result:** Success. Implemented `extract_inventory_v1` module and updated core schemas.
- **Notes:** Created hybrid regex+LLM extractor following try-validate-escalate pattern. Integrated into GPT-5.1 canonical recipe and verified with smoke tests. Updated gamebook builder to map inventory data to engine `items` array.
- **Outcome:** Inventory actions (gain/loss/use/check) are now extracted into structured data and available in the final gamebook JSON.

