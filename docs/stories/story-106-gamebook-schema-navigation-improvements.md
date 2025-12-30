# Story: Gamebook Schema Navigation Improvements

**Status**: Done  
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

- [x] **Problem analyzed**: Document current schema behavior, identify all sources of duplicate edges
- [x] **Options evaluated**: Compare proposed solutions (flagging, restructuring, deduplication) against pipeline constraints
- [x] **Recommendation made**: Propose best approach considering:
  - Backward compatibility with existing consumers
  - Ease of implementation in `build_ff_engine_v1`
  - Schema clarity for new consumers
  - Preservation of semantic information (text vs. mechanics)
- [x] **Implementation plan**: If proceeding, define tasks for schema update, builder changes, and validation
- [x] **Unified navigation implemented**: `gamebook.json` uses a single `navigation` array and removes duplicate mechanics targets
- [x] **Validators updated**: All validators/consumers read `navigation` and no longer rely on `navigationLinks`/`conditionalNavigation`
- [x] **Run + verify**: Pipeline run executed via `driver.py` with artifacts inspected under `output/runs/`

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

- [x] **Analyze current state**: Inspect a full book run's `gamebook.json` to quantify duplicate edges (how many sections have overlaps?)
- [x] **Trace data flow**: Document how `navigationLinks`, `testYourLuck`, `items`, `combat` are populated from enriched portions
- [x] **Evaluate Option 1**: Assess feasibility of detecting overlaps in `make_navigation()` and marking links correctly
- [x] **Evaluate Option 2**: Consider breaking change impact and whether it's worth the cleaner structure
- [x] **Evaluate Option 3**: Assess whether implementing `conditionalNavigation` mapping would solve this comprehensively
- [x] **Check consumer impact**: Review validator code and graph tools to see how they use navigationLinks
- [x] **Recommend approach**: Document recommendation with pros/cons and implementation complexity
- [x] **Implementation plan**: If proceeding, break down into concrete tasks for schema + builder changes
- [x] **Define unified navigation schema**: Update `gamebook-schema.json` + validator types to use `navigation` array
- [x] **Update builders**: Emit unified `navigation` in `build_ff_engine_v1` and `build_ff_engine_with_issues_v1`
- [x] **Update validators**: Adjust `validate_ff_engine_v2`, `validate_gamebook_smoke_v1`, `validate_choice_completeness_v1`, and node validator to use `navigation`
- [x] **Regenerate gamebook**: Run pipeline (driver) and verify new `gamebook.json` has no duplicate edges
- [x] **Manual inspection**: Open artifacts in `output/runs/` and verify navigation samples are correct

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

### Recommendation (Draft)

Given no backward-compat constraints, prefer a **single canonical navigation surface** that cleanly separates player choices from mechanic-driven outcomes and eliminates duplication at the source. Proposed direction:

- **Replace `navigationLinks` + mechanic target fields with a unified `navigation` array** that includes:
  - `targetSection`
  - `kind`: `choice | test_luck | item_check | combat | stat_check | death | custom`
  - `outcome` (e.g., `lucky/unlucky`, `win/lose/escape`, `pass/fail`)
  - `choiceText` (only for `kind: choice`)
  - `params` for mechanics (e.g., `{ itemName: "Sapphire" }`)
- **Mechanics arrays (`testYourLuck`, `items`, `combat`) become descriptive only** (no target sections), or are folded into a single `mechanics` array that carries rules/state changes but not navigation edges.

This avoids duplicate edges entirely, preserves semantic clarity (choice vs mechanic), and simplifies graph consumers to read a single navigation list.

---

## Work Log

- 2025-01-13 — Story created to investigate duplicate navigation edges in gamebook.json schema. Problem identified from user transcript where graph visualization was confused by duplicate edges (navigationLinks + testYourLuck pointing to same sections). Current state: `isConditional` field exists but always `False`, `conditionalNavigation` exists but never populated. Need to evaluate Option 1 (flag conditional links), Option 2 (move targets to mechanics), Option 3 (use conditionalNavigation), or hybrid approaches. Next: Analyze current data flow and quantify duplicate edge problem.

### 20251229-1649 — Inspected builder + schema for navigation sources
- **Result:** Success; traced current navigation link construction and schema fields.
- **Notes:** `modules/export/build_ff_engine_v1/main.py` builds `navigationLinks` solely from `choices`/`targets` and always sets `isConditional: False`; mechanics (`testYourLuck`, `items`, `combat`, `deathConditions`) are copied into sections separately. `collect_targets()` aggregates targets from both `navigationLinks` and mechanics (confirming duplication risk). Schema already defines `conditionalNavigation` and `NavigationLink.isConditional` but exporter never populates `conditionalNavigation`. `modules/validate/validate_ff_engine_node_v1/validator/gamebook-schema.json` still models `navigationLinks` as unconditional and includes `conditionalNavigation`, suggesting Option 3 is schema-aligned but unimplemented.
- **Next:** Inspect a recent `gamebook.json` in `output/runs/` to quantify duplicate edges and identify overlap patterns (testYourLuck vs. items vs. combat).

### 20251229-1652 — Quantified duplicate navigation edges in current run
- **Result:** Success; duplicates confirmed and quantified in `ff-ai-ocr-gpt51-pristine-fast-full`.
- **Notes:** In `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/gamebook.json`, 37 of 401 sections have overlapping targets between `navigationLinks` and mechanics. Total overlap edges: 66. Overlaps are driven by `testYourLuck` (27 sections) and `items` checks (12 sections); no overlap found for combat/death conditions in this run. Examples: Section 5 has `navigationLinks` {185,395} and `testYourLuck` {185,395}; Section 31 has `navigationLinks` {3,376} and item checks referencing those same targets; Section 47 similarly duplicates item-check targets.
- **Next:** Review graph/validator consumers to see how they interpret `navigationLinks`, then recommend the cleanest schema redesign (no backward-compat constraints per user).

### 20251229-1656 — Reviewed consumer/validator usage of navigation targets
- **Result:** Success; identified current consumers and sensitivity to removing nav links.
- **Notes:** `modules/validate/validate_ff_engine_node_v1/validator/validation.js` reachability and target checks treat `navigationLinks`, `conditionalNavigation`, `combat`, `testYourLuck`, and `items` as separate navigation sources; duplicates don’t break validation but they do amplify graph edges. `modules/validate/validate_ff_engine_v2/main.py` similarly treats nav links + mechanics as navigation. `modules/validate/validate_choice_completeness_v1/main.py` compares text refs to `choices`/`navigationLinks` only and ignores mechanics—so if we remove nav links for mechanics we must update this validator (or add a mechanics-aware path).
- **Next:** Draft recommendation and concrete schema changes that avoid duplicates while keeping choice completeness and reachability validators correct.

### 20251229-1701 — Drafted schema recommendation (no backward compat)
- **Result:** Success; added draft recommendation in Notes.
- **Notes:** Proposed a unified `navigation` array as the single canonical edge list, with `kind/outcome/params` to distinguish choices vs mechanics, and making mechanics arrays descriptive-only (no target sections). This removes duplication and keeps semantics explicit for graph consumers.
- **Next:** Confirm preferred schema direction with user, then enumerate concrete implementation tasks (schema updates, exporter changes, validator updates, migration of choice completeness checks).

### 20251229-1658 — Updated story criteria and tasks for unified navigation implementation
- **Result:** Success; checklist expanded to include schema/build/validator updates and pipeline verification.
- **Notes:** Added success criteria for unified navigation output and validator updates; appended implementation tasks for schema, builders, validators, run + manual inspection.
- **Next:** Implement unified navigation schema and update builders/validators accordingly.

### 20251229-1710 — Implemented unified navigation schema and updated builders/validators
- **Result:** Success; code updated to emit `navigation` edges and remove duplicate mechanic targets.
- **Notes:** Builders now emit a canonical `navigation` array (choices + mechanics) and strip target fields from items/combat/test_luck/deathConditions/diceChecks. `build_ff_engine_v1` combat output aligned to list-of-encounters. Schema + node validator updated to define `navigation` and drop `navigationLinks`/`conditionalNavigation` target checks. Python validators now read `navigation` for choice/target validation. Files touched: `modules/export/build_ff_engine_v1/main.py`, `modules/export/build_ff_engine_with_issues_v1/main.py`, `modules/validate/validate_ff_engine_node_v1/validator/gamebook-schema.json`, `modules/validate/validate_ff_engine_node_v1/validator/validation.js`, `modules/validate/validate_ff_engine_node_v1/validator/types.d.ts`, `modules/validate/validate_ff_engine_v2/main.py`, `modules/validate/validate_gamebook_smoke_v1/main.py`, `modules/validate/validate_choice_completeness_v1/main.py`.
- **Next:** Run `driver.py` to rebuild `gamebook.json` for `ff-ai-ocr-gpt51-pristine-fast-full`, then manually inspect navigation samples in `output/runs/` for correctness.

### 20251229-1714 — Rebuilt gamebook + verified unified navigation output
- **Result:** Success; `driver.py` run from `build_gamebook` completed and outputs verified.
- **Notes:** Ran `python driver.py --recipe configs/recipes/recipe-ff-ai-ocr-gpt51.yaml --run-id ff-ai-ocr-gpt51-pristine-fast-full-nav2 --allow-run-id-reuse --output-dir output/runs/ff-ai-ocr-gpt51-pristine-fast-full-nav2 --start-from build_gamebook` (reused upstream artifacts). Inspected `output/runs/ff-ai-ocr-gpt51-pristine-fast-full-nav2/gamebook.json` and confirmed: no `navigationLinks`/`conditionalNavigation`/`testYourLuck`; no mechanic target fields in `items`, `combat`, `diceChecks`, or `deathConditions`. Sample navigation verified: Section 5 now only `test_luck` edges to 185/395 (with choiceText), Section 31 item check edges to 376/3 (with choiceText), Section 6 combat edge to 364 with params `{enemy: MANTICORE}`; mechanics remain descriptive-only.
- **Next:** Update any remaining documentation (if needed) and confirm whether to clean up the intermediate run dir `ff-ai-ocr-gpt51-pristine-fast-full-nav`.

### 20251229-1725 — Re-validated unified navigation with tightened outcome enums
- **Result:** Success; validation report regenerated against the canonical run directory.
- **Notes:** Ran `PYTHONPATH=. python modules/validate/validate_ff_engine_v2/main.py --gamebook output/runs/ff-ai-ocr-gpt51-pristine-fast-full/gamebook.json --out output/runs/ff-ai-ocr-gpt51-pristine-fast-full/validation_report.navigation.json --expected-range-start 1 --expected-range-end 400`. Output written to `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/validation_report.navigation.json`.
- **Next:** None.
