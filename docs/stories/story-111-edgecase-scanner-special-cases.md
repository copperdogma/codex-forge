# Story: Edge-Case Scanner — Special-Case Detection Patterns

**Status**: To Do

---

## Problem Statement

We already handle combat outcomes and Test Your Luck, but other mechanics frequently appear in edge‑case forms that the core extractor can miss or mis-shape. We need a dedicated set of **scanner signals** that flag these special cases for targeted AI analysis and patching (Story 110).

## Goals

- Define concrete, reusable detection patterns for non‑combat special cases.
- Keep the detector generic and book‑agnostic (signals + reasoning, no hardcoded section IDs).
- Funnel only flagged sections into AI analysis (minimize cost).
- Produce a machine‑readable report with reason codes and evidence snippets.

## Acceptance Criteria

- [ ] Each special‑case category has explicit detection rules and example patterns.
- [ ] Reason codes are defined and suitable for use in a scanner report JSONL.
- [ ] At least one real run produces a report that includes multiple categories.
- [ ] Signals are phrased generically to apply across FF books.
- [ ] Notes include guidance for AI escalation prompts per category.

## Special‑Case Categories + Signals

### 1) Survival‑Gate Damage (implicit survival check)
**Reason code:** `survival_gate_damage`  
**Signal:** Text contains dice‑based damage or fixed damage + “if you are still alive / if you survive / if you are alive” leading to a target.  
**Why:** Often mis‑modeled as a stat_check or missing terminal logic.  
**Detection hints:**
- `roll ... die|dice` + `lose|reduce` + `stamina` + `if you are still alive`  
- `if you survive` + `turn to <N>`

### 2) Conditional Choice Branches (explicit yes/no branching)
**Reason code:** `conditional_choice_branch`  
**Signal:** Paired “if you do X, turn to A; if you do not, turn to B” in same paragraph.  
**Why:** Should become conditional sequence or explicit choice effects; duplicates are common.  
**Detection hints:**
- `if you (do|choose|decide|wish|want) ... turn to (\d+)`  
- `if you (do not|don't|refuse) ... turn to (\d+)`

### 3) Inventory/State Checks with Dual Outcomes
**Reason code:** `dual_item_check` / `dual_state_check`  
**Signal:** “If you have X, turn to A; if not, turn to B” or “Have you previously read/seen X?”  
**Why:** Often split into two separate checks or left as choices.  
**Detection hints:**
- `if you have|possess|carry` + `turn to` + paired `if you do not`  
- `have you previously read|seen|visited` + `turn to`

### 4) Dice‑Based Damage Without Explicit Branch
**Reason code:** `dice_damage_no_branch`  
**Signal:** Dice roll determines stamina loss with no explicit branching.  
**Why:** Should be modeled as `stat_change` with expression, not a choice/check.  
**Detection hints:**
- `roll ... die|dice` + `lose|reduce` + `stamina` and **no** nearby `turn to`

### 5) Non‑Target Terminal Outcomes
**Reason code:** `terminal_outcome_text`  
**Signal:** Outcome text implies death/victory/end without a target section.  
**Why:** Should be encoded as `terminal` outcome rather than a missing target or bogus choice.  
**Detection hints:**
- `you die|your adventure ends|you are slain|victory` with no `turn to`

### 6) Multi‑Item Requirements (itemsAll)
**Reason code:** `multi_item_requirement`  
**Signal:** “If you have both X and Y” or “if you have X and Y” leading to target.  
**Why:** Should map to `itemsAll` in `item_check` event.  
**Detection hints:**
- `if you have` + `and` + `turn to`  
- `if you have both`

## Suggested Scanner Output (JSONL)

```json
{
  "section_id": "189",
  "reason_code": "survival_gate_damage",
  "signal": "roll+lose stamina + if you are still alive",
  "snippet": "Roll one die, add 1, reduce STAMINA by total. If you are still alive, turn to 10."
}
```

## AI Escalation Guidance (by category)

- **survival_gate_damage**: Extract damage expression and confirm whether survival is implicit (terminal) vs explicit target.  
- **conditional_choice_branch**: Return a `conditional` sequence event with explicit `then/else` outcomes.  
- **dual_item_check / dual_state_check**: Combine into a single check with `has/missing` (or `itemsAll`).  
- **dice_damage_no_branch**: Return a `stat_change` with `amount` expression and `scope: section`.  
- **terminal_outcome_text**: Return `terminal` outcome with `kind` and optional message.  
- **multi_item_requirement**: Return `item_check` with `itemsAll` list and `has/missing` outcomes.

## Tasks

- [ ] Convert signals into scanner rules and reason codes (Story 110 module).
- [ ] Add tests with representative text snippets for each reason code.
- [ ] Run a real book and verify flagged results include multiple categories.
- [ ] Document AI prompt templates for each category in Story 110.

## Work Log

<!-- Append-only log entries. -->

### 20260102-1312 — Drafted special‑case detection patterns for scanner
- **Result:** Success.
- **Notes:** Added categories, reason codes, detection hints, and escalation guidance to seed the scanner design.
- **Next:** Implement signals in the Story 110 scanner and add tests.
