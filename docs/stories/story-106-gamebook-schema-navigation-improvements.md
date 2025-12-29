# Story: Gamebook Schema Navigation Improvements

**Status**: To Do  
**Created**: 2025-01-13  
**Priority**: Medium  
**Parent Story**: story-104 (Gamebook Output File Tweaks)

---

## Goal

Investigate and implement improvements to the `gamebook.json` schema to eliminate duplicate navigation edges that confuse graph consumers (e.g., visualization tools), while preserving semantic clarity about what the source text says vs. what game mechanics control navigation.

---

## Motivation

**The Problem:**

Current schema design creates duplicate edges in the navigation graph:

- `navigationLinks` contains ALL navigation targets extracted from text (including "Turn to 105", "Turn to 235")
- `testYourLuck` also contains those same targets (luckySection: 105, unluckySection: 235)
- `items[].checkSuccessSection` / `checkFailureSection` duplicate targets already in `navigationLinks`
- `combat[].winSection` / `loseSection` duplicate targets already in `navigationLinks`

This duplication causes problems for consumers:
- Graph layout algorithms see duplicate edges and get confused about graph structure
- Consumers must implement deduplication logic, but the schema doesn't indicate which fields should take precedence
- The semantic distinction (text says "turn to X" vs. mechanic controls navigation) is lost in practice

**Current State:**

- `navigationLinks` is built from `choices`/`targets` in enriched portions via `make_navigation()` in `build_ff_engine_v1/main.py`
- `isConditional` field exists in `NavigationLink` schema but is **always set to `False`**
- `conditionalNavigation` exists in schema but is **never populated** (per story-030 notes, planned but not implemented)
- Enrichment stages populate `testYourLuck`, `items`, and `combat` independently from choice extraction

**Example from Transcript:**

Section 98 had:
- `navigationLinks: [{targetSection: "105"}, {targetSection: "235"}]`
- `testYourLuck: [{luckySection: "105", unluckySection: "235"}]`

This created 4 edges (2 from navigationLinks, 2 from testYourLuck) when only 2 were intended.

---

## Success Criteria

- [ ] **Problem analyzed**: Document current schema behavior, identify all sources of duplicate edges
- [ ] **Options evaluated**: Compare proposed solutions (flagging, restructuring, deduplication) against pipeline constraints
- [ ] **Recommendation made**: Propose best approach considering:
  - Backward compatibility with existing consumers
  - Ease of implementation in `build_ff_engine_v1`
  - Schema clarity for new consumers
  - Preservation of semantic information (text vs. mechanics)
- [ ] **Implementation plan**: If proceeding, define tasks for schema update, builder changes, and validation

---

## Approach

### Phase 1: Analysis

1. **Map current data flow:**
   - Trace how `navigationLinks` are populated from `choices`/`targets` in enriched portions
   - Trace how `testYourLuck`, `items`, `combat` are populated from enrichment stages
   - Identify where duplicates occur (which sections have both navigationLinks and mechanics)

2. **Evaluate proposed Option 1 (Flag conditional navigation):**
   - Use `isConditional: true` to mark navigationLinks controlled by mechanics
   - Add optional `conditionalType` field (e.g., "testYourLuck", "itemCheck", "combat")
   - Filter logic: `navigationLinks.filter(l => !l.isConditional)` for graph generation
   - **Pros**: Minimal schema change, uses existing field, preserves semantic separation
   - **Cons**: Requires builder logic to detect overlaps and mark links

3. **Evaluate alternative Option 2 (Move choice text into mechanics):**
   - Remove targets from `navigationLinks` when they're controlled by mechanics
   - Add `choiceText` to `testYourLuck`, `items`, `combat` structures
   - **Pros**: No duplicates by construction, single source of truth
   - **Cons**: Breaking change, loses "what text says" semantic, requires schema changes

4. **Evaluate alternative Option 3 (Use conditionalNavigation):**
   - Populate `conditionalNavigation` array from mechanics
   - Keep `navigationLinks` only for unconditional navigation
   - **Pros**: Schema already supports this pattern, explicit structure
   - **Cons**: Would require implementing conditionalNavigation mapping (noted as TODO in story-030), more complex structure

5. **Consider hybrid approaches:**
   - Combine flagging with conditionalNavigation for structured cases
   - Keep simple flagging for simple cases (testYourLuck, item checks)
   - Use conditionalNavigation for complex cases (stat checks with multiple conditions)

### Phase 2: Recommendation

Based on analysis, recommend approach considering:
- **Pipeline feasibility**: Can we detect overlaps reliably in `build_ff_engine_v1`?
- **Consumer impact**: Will existing validators/graph tools break?
- **Schema evolution**: Is this a temporary fix or long-term solution?
- **Maintenance burden**: Which approach is easiest to keep correct as enrichment improves?

### Phase 3: Implementation (if proceeding)

If Option 1 (flagging) is recommended:
1. Update `NavigationLink` schema to add optional `conditionalType` field
2. Modify `make_navigation()` in `build_ff_engine_v1/main.py` to:
   - Collect targets from mechanics (testYourLuck, items, combat)
   - Mark matching navigationLinks with `isConditional: true` and `conditionalType`
3. Update `collect_targets()` to optionally skip conditional links (or document current behavior)
4. Add validation to ensure flagged links match their mechanics
5. Test on full book run and verify graph consumers work correctly

---

## Tasks

- [ ] **Analyze current state**: Inspect a full book run's `gamebook.json` to quantify duplicate edges (how many sections have overlaps?)
- [ ] **Trace data flow**: Document how `navigationLinks`, `testYourLuck`, `items`, `combat` are populated from enriched portions
- [ ] **Evaluate Option 1**: Assess feasibility of detecting overlaps in `make_navigation()` and marking links correctly
- [ ] **Evaluate Option 2**: Consider breaking change impact and whether it's worth the cleaner structure
- [ ] **Evaluate Option 3**: Assess whether implementing `conditionalNavigation` mapping would solve this comprehensively
- [ ] **Check consumer impact**: Review validator code and graph tools to see how they use navigationLinks
- [ ] **Recommend approach**: Document recommendation with pros/cons and implementation complexity
- [ ] **Implementation plan**: If proceeding, break down into concrete tasks for schema + builder changes

---

## Notes / Analysis

### Current Schema Structure

From `modules/validate/validate_ff_engine_node_v1/validator/gamebook-schema.json`:

```json
{
  "navigationLinks": [{
    "targetSection": "string",
    "choiceText": "string (optional)",
    "isConditional": "boolean (default: false)"  // ← Currently always false
  }],
  "testYourLuck": [{
    "luckySection": "string",
    "unluckySection": "string"
  }],
  "items": [{
    "name": "string",
    "action": "add|remove|check|reference",
    "checkSuccessSection": "string (optional)",
    "checkFailureSection": "string (optional)"
  }],
  "combat": [{
    "creature": {...},
    "winSection": "string",
    "loseSection": "string (optional)"
  }],
  "conditionalNavigation": [{  // ← Exists but never populated
    "condition": "has_item|test_luck|stat_check|skill_check|custom",
    "ifTrue": NavigationLink,
    "ifFalse": NavigationLink
  }]
}
```

### Current Builder Logic

From `modules/export/build_ff_engine_v1/main.py`:

- `make_navigation()`: Extracts ALL choices/targets → `navigationLinks`, always sets `isConditional: False`
- `build_section()`: Independently copies `testYourLuck`, `items`, `combat` from portions
- No overlap detection or deduplication logic

### Proposed Option 1 Details

**Schema change:**
```json
{
  "navigationLinks": [{
    "targetSection": "string",
    "choiceText": "string (optional)",
    "isConditional": "boolean (default: false)",
    "conditionalType": "testYourLuck|itemCheck|combat|statCheck (optional)"  // ← New field
  }]
}
```

**Builder logic (pseudo-code):**
```python
def make_navigation(portion):
    nav_links = []
    mechanics_targets = collect_mechanics_targets(portion)  # {105, 235} from testYourLuck, etc.
    
    for choice in portion.get("choices") or []:
        target = choice.get("target")
        if target in mechanics_targets:
            conditional_type = find_conditional_type(target, portion)  # "testYourLuck", etc.
            nav_links.append({
                "targetSection": target,
                "choiceText": choice.get("text"),
                "isConditional": True,
                "conditionalType": conditional_type
            })
        else:
            nav_links.append({
                "targetSection": target,
                "choiceText": choice.get("text"),
                "isConditional": False
            })
    return nav_links
```

**Consumer logic:**
```javascript
// For graph generation, filter out conditional links
const unconditionalLinks = section.navigationLinks.filter(l => !l.isConditional);
// Or use mechanics fields directly: section.testYourLuck, section.items, section.combat
```

### Questions to Resolve

1. **Can we reliably detect overlaps?**
   - What if a section has both "Turn to 105" (unconditional) and testYourLuck → 105?
   - Need rules for precedence: mechanics take priority? Or text takes priority?

2. **What about sections with multiple mechanics?**
   - Section with both testYourLuck and itemCheck pointing to same target?
   - Option: `conditionalType` as array? Or mark with primary mechanic?

3. **Backward compatibility:**
   - Will existing validators break if `isConditional: true` appears?
   - Will graph tools need updates, or can they ignore the flag?

4. **Schema versioning:**
   - Is this a minor schema evolution (add optional field) or breaking change?
   - Should we bump `formatVersion` in metadata?

---

## Work Log

- 2025-01-13 — Story created to investigate duplicate navigation edges in gamebook.json schema. Problem identified from user transcript where graph visualization was confused by duplicate edges (navigationLinks + testYourLuck pointing to same sections). Current state: `isConditional` field exists but always `False`, `conditionalNavigation` exists but never populated. Need to evaluate Option 1 (flag conditional links), Option 2 (move targets to mechanics), Option 3 (use conditionalNavigation), or hybrid approaches. Next: Analyze current data flow and quantify duplicate edge problem.
