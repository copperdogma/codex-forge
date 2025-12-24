# Story: Inventory Parsing and Extraction

**Status**: To Do  
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

- [ ] **Gaining items detected**: Extract when items are gained (e.g., "you find", "you take", "add to your backpack")
- [ ] **Losing items detected**: Extract when items are lost (e.g., "you lose", "you drop", "you discard", "remove")
- [ ] **Using items detected**: Extract when items are used (e.g., "you use", "you drink", "you eat", "with the X")
- [ ] **Inventory checks detected**: Extract conditional checks ("if you have X", "if you possess X", "if X is in your backpack")
- [ ] **Structured output**: All inventory data extracted into JSON format per section:
  ```json
  {
    "items_gained": [{"item": "Gold Pieces", "quantity": 10}],
    "items_lost": [{"item": "Rope"}],
    "items_used": [{"item": "Potion of Strength"}],
    "inventory_checks": [{"item": "Lantern", "condition": "if you have"}]
  }
  ```
- [ ] **Generic patterns**: Detection uses semantic patterns, not hard-coded item names (works across all FF books)
- [ ] **No false positives**: Legitimate narrative text not incorrectly flagged as inventory actions
- [ ] **Validation**: Spot-check 20-30 sections with known inventory actions to verify extraction quality

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

**Output Schema:**
```json
{
  "section_id": "42",
  "inventory": {
    "items_gained": [
      {"item": "Gold Pieces", "quantity": 10, "confidence": 0.95}
    ],
    "items_lost": [
      {"item": "Rope", "quantity": 1, "confidence": 0.90}
    ],
    "items_used": [
      {"item": "Potion of Strength", "confidence": 0.95}
    ],
    "inventory_checks": [
      {
        "item": "Lantern",
        "condition": "if you have",
        "target_section": "43",
        "confidence": 0.90
      }
    ]
  }
}
```

**Generic Pattern Requirements:**
- Use semantic patterns (action verbs, conditional phrases), not specific item names
- Detect item names from context (nouns after action verbs)
- Handle variations: "a lantern" vs "the lantern" vs "lantern"
- Support quantity extraction: "10 Gold Pieces", "a rope", "two potions"

**Examples to Detect:**
- "You find 10 Gold Pieces and add them to your backpack."
- "If you have a Lantern, turn to 43."
- "You drink the Potion of Strength."
- "You drop your Rope into the chasm."
- "If you possess the Emerald Eye, turn to 200."

---

## Tasks

- [ ] Analyze inventory patterns in sample sections (20-30 sections with known inventory actions)
- [ ] Design generic pattern detection (semantic patterns, not item-specific)
- [ ] Implement pattern-based detection (regex/keyword matching)
- [ ] Implement LLM-based extraction for complex cases (optional, for validation)
- [ ] Create `extract_inventory_v1` module in `modules/enrich/`
- [ ] Define output schema and add to `schemas.py`
- [ ] Test on sample sections (verify all action types detected)
- [ ] **Validate generality**: Test on multiple FF books to ensure no overfitting
- [ ] Verify no false positives (narrative text preserved)
- [ ] Integrate into enrichment stage in canonical recipe
- [ ] Run full pipeline and validate extraction quality
- [ ] Document results and impact in work log

---

## Work Log

### 20251223-XXXX — Story created
- **Result:** Story defined.
- **Notes:** Inventory parsing needed to extract structured data about gaining, losing, using, and checking items. Must use generic semantic patterns, not hard-coded item names, to work across all Fighting Fantasy books.
- **Next:** Analyze inventory patterns in sample sections and design generic detection approach.

