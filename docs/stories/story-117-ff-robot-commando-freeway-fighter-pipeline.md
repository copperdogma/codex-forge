# Story: FF Robot Commando + Freeway Fighter Pipeline Bring-Up

**Status**: Done

---

## Problem Statement

We need to validate the current pipeline against two new Fighting Fantasy books: **Robot Commando** and **Freeway Fighter**. A full run on Robot Commando has already failed, and we have to determine why, fix the pipeline, and extend the engine if these books introduce new gameplay concepts (e.g., mech vehicles, transport vehicles). The goal is to get both books to run end-to-end with 100% accurate, game-ready outputs.

This work must be done generically (no book-specific hacks) and proven with real pipeline runs and manual artifact inspection per Definition of Done.

## Goals

- Run full pipeline on **ff-robot-commando** and **ff-freeway-fighter** using their new recipes.
- Identify failure points and data-quality gaps using artifact inspection.
- Fix pipeline issues or extend the engine to support new gameplay mechanics.
- Ensure outputs are fully game-ready with 100% accuracy and validated by the canonical Node/Ajv validator.

## Acceptance Criteria

- [x] Both books complete the pipeline using `driver.py` (or the monitored wrapper) with no fatal errors.
- [x] Artifacts exist in `output/runs/<run_id>/` for all stages, and final `output/` package is produced with `gamebook.json` and validator bundle.
- [x] Manual inspection confirms correct, complete extraction of sections, choices, and gameplay features for both books.
- [x] Any new gameplay concepts (e.g., mech/vehicle systems) are represented in the engine schema and exported correctly.
- [x] Stateful navigation mechanics (e.g., Robot Commando "map reference" / `1XX` placeholder targets) are represented in schema and exported as engine-resolvable state checks.
- [x] Combat styles are defined once in `gamebook.metadata.combatStyles` and combat events reference them with `style` (supports standard, robot, vehicle); style definitions are per-book static (no AI parsing).
- [x] Frontmatter combat rules for **Hand Fighting**, **Shooting**, and **Vehicle Combat** (Freeway Fighter) are manually reviewed and encoded into the combat-style definitions so the engine can execute them without book-specific logic.
- [x] A simple, engine-friendly format for combat styles is documented in this story and validated by manual inspection of `gamebook.json` frontmatter and representative combat sections.
- [x] `validate_ff_engine_node_v1` passes for both books with no unresolved critical errors.
- [x] No regressions introduced to existing FF books (spot-check a known-good title if needed).
- [x] A new early module determines the actual max section number for each book and writes it into `gamebook.json` (and is used to bound downstream validation), avoiding manual per-book `max_section` tweaks.
- [x] Section-range detection uses a hybrid approach: (a) observed section headers, (b) observed references, and (c) a backward scan of OCR pages for final headers; it emits confidence + conflict signals and flags refs beyond confirmed bounds for re-OCR.

## Tasks

- [x] Review the new recipes for both books; confirm inputs and settings.
- [x] Re-run **Robot Commando** and capture failure evidence:
  - Stage/module where failure occurs
  - Artifact paths and sample data showing the problem
  - Pipeline events/log notes
- [x] Run **Freeway Fighter** end-to-end and record any failures or quality gaps.
- [x] Diagnose issues by inspecting upstream artifacts (OCR → elements → boundaries → portions → enrich → export).
- [x] Determine whether fixes belong in pipeline modules, recipe configuration, or engine schema.
- [x] Implement fixes with generic logic and schema updates as needed.
- [x] Extend `state_check` and sequence emission to support placeholder/templated targets (e.g., `1XX`) keyed by a state value learned elsewhere in the book.
- [x] Add a new enrichment module for extracting state values (e.g., map references) and stateful choices, and wire it into recipes.
- [x] Add an orphan-driven re-OCR trigger: if an orphan’s number shape matches a high‑inbound target (e.g., 307 vs 397), flag the source section(s) for image re‑OCR before re‑extracting choices.
- [x] Extend `state_check` to support computed targets (e.g., add 50 to a model number) and emit engine-resolvable templates; add tests and re-run Robot Commando to resolve orphan 53.
- [x] Add per-book static combat-style definitions (Robot Commando: standard+robot; Freeway Fighter: standard+vehicle) and tag combat events with a `style` field.
- [x] Read Freeway Fighter frontmatter (Hand Fighting, Shooting, Vehicle Combat) and map each rule into the combat-style definition format; update the format if needed to represent distinct damage/attack rules.
- [x] Manually inspect `gamebook.json` to confirm each combat section references the correct `style` and that the style definitions match the frontmatter.
- [x] Re-run pipelines to confirm success, validate outputs, and manually inspect 5–10 samples per book.
- [x] Update work log with evidence and impacts for each iteration.

## Work Log

<!-- Append-only log entries. -->

### 20260111-1910 — Freeway Fighter combat styles + shooting-combat support; validator stabilized
- **Result:** Success. Freeway Fighter now emits explicit `hand`/`shooting`/`vehicle` combat styles, captures split-target “no damage” rules, and passes game-ready + Node validation after a low-cost resume rerun.
- **Changes (generic):**
  - Updated combat extraction to:
    - Treat “cannot damage” as `secondary_target_no_damage` (in addition to “cannot wound/harm/hurt”).
    - Merge “During this … Combat …” continuation rules onto the previous section’s combat event (common pattern where stat block is in section N and combat rules are in section N+1).
    - Ensure every combat event has a valid `outcomes.win` (promote from triggers when possible; otherwise `terminal: {kind: continue}`).
  - Updated style assignment to respect an already-set `combat.style` (don’t overwrite).
  - Updated stat-mod extraction to drop **conditional** stat changes rather than emitting incorrect unconditional events.
  - Updated Node validator schema to accept `combat.triggers[].kind = "survive_rounds"`.
  - Updated Freeway Fighter recipe to emit per-book static styles: `hand,shooting,vehicle`.
- **Impact:**
  - **Story-scope impact:** Freeway Fighter frontmatter combat modes are now representable and referenced from combat events (`style`), including Shooting Combat vs Vehicle Combat, aligning with manual frontmatter inspection.
  - **Pipeline-scope impact:** Node validator is stable again (no JSON parse failures), and game-ready validation passes with 0 reachability or choice completeness errors.
  - **Evidence (artifacts inspected):**
    - `output/runs/ff-freeway-fighter/gamebook.json`:
      - `metadata.combatStyles` now includes `hand`, `shooting`, `vehicle`.
      - Section `83` has vehicle combat with `modifiers: [{stat: firepower, amount: -2, scope: combat}]` (matches “reduce your FIREPOWER by 2”).
      - Section `115` includes `mode: split-target` + rules including `secondary_target_no_damage` (matches “you will not damage it”).
      - Section `299` is now `style: shooting` with split-target rules and `outcomes.win.terminal = continue` (combat continues into section 300 narrative/choices).
    - `output/runs/ff-freeway-fighter/42_validate_ff_engine_node_v1/gamebook_validation_node.json` — `valid: true`.
    - `output/runs/ff-freeway-fighter/45_validate_game_ready_v1/game_ready_validation_report.json` — `status: pass`.
- **Next:** Decide how/where to represent conditional penalties like “reduce SKILL permanently by 1 **if you are shot more than once**” (section 300) using existing engine primitives (likely `conditional` event support), without emitting incorrect unconditional stat changes.

### 20260111-1935 — Conditional “shot more than once” penalty modeled as engine conditional event
- **Result:** Success. The “reduce SKILL permanently by 1 if you are shot more than once in the battle” clause is now represented as a schema-valid `conditional` event attached to the combat section sequence (section 299), and the run still passes Node + game-ready validation.
- **Changes:**
  - Extended Node validator schema `Condition` to support a new `combat_metric` condition kind (initially `metric: enemy_round_wins` with numeric operators).
  - Updated `sequence_order_v1` to detect the clause in section N+1 text and inject a `conditional` event immediately after the combat event in section N (only when the combat style is `shooting` and the sections are consecutive).
- **Impact:**
  - **Story-scope impact:** Shooting combat conditional penalties are now engine-representable without incorrectly emitting unconditional stat changes.
  - **Pipeline-scope impact:** No regressions to validation; Node validator remains `valid: true` and game-ready remains `pass`.
  - **Evidence (artifacts inspected):**
    - `output/runs/ff-freeway-fighter/gamebook.json` — section `299` sequence now includes:
      - `combat` (style `shooting`, `win: terminal continue`)
      - `conditional` with `condition: {kind: combat_metric, metric: enemy_round_wins, operator: gte, value: 2}` and `then: [{kind: stat_change, stat: skill, amount: -1, scope: permanent}]`
    - `output/runs/ff-freeway-fighter/42_validate_ff_engine_node_v1/gamebook_validation_node.json` — `valid: true`.
    - `output/runs/ff-freeway-fighter/45_validate_game_ready_v1/game_ready_validation_report.json` — `status: pass`.
- **Next:** Implement engine/runtime support for `combat_metric` evaluation (if not already present), and decide whether additional metrics/operators are needed beyond `enemy_round_wins`.

### 20260111-1950 — Validator/runtime helper: evaluate `combat_metric` conditions
- **Result:** Success. Added a small exported helper to the bundled Node validator package that evaluates `conditional.condition` at runtime, including `combat_metric` (starting with `enemy_round_wins`). Re-validated Freeway Fighter; Node validator still passes and game-ready remains pass.
- **Changes:**
  - `modules/validate/validate_ff_engine_node_v1/validator/validation.js`: added `evaluateCondition(condition, context)` export.
  - `modules/validate/validate_ff_engine_node_v1/validator/validation.d.ts` + `types.d.ts`: documented `CombatMetricCondition` and added `EvaluationContext`.
- **Impact:**
  - **Story-scope impact:** The new `combat_metric` conditional is not just schema-valid; there is now a reference implementation for runtime evaluation shipped alongside the validator.
  - **Pipeline-scope impact:** No changes to validation outcomes; this is additive and safe.
  - **Evidence (artifacts inspected):**
    - `modules/validate/validate_ff_engine_node_v1/validator/validation.js` — `exports.evaluateCondition = evaluateCondition;`
    - `output/runs/ff-freeway-fighter/42_validate_ff_engine_node_v1/gamebook_validation_node.json` — `valid: true` (post-change re-run).
    - `output/runs/ff-freeway-fighter/45_validate_game_ready_v1/game_ready_validation_report.json` — `status: pass` (post-change re-run).
- **Next:** If/when the actual game engine integrates these condition kinds, ensure it passes a `combatMetrics` object after combat resolution (e.g., `{enemy_round_wins: n}`) so `combat_metric` conditions can be evaluated deterministically.

### 20260109-0000 — Story created
- **Result:** Success.
- **Notes:** Story initialized to cover full pipeline bring-up for Robot Commando and Freeway Fighter, including engine extensions for new gameplay mechanics.
- **Next:** Review recipes and re-run Robot Commando to capture failure evidence.

### 20260109-0835 — Investigation: ff-robot-commando failure traced
- **Result:** Partial. Failure cause identified; fix not yet implemented.
- **Evidence:** Pipeline failed at `order_sequence` stage; `output/runs/ff-robot-commando/pipeline_events.jsonl` shows `order_sequence` failed after 0.64s with no output artifact.
- **Root cause:** `sequence_order_v1` crashes when `inventory.items_gained[].quantity` is a string (e.g., `"all"`). In section 259, inventory extraction yields `{"item": "Possessions", "quantity": "all"}` and the sequence builder does `quantity > 1`, raising `TypeError: '>' not supported between instances of 'str' and 'int'`.
- **Artifacts inspected:**
  - `output/runs/ff-robot-commando/13_extract_inventory_v1/portions_with_inventory.jsonl` (section 259 shows `quantity: "all"` for Possessions).
  - `output/runs/ff-robot-commando/22_ending_guard_v1/portions_with_endings.jsonl` (same section propagated).
- **Next:** Update `sequence_order_v1` to handle non-numeric quantities (and/or normalize inventory quantities upstream), then re-run pipeline to verify.

### 20260109-0955 — Implemented Possessions inventory-state extraction (code + tests)
- **Result:** Partial. New inventory-state modeling implemented; pipeline re-run not executed yet.
- **Changes:** Added `inventory_states` to schema, regex/LLM extraction for Possessions loss/restore, sequence event emission (`inventory_state`), and validator schema updates. Added unit tests for Possessions loss/restore language.
- **Next:** Re-run ff-robot-commando from `extract_inventory` (or `order_sequence`) onward and validate outputs + manual artifact inspection.

### 20260109-1545 — Re-run from extract_inventory → order_sequence; Possessions state verified
- **Result:** Success. Pipeline re-run from `extract_inventory` through `order_sequence` with reuse of upstream artifacts; inventory state is correctly represented.
- **Evidence (artifacts inspected):**
  - `output/runs/ff-robot-commando/13_extract_inventory_v1/portions_with_inventory.jsonl`
    - Section 89: `inventory_states=[{action: lose_all, scope: possessions}]`
    - Section 259: `inventory_states=[{action: restore_all, scope: possessions}]` and no `item="Possessions"`
  - `output/runs/ff-robot-commando/23_sequence_order_v1/portions_with_sequence.jsonl`
    - Section 89 sequence includes `inventory_state` before choices
    - Section 259 sequence includes `inventory_state` + Medikit add + choice to 69
- **Next:** Continue from `order_sequence` to full pipeline run and validate `gamebook.json` once choice-completeness issues are resolved.

### 20260109-1730 — Implemented state template extraction + schema support
- **Result:** Partial. New state extraction module, schema updates, and sequence emission added; pipeline run pending.
- **Impact:**
  - **Story-scope impact:** Adds engine-representable state values (`state_set`) and templated state checks (`state_check.key` + `templateTarget`) needed for Robot Commando’s map-reference/`1XX` mechanic.
  - **Pipeline-scope impact:** Enables `sequence_order_v1` to emit state events; no downstream artifact validation yet.
  - **Evidence:** Unit tests pass in `tests/test_extract_state_refs_v1.py` (3 cases covering map reference value, templated turn-to, and conditional map-reference branch).
  - **Next:** Re-run ff-robot-commando from `extract_state_refs` through `order_sequence` and inspect `portions_with_state_refs.jsonl` + `portions_with_sequence.jsonl` for sections 43/122/256/309; success = state_set + state_check events present with correct keys/targets, and Node validator accepts schema.

### 20260109-1910 — Re-run from extract_state_refs; state templating verified in artifacts
- **Result:** Mixed. State templating is captured and exported, but game-ready validation still fails due to reachability/issue reports.
- **Impact:**
  - **Story-scope impact:** Map-reference state values and templated choices are now preserved through sequence and gamebook output.
  - **Pipeline-scope impact:** Node validator passes with new `state_set`/extended `state_check`; reachability still reports orphans and `issues_report` failures (unresolved).
  - **Evidence:**
    - `output/runs/ff-robot-commando/21_extract_state_refs_v1/portions_with_state_refs.jsonl`:
      - Section 256 `state_values=[{key: map_reference_city_of_the_guardians, value: 2X}]`
      - Sections 43/309 `state_checks` with `template_target=1{state}` + choice text “City of the Guardians?”
      - Section 122 `state_checks` with `template_target={state}`, `missing_target=218`
    - `output/runs/ff-robot-commando/24_sequence_order_v1/portions_with_sequence.jsonl`:
      - Section 256 includes `state_set` event before choice to 368
      - Sections 43/309 include `state_check` with `templateTarget=1{state}` + `choiceText`
      - Section 122 includes `state_check` with `templateTarget={state}` + `missing` to 218
    - `output/runs/ff-robot-commando/gamebook.json`: state events preserved in final sequence for sections 43/122/256/309.
  - **Next:** Resolve remaining reachability/issue-report failures (orphans/ordering conflicts) and re-run `validate_game_ready_v1`; success = game_ready passes and artifacts in `output/runs/ff-robot-commando/output/`.

### 20260109-1820 — Re-run from extract_state_refs; orphan count reduced but validation still fails
- **Result:** Mixed. Tests pass; pipeline run completes, but `validate_game_ready_v1` still fails.
- **Impact:**
  - **Story-scope impact:** Confirms state-template extraction changes are stable (tests + full run) and reduces reachability orphans (10 → 5).
  - **Pipeline-scope impact:** `validate_holistic_reachability_v1` now reports 5 orphans; `report_pipeline_issues_v1` still flags 7 orphans plus boundary conflicts (ordering + duplicate headers), so game-ready validation remains failing.
  - **Evidence:**
    - `tests/test_extract_state_refs_v1.py` — 7/7 passing.
    - `output/runs/ff-robot-commando/22_validate_holistic_reachability_v1/reachability_report.json` — orphans: `22, 53, 305, 307, 338`.
    - `output/runs/ff-robot-commando/25_report_pipeline_issues_v1/issues_report.jsonl` — orphans: `22, 53, 100, 140, 305, 307, 338`, plus `ordering_conflicts` + `duplicate_headers`.
  - **Next:** Inspect inbound references for the remaining orphan sections (22/53/100/140/305/307/338) and resolve boundary conflicts for sections 15/159; success = orphans cleared and `validate_game_ready_v1` passes.

### 20260109-1915 — report_pipeline_issues now respects reachability (state-aware)
- **Result:** Partial. `issues_report` orphans reduced to match reachability; game-ready still fails due to remaining orphans + boundary conflicts.
- **Impact:**
  - **Story-scope impact:** Removes false orphan flags caused by templated state checks (e.g., potion letter-count paths).
  - **Pipeline-scope impact:** `report_pipeline_issues_v1` now loads the latest reachability report regardless of stage ordinal; orphans dropped from 7 → 5.
  - **Evidence:**
    - `modules/adapter/report_pipeline_issues_v1/main.py` — reachability report discovery now scans for `validate_holistic_reachability_v1`.
    - `output/runs/ff-robot-commando/25_report_pipeline_issues_v1/issues_report.jsonl` — orphans now `22, 53, 305, 307, 338` (100/140 removed).
    - `output/runs/ff-robot-commando/22_validate_holistic_reachability_v1/reachability_report.json` — orphans list matches.
  - **Next:** Trace remaining orphans (22/53/305/307/338) to locate missing inbound references or non-standard mechanics, then fix via OCR re-read or extraction rules.

### 20260109-1940 — Orphan trace: 22/53/305/307/338
- **Result:** Partial. Located one orphan’s missing inbound reference; others show no inbound links in OCR.
- **Impact:**
  - **Story-scope impact:** Identified boundary conflict as the root cause for orphan 338; remaining orphans appear to be missing inbound references in OCR (likely non-standard mechanics or OCR misses).
  - **Pipeline-scope impact:** Confirms reachability logic is correct; remaining orphans require upstream boundary/OCR fixes or extraction enhancements.
  - **Evidence:**
    - `output/runs/ff-robot-commando/03_ocr_ai_gpt51_v1/pages_html.jsonl`:
      - Section 159 on page 54 includes `Turn to 338` (valid inbound link in OCR).
      - Section 53 (page 28) has no inbound `Turn to 53` in OCR.
      - Sections 305/307 appear on page 88 with no inbound `Turn to 305/307` in OCR.
      - Section 22 (page 21) appears only as a section; no inbound `Turn to 22` in OCR.
    - `output/runs/ff-robot-commando/11_portionize_html_extract_v1/portions_enriched.jsonl`:
      - Section 159 text is wrong (Tripod fight) due to duplicate header/ordering conflict; link to 338 is missing in extracted portion.
  - **Next:** Fix boundary conflicts for section 159 to restore the 338 link; then locate true inbound references for 22/53/305/307 (targeted OCR or extraction updates).

### 20260109-2010 — Boundary repair stabilized; node validator unblocked
- **Result:** Mixed. Boundary repair now resolves missing/duplicate headers; node validator passes after filtering impossible combat outcomes. Orphans remain (4).
- **Impact:**
  - **Story-scope impact:** Restored section 169 header, removed stale ordering/duplicate header errors, and fixed invalid combat escape outcomes that broke Node validation.
  - **Pipeline-scope impact:** `detect_boundaries_html_loop_v1` now yields full coverage (401/400), no ordering conflicts or duplicate headers; `validate_ff_engine_node_v1` passes. `issues_report` now flags only 4 orphans.
  - **Evidence:**
    - `output/runs/ff-robot-commando/08_detect_boundaries_html_loop_v1/pages_html_repaired.jsonl` — page 57R now has `h2 169` with Tripod fight.
    - `output/runs/ff-robot-commando/10_detect_boundaries_html_v1/section_boundaries.jsonl` — 401 boundaries, no duplicate_headers report.
    - `output/runs/ff-robot-commando/31_validate_ff_engine_node_v1/gamebook_validation_node.json` — valid gamebook.
    - `output/runs/ff-robot-commando/25_report_pipeline_issues_v1/issues_report.jsonl` — orphans only `22, 53, 305, 307`.
- **Next:** Resolve remaining orphans (22/53/305/307) by locating missing inbound references (likely OCR misses or non-standard mechanics) and re-run from `extract_choices`.

### 20260110-1045 — Hardcoded combat styles via per-book recipes; Robot Commando re-run
- **Result:** Success. Static combat style definitions now drive assignment and metadata; Robot Commando run passes with correct style tagging.
- **Impact:**
  - **Story-scope impact:** Implements the per-book hardcoded combat-style requirement (Robot Commando uses standard+robot) and removes reliance on frontmatter parsing for style IDs.
  - **Pipeline-scope impact:** Combat style metadata is stable and deterministic; styles are correctly assigned in sections (robot vs standard) and exported in `gamebook.json`.
  - **Evidence:**
    - `output/runs/ff-robot-commando/12_extract_combat_styles_frontmatter_v1/combat_styles.json` — styles: `standard`, `robot`; debug source `static`.
    - `output/runs/ff-robot-commando/gamebook.json` — `metadata.combatStyles` contains `standard` + `robot`.
    - `output/runs/ff-robot-commando/gamebook.json` — section `16` combat style `robot`, section `142` combat style `standard`.
  - **Next:** Apply the per-book recipe to Freeway Fighter (standard+vehicle), re-run from `extract_combat_styles_frontmatter`, and manually inspect combat styles in `gamebook.json`; success is falsified if vehicle combats are tagged as `standard` or metadata lacks `vehicle`.

### 20260110-1145 — Freeway Fighter re-run from OCR; combat styles validated
- **Result:** Partial. Combat styles are correct (standard+vehicle), but the pipeline still fails due to missing sections/reachability.
- **Impact:**
  - **Story-scope impact:** Confirms the per-book static style definition works for Freeway Fighter (vehicle combat is detected and tagged).
  - **Pipeline-scope impact:** `combatStyles` metadata is deterministic and section-level combat events are correctly styled; however, `validate_reachability` and Node validator fail due to missing sections and broken links.
  - **Evidence:**
    - `output/runs/ff-freeway-fighter/12_extract_combat_styles_frontmatter_v1/combat_styles.json` — styles: `standard`, `vehicle`; debug source `static`.
    - `output/runs/ff-freeway-fighter/gamebook.json` — `metadata.combatStyles` includes `standard` + `vehicle`.
    - `output/runs/ff-freeway-fighter/gamebook.json` — section `17` combat style `vehicle` (enemy has `firepower`/`armour`), section `6` combat style `standard` (enemy has `skill`/`stamina`).
  - **Next:** Investigate the 16 missing sections + reachability failures in Freeway Fighter before attempting game-ready validation; success is falsified if missing sections remain or reachability stays invalid.

### 20260110-1315 — Robot Commando combat outcomes fix (ARMOUR→lose) + re-run
- **Result:** Success. Combat outcomes now include loss paths when text says ARMOUR is reduced to zero; Node validator passes.
- **Impact:**
  - **Story-scope impact:** Fixes Robot Commando combat schema failure caused by conditional outcomes; combat events now always include valid win/lose targets.
  - **Pipeline-scope impact:** `validate_ff_engine_node_v1` and `validate_game_ready_v1` pass after re-running from `extract_combat`; combat outcome extraction is more robust for robot/vehicle fights.
  - **Evidence:**
    - `tests/test_extract_combat_outcomes_fallback.py` — new tests for armour-to-zero loss detection and conditional coercion.
    - `output/runs/ff-robot-commando/gamebook.json` — section `156` combat outcomes include win `354` and lose `6`.
    - `output/runs/ff-robot-commando/40_validate_ff_engine_node_v1/gamebook_validation_node.json` — valid gamebook.
  - **Next:** Begin Freeway Fighter missing-section investigation; success is falsified if missing sections persist or reachability stays invalid after fixes.

### 20260110-1500 — Detect section range module + Freeway Fighter retest
- **Result:** Partial. New early module writes section count into `gamebook.json` and reachability missing sections drop to 0, but Node validation still fails on combat outcomes in section 295.
- **Impact:**
  - **Story-scope impact:** Adds automatic max‑section detection to avoid manual per‑book `max_section` tweaks; metadata now reflects detected section range.
  - **Pipeline-scope impact:** `validate_holistic_reachability_v1` no longer flags missing 385–400 for Freeway Fighter; broken links remain, and Node validator still fails on a combat schema issue.
  - **Evidence:**
    - `output/runs/ff-freeway-fighter/12_detect_section_range_v1/section_range.json` — `max_section: 384`.
    - `output/runs/ff-freeway-fighter/gamebook.json` — `metadata.sectionCount: 384`.
    - `output/runs/ff-freeway-fighter/32_validate_holistic_reachability_v1/reachability_report.json` — `missing_sections: []`.
- **Next:** Fix Freeway Fighter combat outcome schema issue in section 295 and investigate orphans 382/383; success is falsified if Node validator still fails or orphans persist.

### 20260111-0025 — Freeway Fighter validate_game_ready pass + manual combat style inspection
- **Result:** Success. Freeway Fighter now passes `validate_game_ready_v1` with section count bounded to 380; manual spot-check confirms vehicle vs standard combat styles are correctly tagged in gameplay sections.
- **Impact:**
  - **Story-scope impact:** Confirms Freeway Fighter can reach game-ready status with the new section-count bounding and combat-style tagging.
  - **Pipeline-scope impact:** `validate_game_ready_v1` now passes while still surfacing duplicate-header warnings in `issues_report` without blocking release.
  - **Evidence:**
    - `output/runs/ff-freeway-fighter/44_validate_game_ready_v1/game_ready_validation_report.json` — status `pass`.
    - `output/runs/ff-freeway-fighter/gamebook.json` — `metadata.combatStyles` includes `standard` + `vehicle`.
    - `output/runs/ff-freeway-fighter/gamebook.json` — section `6` uses `style: standard` (biker shootout), section `17` uses `style: vehicle` (motor cycle FIREPOWER/ARMOUR), section `63` uses `style: vehicle` (YELLOW FORD), section `299` uses `style: standard` (biker shootout).
  - **Next:** Finish orphan/missing-section cleanup in Freeway Fighter (`issues_report` still flags duplicate headers 300/380) and confirm Robot Commando final validation status; success is falsified if a full Freeway Fighter run regresses or if duplicate headers break choice extraction downstream.

### 20260111-0630 — Duplicate header mitigation + combat outcome fix; Freeway Fighter + Robot Commando verified
- **Result:** Success. Duplicate headers reduced from 2 → 1 (section 300 resolved), combat outcomes now capture “survive X attack rounds” phrasing, and Freeway Fighter re-run passes game-ready validation. Robot Commando remains game-ready with state-templated map reference choices intact.
- **Impact:**
  - **Story-scope impact:** Freeway Fighter pipeline is stable after the duplicate-header fix and combat outcome enhancement; Robot Commando state template mechanics confirmed in final output.
  - **Pipeline-scope impact:** `detect_boundaries_html_v1` now ignores repeated same-number headers on a single page; `extract_combat_v1` reliably captures “survive X attack rounds … turn to N,” preventing missing combat outcomes that break Node validation.
  - **Evidence:**
    - `output/runs/ff-freeway-fighter/10_detect_boundaries_html_v1/duplicate_headers.json` — only section `380` remains duplicated (section `300` resolved).
    - `output/runs/ff-freeway-fighter/gamebook.json` — section `158` combat now includes `outcomes.win.targetSection = "67"` (survive three Attack Rounds).
    - `output/runs/ff-freeway-fighter/44_validate_game_ready_v1/game_ready_validation_report.json` — status `pass`.
    - `output/runs/ff-robot-commando/gamebook.json` — section `256` sets `map_reference_city_of_the_guardians=22`, sections `43/309` use `templateTarget=1{state}`.
  - **Next:** Decide how to handle the remaining duplicate header for section `380` (likely scan duplication). Success is falsified if the duplicate header causes choice or boundary inconsistencies downstream.

### 20260111-0710 — Early duplicate-page detection module added + FF manual verification
- **Result:** Success. Added a generic early duplicate-page detector and verified Freeway Fighter’s duplicate section 380 pages are near-identical and now caught before section parsing.
- **Impact:**
  - **Story-scope impact:** Removes duplicated pages from the pipeline early, preventing duplicate headers and double-processing downstream.
  - **Pipeline-scope impact:** New early-stage dedupe report identifies duplicate pages with similarity evidence; duplicate header warnings can be avoided without per-book patches.
  - **Evidence:**
    - `output/runs/ff-freeway-fighter/06_detect_duplicate_pages_v1/duplicate_pages.json` — duplicate detected: page 206 → page 204, similarity `0.8864`, `header_overlap: true`.
    - `output/runs/ff-freeway-fighter/02_split_pages_from_manifest_v1/images/page-103L.png` and `.../page-104L.png` — both show section `380` with the same victory text (scan duplication).
    - `output/runs/ff-freeway-fighter/06_detect_duplicate_pages_v1/pages_html_deduped.jsonl` — total pages reduced (207 → 205).
  - **Next:** Re-run Freeway Fighter from `detect_duplicate_pages` through `detect_boundaries_html` to confirm duplicate header `380` is eliminated in boundary detection; success is falsified if duplicate headers remain without a clear scan-duplicate signal.

### 20260109-2135 — Orphan text dump + manual trace via global search
- **Result:** Mixed. Extracted orphan section texts and searched the full gamebook text for clues. Two orphans are now attributable to OCR misreads; two remain unresolved.
- **Impact:**
  - **Story-scope impact:** Confirms `22` and `307` are reachable via state/mechanics but are broken by OCR errors; `53` and `305` have no inbound links in OCR and require targeted inspection or re-OCR to recover the missing “Turn to …” lines.
  - **Pipeline-scope impact:** narrows fixes to OCR/choice extraction for specific upstream pages instead of reachability logic.
  - **Evidence:** `output/runs/ff-robot-commando/11_portionize_html_extract_v1/portions_enriched.jsonl` (raw_html for orphans); global keyword search over the same artifact.
  - **Next:** Targeted manual scan of the specific source pages for the missing inbound references (the pages that should contain “Turn to 53” and “Turn to 305”), then decide whether to re-OCR or add a targeted recovery rule.

#### Orphan 22 — Text
“You use the code-words you found with the map reference. ‘Acceptable,’ crackles the voice of the guardian computer. ‘Entering at Clearance Level Zero.’ Turn to 175.”

**Reasoning + search results**
- Keyword search finds “map reference” only in sections 22, 122, and 256.
  - Section 122: “If you have read a military volume on the City of the Guardians, turn to the map reference you were given there. If you have not read this volume, turn to 218.”
  - Section 256: “The map reference is 2X. Make a note of this number. Substitute it for ‘XX’ when you are given the option to visit the City of the Guardians.”
- Manual scan of the printed page shows the map reference is **22**, not “2X”.
- Conclusion: Orphan 22 is caused by an OCR misread in section 256 (22 → 2X). With the correct map reference, 122 should reach 22 via state-based templating.

#### Orphan 53 — Text
“In a closet, you find what appears to be an unused coat-hanger… You have found the Cloak of Invisibility… Return to 85.”

**Reasoning + search results**
- “closet” appears only in sections 53, 114, 259 (the latter two are the Possessions recovery paths).
- “Cloak of Invisibility” appears in sections 29, 32, 53, 71, 90, 106, 112, 164, 190, 192, 201, 215, 358.
- There is no “Turn to 53” in OCR anywhere (`pages_html.jsonl` has no `Turn to 53`).
- Conclusion: inbound link to 53 is missing from OCR; likely a “look in the closet/coat-hanger” choice in a hospital/museum subsection. Needs targeted page inspection to locate the missing “Turn to 53”.

#### Orphan 305 — Text
“Over the radio, the Karossean challenges you: ‘Eighty-eight!’ If you know the proper countersign… If not, turn to 26.”

**Reasoning + search results**
- “countersign” appears in sections 7, 88, 187, 236, 305.
- “Eighty-eight” appears in multiple sections but no “Turn to 305” appears anywhere in OCR.
- Section 197 routes to 236 if you don’t remember the number-based password; 236 is a similar radio challenge.
- Conclusion: 305 is a parallel challenge branch whose inbound “Turn to 305” line is missing from OCR. Needs targeted page inspection or re-OCR on the page that should link to 305.

#### Orphan 307 — Text
“The lift shoots quickly upward… You are in the lobby of the Robot Experimental Centre. If you cross the square and re-enter your robot, turn to 206. If you investigate the Robot Experimental Centre, turn to 25.”

**Reasoning + search results**
- Manual scan shows section 398 says: “If you want to get in the lift and press the button, turn to 307.”
- OCR for section 398 instead says “turn to 397” and “turn to 178.”
- Conclusion: Orphan 307 is caused by OCR misreading section 398’s target. Fixing OCR/choice extraction for 398 should restore the inbound link.

### 20260109-2210 — Implemented orphan→shape re-OCR candidate selection
- **Result:** Partial. Added a new adapter module that flags likely source sections for re-OCR when orphans match near-number targets with high inbound counts.
- **Impact:**
  - **Story-scope impact:** Introduces the requested “orphan + number-shape similarity → re‑OCR” signal so we can prioritize pages like the 307↔397 mismatch.
  - **Pipeline-scope impact:** Produces `repair_hints` with `orphan_similar_target` for downstream re‑OCR; not yet wired into the main recipe.
  - **Evidence:**
    - `modules/adapter/orphan_reocr_candidates_v1/main.py` (new module).
    - `tests/test_orphan_reocr_candidates_v1.py` (unit tests for 307↔397).
  - **Next:** Wire this module into the pipeline (before `repair_portions_v1`) and re-run from that stage to confirm the 307↔397 fix on Robot Commando.

### 20260110-0115 — Orphan re-OCR run on Robot Commando (wire-in test)
- **Result:** Mixed. The re-OCR candidate stage flagged 26 sections and repair reran, but section 398 still reads “turn to 397” after re-OCR; orphan list unchanged.
- **Impact:**
  - **Story-scope impact:** The new orphan→shape re-OCR path executes end-to-end, but it did not resolve the 307↔397 error in Robot Commando.
  - **Pipeline-scope impact:** `repair_portions_v1` now runs only on orphan-shape candidates (require_hints); no change to orphan counts.
  - **Evidence:**
    - `output/runs/ff-robot-commando/22_repair_portions_v1/portions_orphan_repaired.jsonl` — section 398 clean_text still “turn to 397”.
    - `output/runs/ff-robot-commando/02_split_pages_from_manifest_v1/images/page-108R.png` — manual inspection shows “turn to 307”.
    - `output/runs/ff-robot-commando/32_report_pipeline_issues_v1/issues_report.jsonl` — orphans remain (includes 307).
  - **Next:** Tighten re‑OCR for orphan‑shape cases: if a repaired section still contains the suspect target, force a boosted reread (or use a stronger model) for those sections.

### 20260110-0205 — gpt-5.2 strict reread fixes 307/397 but game-ready still fails
- **Result:** Partial. gpt-5.2 strict reread corrected section 398 to “turn to 307”, and choice completeness now passes, but game-ready still fails due to reachability orphans (22, 53).
- **Impact:**
  - **Story-scope impact:** The orphan‑shape fix works on the targeted 307/397 case (critical path for Robot Commando).
  - **Pipeline-scope impact:** Choice completeness now passes; remaining failure is reachability/issue-report orphans (22, 53).
  - **Evidence:**
    - `output/runs/ff-robot-commando/22_repair_portions_v1/portions_orphan_repaired.jsonl` — section 398 clean_text now “turn to 307”; raw_html anchor also 307.
    - `output/runs/ff-robot-commando/gamebook.json` — section 398 `turn_to_links` now `[178, 307]` and presentation_html shows 307.
    - `output/runs/ff-robot-commando/41_validate_game_ready_v1/game_ready_validation_report.json` — reachability orphans `22, 53`.
  - **Next:** Resolve orphans 22 and 53 (map reference still misread, missing inbound for Cloak of Invisibility) and rerun from `extract_state_refs` or `repair_choices`.

### 20260110-0905 — Manual inspection: map reference resolved; orphan 53 is computed link (model+50)
- **Result:** Partial. The map reference for City of the Guardians now resolves to 22 (not 2X), and orphan 22 disappears. Orphan 53 remains because its inbound is **computed**, not a literal “Turn to 53.”
- **Impact:**
  - **Story-scope impact:** Confirms the map-reference escalation is working and isolates the remaining failure to a computed-link mechanic (model number + 50).
  - **Pipeline-scope impact:** Reachability now flags only section 53 as orphan; any fix must model computed targets rather than OCR correction.
  - **Evidence:**
    - `output/runs/ff-robot-commando/28_extract_state_refs_v1/portions_with_state_refs.jsonl` — section 256 has `state_values` with `map_reference_city_of_the_guardians=22` (source text “map reference is 2X”).
    - `output/runs/ff-robot-commando/29_validate_holistic_reachability_v1/reachability_report.json` — orphans list is now `['53']`.
    - `output/runs/ff-robot-commando/28_extract_state_refs_v1/portions_with_state_refs.jsonl` — section 112 plaque reveals “Cloak of Invisibility … Model 3” (implies 53 via model+50).
    - `output/runs/ff-robot-commando/28_extract_state_refs_v1/portions_with_state_refs.jsonl` — section 17 instructs “add 50 to its model number and turn to that paragraph,” which yields 53.
  - **Next:** Define a generic “computed target” mechanism (state-based target templating) so section 17 can resolve to 50+model_number and produce an explicit turn_to for reachability/engine use.

### 20260110-1015 — Computed state targets implemented; Robot Commando passes game-ready
- **Result:** Success. Added computed state target support (model number + offset), reran from `extract_state_refs`, and Robot Commando now passes reachability and game-ready validation.
- **Impact:**
  - **Story-scope impact:** Resolves the last orphan (53) by modeling the “add 50 to its model number” mechanic as a state check with computed target.
  - **Pipeline-scope impact:** Reachability now reports 0 orphans; game-ready validation passes without patches.
  - **Evidence:**
    - `output/runs/ff-robot-commando/28_extract_state_refs_v1/portions_with_state_refs.jsonl` — section 17 has `state_checks` with `template_op=add`, `template_value=50`; section 112 sets `model_number=3`.
    - `output/runs/ff-robot-commando/29_validate_holistic_reachability_v1/reachability_report.json` — `orphans=[]`.
    - `output/runs/ff-robot-commando/gamebook.json` — section 17 sequence includes `state_check` with `templateOp=add`, `templateValue=50`.
  - **Next:** Validate Freeway Fighter end-to-end and inspect for any new mechanics requiring engine support.

### Combat Style Definition (Proposed Format)

Store a small combat rules dictionary in `gamebook.metadata.combatStyles` and reference it from combat events via `style`:

```json
{
  "metadata": {
    "combatStyles": {
      "standard": {
        "id": "standard",
        "name": "Standard Combat",
        "attackStrength": {"attacker": "2d6 + SKILL", "defender": "2d6 + ENEMY_SKILL"},
        "damage": {"stat": "stamina", "amount": 2},
        "endCondition": {"stat": "stamina", "threshold": 0}
      },
      "vehicle": {
        "id": "vehicle",
        "name": "Vehicle Combat",
        "attackStrength": {"attacker": "2d6 + FIREPOWER", "defender": "2d6 + ENEMY_FIREPOWER"},
        "damage": {"stat": "armour", "amount": "1d6"},
        "endCondition": {"stat": "armour", "threshold": 0},
        "special": ["Rocket launch: auto-hit, target destroyed."]
      }
    }
  },
  "sections": {
    "23": {
      "sequence": [
        {"kind": "combat", "style": "vehicle", "enemies": [{"enemy": "Bandit Car", "firepower": 8, "armour": 10}]}
      ]
    }
  }
}
```
### 2026-01-10
- Fixed choice extraction to prevent repaired text from overriding explicit HTML anchor targets when they are near-variants, addressing false choice rewrites (e.g., 108→106, 290→29).
- Re-ran Robot Commando pipeline from `extract_choices` with downstream invalidation; run completed and game-ready validation passed.
- **Impact:**
  - **Story-scope impact:** Unblocked Robot Commando pipeline completion with accurate choice targets for affected sections.
  - **Pipeline-scope impact:** Eliminated false choice mutations introduced by orphan re-OCR repairs; choice completeness now passes.
  - **Evidence:** `output/runs/ff-robot-commando/39_validate_choice_completeness_v1/choice_completeness_report.json` shows `flagged_count: 0`; `output/runs/ff-robot-commando/gamebook.json` section `153` has targets `108/290/311` and section `325` targets `290`; `output/runs/ff-robot-commando/41_validate_game_ready_v1/game_ready_validation_report.json` reports pass.
  - **Next:** Inspect `output/runs/ff-robot-commando/gamebook.json` samples for gameplay feature fidelity and then start Freeway Fighter pipeline; success is falsified if choice completeness flags reappear or engine validator fails.

### 2026-01-10 — Early section range detection uses backscan/ref signals
- **Result:** Partial. `detect_section_range_v1` now prefers backscan/ref signals over inflated headers, and Freeway Fighter’s `metadata.sectionCount` is correctly set to 380. The pipeline still fails later (combat/sequence validation), so the book is not yet playable.
- **Impact:**
  - **Story-scope impact:** Achieves the new requirement to auto-detect the true max section count early and write it into `gamebook.json`.
  - **Pipeline-scope impact:** Prevents false “missing sections 381–400” by grounding `sectionCount` to the backscanned max; also emits `headers_exceed_backscan` flag for diagnostics.
  - **Evidence:**
    - `output/runs/ff-freeway-fighter/12_detect_section_range_v1/section_range.json` — `max_section: 380`, `backscan_max_section: 380`, `flags: ["headers_exceed_backscan"]`.
    - `output/runs/ff-freeway-fighter/gamebook.json` — `metadata.sectionCount` is `380`.
    - `output/runs/ff-freeway-fighter/32_validate_holistic_reachability_v1/reachability_report.json` — `missing: 0` (section range no longer inflates missing count).
  - **Next:** Fix combat extraction/schema errors (e.g., sections 63/295/299) and re-run from `extract_combat` so Node validator passes; success is falsified if `validate_ff_engine_node_v1` still fails or new missing-section warnings appear.

### 2026-01-11 — Skip repair on blank OCR pages to stop hallucinated sections
- Implemented a blank-page guard in `detect_boundaries_html_loop_v1` (image brightness + low-variance heuristic) so OCR-empty pages are never repaired or used for section detection.
- Re-ran Freeway Fighter from `html_repair_loop` through `validate_game_ready`; section boundaries now stop at 380 with no ghost 381.
- **Impact:**
  - **Story-scope impact:** Removes the hallucinated section that created a phantom orphan and duplicate header, unblocking accurate section counts.
  - **Pipeline-scope impact:** Eliminated false section headers originating from blank right-hand pages; reachability now has 0 orphans with 380 detected sections.
  - **Evidence:**
    - `output/runs/ff-freeway-fighter/09_detect_boundaries_html_loop_v1/pages_html_repaired.jsonl` — page 205 has empty `html`/`raw_html` (no fabricated section).
    - `output/runs/ff-freeway-fighter/11_detect_boundaries_html_v1/section_boundaries.jsonl` — no section 381 present; total 380 boundaries.
    - `output/runs/ff-freeway-fighter/23_trace_orphans_text_v1/orphan_trace_report.json` — `orphans: 0`.
  - **Next:** Reconcile the “missing 20” counters from `html_repair_loop` with `detect_section_range_v1` so the missing-section metric aligns with the real 380 max; success is falsified if `report_pipeline_issues_v1` still flags missing 381–400.

### 2026-01-11 — Cap missing-section issues using detected section range
- `report_pipeline_issues_v1` now loads `detect_section_range_v1/section_range.json` and filters missing-section issues beyond `max_section`.
- Re-ran from `report_pipeline_issues` to `validate_game_ready`; missing count is now 0 in the issue report while the book still has 380 sections.
- **Impact:**
  - **Story-scope impact:** Missing-section reporting now aligns with the detected max section count (380) for Freeway Fighter, removing false “missing 381–400” flags.
  - **Pipeline-scope impact:** Issue summaries no longer inflate missing counts when books end early; reduces false alarms for partial‑length FF books.
  - **Evidence:**
    - `output/runs/ff-freeway-fighter/12_detect_section_range_v1/section_range.json` — `max_section: 380`.
    - `output/runs/ff-freeway-fighter/36_report_pipeline_issues_v1/issues_report.jsonl` — `missing_section_count: 0`.
    - `output/runs/ff-freeway-fighter/37_build_ff_engine_with_issues_v1/gamebook_raw.json` — `sections` length 380.
  - **Next:** Confirm Freeway Fighter frontmatter combat styles and in-section combat assignments are correct with manual inspection of `gamebook.json`; success is falsified if any combat events lack the correct style or required stats.

### 2026-01-11 — Manual combat-style inspection (Freeway Fighter)
- Manually inspected frontmatter combat rules (images pages 9R–11L) and sampled gameplay sections with combat text.
- **Findings:**
  - Frontmatter defines three combat types: Hand Fighting, Shooting, and Vehicle Combat. Vehicle rules match current `combatStyles.vehicle` (2d6 + FIREPOWER vs enemy, damage 1d6 ARMOUR, rocket auto-hit).
  - Shooting combat specifies damage as 1d6 STAMINA, but current `combatStyles.standard` uses fixed 2 STAMINA; this is a mismatch for all “Shooting Combat” sections.
  - Section 83 text says “reduce your FIREPOWER by 2” but the sequence encodes a `stat_change` on SKILL (wrong stat).
  - Section 300 contains explicit “Shooting Combat” text but no combat event was extracted (sequence has only narrative + choices), indicating an extraction miss.
  - Some vehicle combat sections (e.g., 63, 115) have special rules (“survive four Attack Rounds”, split-target with no-damage rules) that are not fully represented in the current combat model.
- **Evidence:**
  - `output/runs/ff-freeway-fighter/02_split_pages_from_manifest_v1/images/page-009R.png` — Hand Fighting rules start.
  - `output/runs/ff-freeway-fighter/02_split_pages_from_manifest_v1/images/page-010R.png` — Vehicle Combat rules start.
  - `output/runs/ff-freeway-fighter/gamebook.json` — section 83 encodes `stat_change` SKILL -2 despite text saying FIREPOWER; section 300 has “Shooting Combat” text but no combat event.
  - `output/runs/ff-freeway-fighter/gamebook.json` — `metadata.combatStyles.standard` uses fixed 2 STAMINA damage (does not match shooting rules).
  - `output/runs/ff-freeway-fighter/gamebook.json` — section 63 text references “survive four Attack Rounds” but combat outcome is only `win -> 334`.
  - `output/runs/ff-freeway-fighter/gamebook.json` — section 115 vehicle combat has split‑target rules but only `mode: split-target` encoded.
  - **Next:** Extend combat model to represent Shooting vs Hand Fighting and encode special vehicle rules (survive‑rounds, split‑target no‑damage), then re‑extract combat and re‑validate. Success is falsified if any “Shooting Combat” sections still use fixed damage or missing combat events.

### 2026-01-11 — Manual sampling + export hardening for choice item effects
- **Result:** Success. Manual sampling confirmed combat-metric conditional modeling in Freeway Fighter and uncovered (then fixed) a real Robot Commando export bug where “collect them all and escape…” produced bogus `choice.effects` items.
- **Fix (generic):** Tightened choice-item name validation so pronoun/quantifier/non-item phrases are rejected:
  - `modules/export/build_ff_engine_v1/main.py`
  - `modules/export/build_ff_engine_with_issues_v1/main.py`
- **Evidence (artifacts inspected):**
  - Freeway Fighter:
    - `output/runs/ff-freeway-fighter/gamebook.json` section `83` — `combat.style: "vehicle"` with `modifiers: [{stat: "firepower", amount: -2, scope: "combat"}]`.
    - `output/runs/ff-freeway-fighter/gamebook.json` section `299` — emits `conditional` with `condition.kind: "combat_metric"` and `metric: "enemy_round_wins"`, `operator: "gte"`, `value: 2`.
  - Robot Commando:
    - `output/runs/ff-robot-commando/gamebook.json` section `259` — now clean (no bogus `choice.effects`): `item(add,"Medikit")`, `inventory_state(restore_all,"possessions")`, `choice(targetSection:"69")`.
    - Packaging matches:
      - `output/runs/ff-robot-commando/output/gamebook.json` is byte-identical to `output/runs/ff-robot-commando/gamebook.json`
    - Node validator ran:
      - `output/runs/ff-robot-commando/40_validate_ff_engine_node_v1/gamebook_validation_node.json`

### 2026-01-11 — Regression spot-check (Robot Commando) after validator/runtime changes
- **Result:** Success. Re-ran the current bundled Node/Ajv validator against Robot Commando; it still validates cleanly (`valid: true`, exit code 0).
- **Evidence:**
  - `output/runs/ff-robot-commando/zz_regression_node_validator_report.json` — `valid: true`, `_exit_code: 0`
  - Packaged output still matches root:
    - `output/runs/ff-robot-commando/output/gamebook.json` is byte-identical to `output/runs/ff-robot-commando/gamebook.json`

### 2026-01-11 — Mark story done (user sign-off)
- Marked story as **Done** after:
  - Successful end-to-end runs for both books with packaged outputs present.
  - Manual spot-check sampling recorded in this work log.
  - Regression spot-check performed using **Robot Commando** as the target per user direction.
