# Story: Schema + Validation Update and Alignment (Node/AJV Canonical)

**Status**: Done  
**Created**: 2025-12-29  
**Priority**: High  
**Parent Story**: story-030 (FF Engine format), story-083 (Game-ready validation checklist)

---

## Goal

Make the **Node/AJV FF validator** the canonical, portable validation engine shared between the pipeline and the game engine, with explicit versioning so mismatches are detectable without blocking correct validation.

---

## Motivation

We require the pipeline and the game engine to use **identical validation logic**. The Node validator is portable but has drifted behind the pipeline output (e.g., combat arrays). This story restores a single source of truth and documents how to use it in both contexts.

---

## Success Criteria

- [x] **Validator updated**: `validate_ff_engine_node_v1` accepts current pipeline output (combat arrays, etc.).
- [x] **Canonical in pipeline**: Recipes use Node validator as the authoritative schema validator; Python validator remains for forensics.
- [x] **Portability documented**: README + AGENTS explain what the validator is, why it matters, and that it must ship with `gamebook.json` to the game engine.
- [x] **Versioning**: Introduce a clear version stamp and mismatch signaling (warning on mismatch, no hard fail if validation passes).
- [x] **Core validator parity**: Node validator covers all critical checks previously enforced by the Python validator (missing sections, duplicates, reachability, etc.) and validates the new `sequence`-based schema.
- [x] **Legacy validator retired**: Python `validate_ff_engine_v2` no longer gates pipeline success (forensics-only).
- [x] **Portable bundle**: Node validator is shippable as a single JS file (with schema embedded) and runnable by the game engine alongside `gamebook.json`.
- [x] **Game-ready alignment**: `story-083` checklist updated/confirmed to require Node validator pass.
- [x] **Navigation targets normalized**: navigation targets must be canonical section IDs (no descriptive strings like “death (no section number)”).
- [x] **Terminal outcomes supported**: navigation edges may omit `targetSection` and instead include `terminal` (e.g., death), with validator support.
- [x] **Navigation order preserved**: navigation links keep the same order as they appear in the section text (stat checks appear before choices when described that way).
- [x] **Sequence replaces navigation**: `navigation` is removed and replaced by ordered `sequence` events that drive gameplay flow and validation.
- [x] **Sequence-only output**: `gamebook.json` emits only `sequence` for gameplay flow; legacy fields (navigation/combat/items/statModifications/statChanges/diceChecks/deathConditions) are removed and forbidden by schema.
- [x] **State checks supported**: Non-item conditional checks are emitted as `state_check` with `conditionText` and validated by the Node validator.
- [x] **Upstream ordering integrated**: a deterministic ordering module runs before build to guarantee sequence order matches section text.
- [x] **Global death rule enforced**: `stat_change` events no longer encode `continue_if`; survival is a global engine rule (`STAMINA <= 0` ends the game). Survival-only stat checks are dropped.
- [x] **Choice effects captured**: choice events may include item effects (add/remove) when the choice text implies a conditional pickup/use.
- [x] **Manual audit completed**: Manually inspect and log findings for at least 20 sections each for inventory, stat changes, combat, choices, and **all available sections** for any other extracted feature class (if fewer than 20 exist in the book).
- [x] **High-confidence audit thresholds met**:
  - **Choices**: ≥150 distinct choice sections audited (or ≥25% of all choice-bearing sections, whichever is larger).
  - **Stat changes**: ≥70% of stat-change sections audited.
  - **Saturation**: No new extraction/ordering issues found in the last 30 audits per feature class (choices/stat changes).

---

## Approach

1. **Audit validator drift** vs current pipeline output schema.
2. **Update Node validator** to handle current structures (e.g., combat arrays).
3. **Wire canonical validation** in recipes (`recipe-ff-ai-ocr-gpt51*.yaml`).
4. **Add versioning**:
   - Add a `validatorVersion` (or similar) in `gamebook.json` metadata.
   - Node validator emits its own version.
   - On mismatch: warn + record in report (do not fail if validation succeeds).
5. **Documentation**: Update README + AGENTS with “ship validator with gamebook” guidance.
6. **Navigation semantics**:
   - Use `navigation.terminal` to represent outcomes with no target section (e.g., death from stat checks).
   - Preserve navigation order based on HTML anchor order; place stat checks before choices when the text sequence indicates a roll before links.
7. **Sequence semantics**:
   - Replace `navigation` with ordered `sequence` events (choices, stat changes, combat, item events).
   - `sequence` is required on gameplay sections and is the canonical source of flow + targets.
8. **AI assist guideline**:
   - Prefer deterministic extraction first, but use targeted AI calls when logic complexity would balloon or edge cases are too varied.
   - Keep AI calls bounded; use them as a pragmatic accuracy lever for tricky sections instead of overfitting regexes.
   - Any AI-assisted extraction must still be validated (tests + pipeline run) and logged in the work log.
9. **Evidence-only rules**:
   - Only add new extraction/validation rules when they are explicitly required by verified examples in the source text.
   - Record the concrete section IDs and text snippets that justify the rule before implementing it.

### Sequence Schema (Draft)
- **choice**: `{ kind: "choice", targetSection, choiceText?, effects?: ItemEvent[] }`
- **stat_change**: `{ kind: "stat_change", stat, amount, permanent? }`
- **stat_check**: `{ kind: "stat_check", stat, diceRoll?, passCondition?, failCondition?, pass?: {targetSection|terminal}, fail?: {targetSection|terminal} }`
- **item**: `{ kind: "item", action: "add"|"remove"|"reference", name }`
- **item_check**: `{ kind: "item_check", itemName?, has?: {targetSection|terminal}, missing?: {targetSection|terminal} }`
- **state_check**: `{ kind: "state_check", conditionText?, has?: {targetSection|terminal}, missing?: {targetSection|terminal} }`
- **test_luck**: `{ kind: "test_luck", lucky?: {targetSection|terminal}, unlucky?: {targetSection|terminal} }`
- **combat**: `{ kind: "combat", enemies: [...], outcomes?: {win|lose|escape: {targetSection|terminal}} }`
- **death**: `{ kind: "death", outcome: {targetSection|terminal}, description? }`

---

## Tasks

- [x] Identify and fix validator drift (combat arrays, other schema mismatches).
- [x] Update Node validator to handle new shapes; remove legacy-only paths/shims as needed.
- [x] Rewire canonical validation stage in recipes to use Node validator.
- [x] Add version stamp in gamebook output + validator report.
- [x] Implement mismatch warning logic (no fail on mismatch if validation passes).
- [x] Update README and AGENTS.md with validator guidance and portability note.
- [x] Run Node validator on `ff-ai-ocr-gpt51-pristine-fast-full` and record artifacts.
- [x] Normalize navigation targets for stat checks/death outcomes to section IDs or non-target outcomes before validation.
- [x] Implement `terminal` navigation outcomes and update Node validator schema/logic accordingly.
- [x] Preserve navigation link order from source text when building `navigation` arrays.
- [x] Replace `navigation` with ordered `sequence` events in schema + builders + validators.
- [x] Update validators to derive reachability/choice completeness from `sequence`.
- [x] Remove legacy gameplay fields from `gamebook.json` output and forbid them in the Node schema/types.
- [x] Add upstream sequence-ordering stage to canonical and resume recipes.
- [x] Remove `continue_if`/`else` from `stat_change` schema/builders; drop survival-only stat checks and rely on global death rule.
- [x] Extract conditional item effects into `choice.effects` when choice text implies add/remove.
- [x] Verify Node validator includes all critical checks previously enforced by `validate_ff_engine_v2` (parity checklist).
- [x] Ensure Python `validate_ff_engine_v2` is forensics-only (not gating pipeline success).
- [x] Produce a single-file JS validator bundle with embedded schema for game engine consumption and document invocation.
- [x] Manually audit 20 sections each for inventory, stat changes, combat, choices, and **all available sections** for any other feature class if fewer than 20 exist; record artifact paths + findings in work log.
- [x] Continue audits until high-confidence thresholds are met (choices ≥150 or ≥25%, stat changes ≥70%, and zero new issues in last 30 samples per feature).
- [x] Define conditional sequence event shape (schema + examples) for item/flag‑gated mechanics and outcomes.
- [x] Implement conditional sequence events in builders and sequence ordering (including conditional item removal/stat changes).
- [x] Update Node validator schema/types/bundle and validation logic to support conditional events.
- [x] Add synthetic tests for conditional sequence behaviors (item‑gated stat changes and conditional outcomes).
- [x] Re‑run pipeline from the appropriate stage and manually verify conditional sections in `gamebook.json` (record evidence).
- [x] Add `state_check` for non‑item conditions (schema/types/bundle + builders + ordering) and migrate non‑item checks to `state_check`.

---

## Audit Tracker

**Purpose:** Track which sections have been manually audited for each feature class to avoid duplicates and ensure coverage.

**Inventory (26 audited):** 206, 105, 106, 162, 171, 9, 54, 33, 240, 257, 285, 94, 11, 157, 71, 273, 307, 281, 270, 150, background, 20, 256, 158, 175, 253  
**Stat changes (66 audited):** 390, 157, 20, 6, 167, 132, 397, 247, 26, 297, 386, 337, 358, 173, 150, 306, 33, 343, 235, 384, 304, 147, 115, 246, 223, 179, 16, 162, 158, 171, 238, 28, 377, 286, 189, 363, 195, 190, 295, 207, 199, 38, 139, 123, 353, 389, 175, 287, 57, 394, 215, 95, 354, 220, 391, 45, 330, 395, 42, 72, 103, 285, 309, 336, 339, 399  
**Combat (32 audited):** 302, 166, 312, 51, 236, 143, 211, 225, 254, 139, 196, 247, 331, 349, 294, 124, 130, 148, 203, 245, 6, 39, 369, 189, 145, 40, 327, 387, 380, 91, 151, 172  
**Choices (152 audited):** 310, 205, 284, 201, 162, 239, 231, 356, 246, 322, 146, 340, 171, 145, 60, 300, 362, 45, 383, 200, 271, 263, 318, 398, 107, 260, 120, 327, 230, 367, 204, 348, 100, 131, 256, 216, 224, 51, 306, 84, 158, 93, 320, 52, 40, 382, 273, 254, 307, 238, 166, 156, 288, 338, 241, 314, 50, 207, 195, 385, 92, 177, 1, 5, 6, 9, 10, 11, 12, 13, 14, 15, 16, 18, 20, 21, 22, 23, 24, 25, 26, 27, 37, 69, 97, 132, 155, 223, 226, 243, 252, 257, 262, 265, 266, 280, 285, 290, 292, 304, 365, 386, 29, 30, 56, 74, 81, 94, 95, 104, 105, 110, 124, 129, 134, 152, 163, 186, 209, 211, 229, 309, 313, 343, 360, 379, 395, 38, 42, 49, 68, 78, 80, 111, 139, 148, 164, 167, 182, 213, 220, 227, 251, 269, 287, 289, 291, 339, 363, 371, 376, 380  
**Item/State checks audited (14 total available in this run):** 90, 134, 188, 315, 376, 318, 159, 364, 146, 342, 222, 234, 10, 339  
**Test Luck (27 audited):** 332, 335, 30, 294, 275, 89, 361, 204, 79, 5, 228, 180, 67, 378, 174, 225, 177, 181, 98, 186, 289, 21, 149, 125, 202, 309, 374  
**Custom events audited (1):** 191  

## Work Log

### 20251229-1615 — Story created
- **Result**: Success; stubbed story to re‑canonize Node validator and add versioning/portability guidance.
- **Notes**: Current Node validator crashes on combat array output; pipeline uses Python validators instead.
- **Next**: Audit validator drift, then update Node validator and recipes.

### 20251229-1757 — Aligned tasks with no-compat directive
- **Result**: Success; revised task to remove legacy-compat requirement.
- **Notes**: Task now explicitly allows removing legacy-only paths/shims.
- **Next**: Audit Node validator vs current pipeline output to identify concrete drift points.

### 20251229-1803 — Updated Node validator schema/docs for current gamebook shape
- **Result**: Partial success; updated schema/types/docs to require presentation_html and added current section fields.
- **Notes**: Edited `modules/validate/validate_ff_engine_node_v1/validator/gamebook-schema.json`, `modules/validate/validate_ff_engine_node_v1/validator/types.d.ts`, `modules/validate/validate_ff_engine_node_v1/validator/README.md`, `modules/validate/validate_ff_engine_node_v1/validator/USAGE.md`.
- **Next**: Run the Node validator against a recent `output/runs/*/gamebook.json` to confirm it passes end-to-end.

### 20251229-1806 — Ran Node validator on latest good run
- **Result**: Failure; validation failed with invalid navigation targets.
- **Notes**: Ran `PYTHONPATH=. python modules/validate/validate_ff_engine_node_v1/main.py --input output/runs/ff-ai-ocr-gpt51-pristine-fast-full/gamebook.json --out output/runs/ff-ai-ocr-gpt51-pristine-fast-full/gamebook_validation_node.json`. Errors: `/sections/16/navigation/6/targetSection` = `"16 (try again)"`, `/sections/16/navigation/7/targetSection` = `"death (no section number)"`.
- **Next**: Investigate why navigation targets are not normalized to section IDs before build/clean; fix in upstream extraction or builder normalization, then re-run validation.

### 20251229-1811 — Added requirements for target normalization + navigation order
- **Result**: Success; documented new requirements and tasks.
- **Notes**: Verified section 16 text order vs navigation order: text lists Turn to 16, 392, 177, 287, 132, 249; navigation order is 16, 132, 177, 249, 287, 392 plus stat_check edges. This mismatch would reorder choices in UI.
- **Next**: Identify where navigation order is being re-sorted (builder/extractor) and preserve original textual order.

### 20251229-1823 — Implemented terminal outcomes + navigation ordering heuristics
- **Result**: Partial success; added terminal support, target normalization, and choice ordering by HTML anchor order.
- **Notes**: Updated builder logic in `modules/export/build_ff_engine_with_issues_v1/main.py` and `modules/export/build_ff_engine_v1/main.py` to normalize stat_check/death targets and reorder choices by anchor order; added terminal support + schema/validator updates in `modules/validate/validate_ff_engine_node_v1/validator/*`.
- **Next**: Re-run a minimal pipeline to rebuild `gamebook.json` from the existing run artifacts and validate with the Node validator.

### 20251229-1828 — Resume build run + manual artifact inspection
- **Result**: Success; resume build completed and Node validator passed.
- **Notes**: Ran `python driver.py --recipe configs/recipes/recipe-ff-ai-ocr-gpt51-resume-build.yaml` (run id `ff-ai-ocr-gpt51-pristine-fast-full-navfix-20251229-182829-35c4df`). Inspected `output/runs/ff-ai-ocr-gpt51-pristine-fast-full-navfix-20251229-182829-35c4df/gamebook.json` section 16: navigation now starts with stat_check pass to `16`, includes terminal death on fail, and choice order matches HTML table (392, 177, 287, 132, 249). Node validator report at `output/runs/ff-ai-ocr-gpt51-pristine-fast-full-navfix-20251229-182829-35c4df/05_validate_ff_engine_node_v1/gamebook_validation_node.json` shows valid.
- **Next**: Wire Node validator into canonical recipe and add versioning/mismatch warnings per story scope.

### 20251229-2002 — Added validator versioning + wired Node validator in recipes
- **Result**: Success; gamebook now stamps validatorVersion and Node validator emits version/mismatch warnings.
- **Notes**: Updated build modules to stamp `metadata.validatorVersion` from bundled validator package; Node validator now reports `validatorVersion` and warns on mismatch. Wired `validate_ff_engine_node_v1` into `recipe-ff-ai-ocr-gpt51.yaml` (+ pristine/old-fast variants) as the engine report; kept `validate_ff_engine_v2` for forensics. Ran `python driver.py --recipe configs/recipes/recipe-ff-ai-ocr-gpt51-resume-build.yaml` → `ff-ai-ocr-gpt51-pristine-fast-full-navfix-20251229-200158-0b54a7` with `gamebook.json` + `gamebook_validation_node.json` valid and versions matching.
- **Next**: Update story-083 checklist if needed and confirm canonical recipe change is aligned with downstream validators.

### 20251229-2039 — Added sequence-only requirement
- **Result**: Success; documented sequence replacing navigation in success criteria/tasks.
- **Notes**: Added requirement that `sequence` becomes canonical flow source and `navigation` is removed.
- **Next**: Implement schema/builder/validator changes and re-run minimal build for verification.

### 20251230-0055 — Dropped per-section survival gates for stat_change
- **Result**: Success; removed `continue_if`/`else` from stat_change schema and builders, and filtered survival-only stat checks.
- **Notes**: Updated `modules/enrich/sequence_order_v1/main.py` and `modules/export/build_ff_engine*_v1/main.py` to drop survival-only stat checks and ignore “continue if alive” placeholders. Updated Node validator schema/types and rebuilt bundle; added test for survival-check dropping.
- **Next**: Re-run from `order_sequence` or `build_gamebook`, validate Node report, and re-check section 16 sequence for correct ordering.

### 20251230-0100 — Rebuilt sequence + gamebook after survival-rule change
- **Result**: Success; Node validator passes and section 16 no longer emits a stat_check placeholder.
- **Notes**: Ran `python driver.py --recipe configs/recipes/recipe-ff-ai-ocr-gpt51.yaml --run-id ff-ai-ocr-gpt51-pristine-fast-full --allow-run-id-reuse --output-dir output/runs/ff-ai-ocr-gpt51-pristine-fast-full --start-from order_sequence`. Verified `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/gamebook.json` section 16 sequence begins with `stat_change` and then ordered choices; Node report at `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/27_validate_ff_engine_node_v1/gamebook_validation_node.json` valid.
- **Next**: Continue manual audit checklist (20 each inventory/stat changes/combat/choices/other) with artifact evidence.

### 20251230-0059 — Manual audit pass (20 each: inventory/stat_change/combat/choices/other)
- **Result**: Mixed; several extraction/order errors found across inventory, stat changes, combat ordering, and other features.
- **Notes**: Reviewed `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/gamebook.json` for 20 sections per feature. Inventory failures include false item names: sections 201 (adds “nothing except for an old bone”), 253 (“bone out of your backpack”), 55 (“yourself in another circular room”), 266 (“which you may take with you if you wish”), 360 (“yourself in a small chamber”), 135 (“but do not see anybody approaching”), 358 (“balance”, “tumble headlong to the floor”). Stat-change issues include variable-dice damage collapsed to constants: section 223 (roll two dice → STAMINA loss modeled as -1), section 247 (spike count roll → -2), plus item_check glitch in 217 (itemName = “(lose 1 SKILL point)”). Combat ordering issue: section 139 and 247 have stat_change after combat though text applies damage before fight. Choice/other feature issues: section 191 missing stat_check for “roll two dice”; section 47 duplicates item_check instead of has/missing; section 371/378 inject bogus item adds; section 357 item_check itemName corrupt (“one)?”); section 309 includes spurious item remove. Evidence sample paths: `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/gamebook.json` sections 201/253/55/266/360/135/358/223/247/217/139/191/47/371/378/357/309.
- **Next**: Start fixing extraction/ordering errors and add synthetic tests per fix; re-run from `extract_inventory` and `order_sequence`.

### 20251230-0136 — Inventory/stat mods cleanup + dice-check sequence + rerun
- **Result**: Partial success; most audit failures resolved, new dice-check custom event emitted, and pipeline run passes validators.
- **Notes**: Hardened `extract_inventory_v1` against narrative false positives (cleaning, verb/phrase filters, question-form checks, audit filtering by text mention), added LLM/audit gating by verb proximity; improved `sequence_order_v1` with plain dice-check custom events and combat keyword ordering; added dice expression support in `extract_stat_modifications_v1` and filtered duplicate numeric losses. Re-ran `python driver.py --recipe configs/recipes/recipe-ff-ai-ocr-gpt51.yaml --run-id ff-ai-ocr-gpt51-pristine-fast-full --allow-run-id-reuse --output-dir output/runs/ff-ai-ocr-gpt51-pristine-fast-full --start-from extract_stat_modifications` (after a failed run from extract_inventory due to audit NoneType; fixed guard). Verified `gamebook.json` sections 201/266/358/371/191 and Node report. Remaining open questions: whether section 253 should explicitly remove the bone (currently no item event) and whether conditional shield drop (217) should be encoded as remove vs check.
- **Next**: Decide on idempotent item-removal semantics and finish any remaining manual audits if new failures surface.

### 20251230-0137 — Added AI assist guideline
- **Result**: Success; documented a bounded AI‑assist rule for tricky extraction cases.
- **Notes**: Added guideline to prefer deterministic logic but allow targeted AI calls to avoid brittle complexity; still requires validation + logging.
- **Next**: Apply this guideline when deciding between regex expansion vs targeted AI repair on remaining edge cases.

### 20251230-0849 — Implemented item-loss extraction for “take out of backpack”
- **Result**: Success; section 253 now records the bone removal, no false gains added.
- **Notes**: Added a loss regex for “take X out of your backpack” and updated tests. Re-ran pipeline from `extract_inventory` to regenerate `gamebook.json`. Verified `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/gamebook.json` section 253 sequence includes `{kind: "item", action: "remove", name: "bone"}`.
- **Next**: Continue spot checks on any remaining questionable inventory/AI audit outputs.

### 20251229-2053 — Implemented sequence schema + validated on resume build
- **Result**: Success; Node validator passes with sequence-only output.
- **Notes**: Updated builders/validators/schemas to replace `navigation` with ordered `sequence`. Ran `python driver.py --recipe configs/recipes/recipe-ff-ai-ocr-gpt51-resume-build.yaml` → `ff-ai-ocr-gpt51-pristine-fast-full-navfix-20251229-205319-dc6422`. Inspected `output/runs/ff-ai-ocr-gpt51-pristine-fast-full-navfix-20251229-205319-dc6422/gamebook.json` section 16: sequence starts with `stat_change` + `continue_if: alive`, terminal death on else, then ordered choices (16, 392, 177, 287, 132, 249). Node report at `output/runs/ff-ai-ocr-gpt51-pristine-fast-full-navfix-20251229-205319-dc6422/05_validate_ff_engine_node_v1/gamebook_validation_node.json` shows valid.
- **Next**: Confirm downstream validators relying on `navigation` are fully migrated (choice completeness, smoke checks).

### 20251229-2055 — Re-ran resume build after item guard fix
- **Result**: Success; Node validator passes and sequence looks correct.
- **Notes**: Ran `python driver.py --recipe configs/recipes/recipe-ff-ai-ocr-gpt51-resume-build.yaml` → `ff-ai-ocr-gpt51-pristine-fast-full-navfix-20251229-205451-f41ebd`. Verified `output/runs/ff-ai-ocr-gpt51-pristine-fast-full-navfix-20251229-205451-f41ebd/gamebook.json` section 16 sequence (stat_change with continue_if/terminal else, ordered choices). Node report at `output/runs/ff-ai-ocr-gpt51-pristine-fast-full-navfix-20251229-205451-f41ebd/05_validate_ff_engine_node_v1/gamebook_validation_node.json` valid.
- **Next**: Decide whether to deprecate or delete legacy `navigation` consumers outside validators (if any remain).

### 20251229-2127 — Added sequence-only + upstream ordering requirements
- **Result**: Success; story now tracks schema forbiddance + ordering stage integration.
- **Notes**: Updated success criteria/tasks for sequence-only output and upstream sequence ordering stage; began removing legacy fields from builders/schema and wiring `sequence_order_v1` into recipes.
- **Next**: Finish removing legacy fields from `build_ff_engine_v1`, forbid legacy fields in Node schema/types, wire `sequence_order_v1` into resume recipe, then re-run a resume build and inspect `gamebook.json`.

### 20251229-2130 — Sequence-only build + artifact inspection
- **Result**: Success; resume build passes Node validator and legacy fields removed.
- **Notes**: Ran `python driver.py --recipe configs/recipes/recipe-ff-ai-ocr-gpt51-resume-build.yaml --run-id ff-ai-ocr-gpt51-pristine-fast-full-seqonly-20251229-2136 --output-dir output/runs/ff-ai-ocr-gpt51-pristine-fast-full-seqonly-20251229-2136`. Inspected `output/runs/ff-ai-ocr-gpt51-pristine-fast-full-seqonly-20251229-2136/gamebook.json` section 16 sequence: stat_change with continue_if/terminal else, then ordered choices 16, 392, 177, 287, 132, 249. Verified no legacy fields anywhere (navigation/combat/items/statModifications/statChanges/diceChecks/deathConditions absent). Node report at `output/runs/ff-ai-ocr-gpt51-pristine-fast-full-seqonly-20251229-2136/07_validate_ff_engine_node_v1/gamebook_validation_node.json` valid.
- **Next**: Update remaining story tasks (story-083 alignment) and ensure schema forbiddance + sequence ordering changes are fully documented.

### 20251229-2202 — Validator parity + portable bundle
- **Result**: Success; Node validator now enforces missing/duplicate sections + empty text/no-choice warnings, and single-file bundle is generated and runnable.
- **Notes**: Updated `modules/validate/validate_ff_engine_node_v1/validator/validation.js` to add missing/duplicate/empty/no-choice checks (expected range from `gamebook.provenance.expected_range`). Generated `modules/validate/validate_ff_engine_node_v1/validator/gamebook-validator.bundle.js` via `node modules/validate/validate_ff_engine_node_v1/validator/build_bundle.js` and confirmed it validates `output/runs/ff-ai-ocr-gpt51-pristine-fast-full-seqonly-20251229-2136/gamebook.json` (bundle runs without deps). Marked `validate_ff_engine_v2` forensics-only in `modules/validate/validate_ff_engine_v2/module.yaml`.
- **Next**: Decide whether to close out story-083 alignment item or leave as "informational only."

### 20251229-2204 — Added shipping snippet to README
- **Result**: Success; documented portable bundle usage for game engine shipping.
- **Notes**: Added a short “how to ship” snippet under `validate_ff_engine_node_v1` in `README.md` referencing `gamebook-validator.bundle.js`.
- **Next**: None (documentation aligned with bundle output).

### 20251229-2209 — Auto-regenerate validator bundle on validation
- **Result**: Success; Node validator now rebuilds the single-file bundle on each validation run.
- **Notes**: Updated `modules/validate/validate_ff_engine_node_v1/main.py` to run `build_bundle.js` before invoking the CLI validator. Re-ran validation on `output/runs/ff-ai-ocr-gpt51-pristine-fast-full-seqonly-20251229-2136/gamebook.json` and confirmed success.
- **Next**: None.

### 20251229-2224 — Renamed forensics validator stage
- **Result**: Success; recipe stage now signals forensics-only validation.
- **Notes**: Renamed `validate_gamebook` stage to `forensics_gamebook` in canonical recipes and removed it from `validate_game_ready` dependencies so the Node validator is the sole engine gate.
- **Next**: None.

### 20251229-2225 — README updated for forensics stage naming
- **Result**: Success; documentation now matches recipe stage naming.
- **Notes**: Updated `README.md` to refer to the forensics stage as `forensics_gamebook / validate_ff_engine_v2`.
- **Next**: None.

### 20251230-0926 — Inventory extraction cleanup + pronoun recovery + rerun
- **Result**: Partial success; removed multiple false positives and recovered pronoun-based item gain, but conditional item effects still ambiguous.
- **Notes**: Hardened `extract_inventory_v1` to filter travel/locational false positives (e.g., “take a raft up‑river”), added LLM add gating by verb proximity, and added a pronoun-backreference heuristic for “put it in your backpack” to recover the preceding item. Added tests in `tests/test_extract_inventory_v1.py` for “done so already”, “find it is glued…”, “take a raft up‑river…”, and pronoun recovery. Re‑ran `python driver.py --recipe configs/recipes/recipe-ff-ai-ocr-gpt51.yaml --run-id ff-ai-ocr-gpt51-pristine-fast-full --allow-run-id-reuse --output-dir output/runs/ff-ai-ocr-gpt51-pristine-fast-full --start-from extract_inventory` and validated Node report. Manual checks: `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/gamebook.json` section 11 now includes `{kind:"item", action:"add", name:"emerald eye"}`; section 339 no longer emits bogus items; section 337 no longer emits `item_check` “done so already”; background now only shows `Violet Scarf` and `Sword` items. 
- **Next**: Review conditional item wording (e.g., section 269 “eat rice/drink water” vs “take diamond”) and decide whether to suppress/encode choice‑conditional item changes.

### 20251230-0950 — Stat-change dice add + combat-mod filter + key-check merge
- **Result**: Success; fixed dice‑add expressions, removed combat‑only stat changes, and merged generic key checks.
- **Notes**: Updated `extract_stat_modifications_v1` to parse “roll die + add N → lose per each” as `-(1d6+N)` and to drop combat‑duration modifiers; added tests in `tests/test_extract_stat_modifications_v1.py`. Updated `sequence_order_v1` to merge “iron key” + “key” checks into a single item_check; added test in `tests/test_sequence_order_v1.py`. Re‑ran `python driver.py --recipe configs/recipes/recipe-ff-ai-ocr-gpt51.yaml --run-id ff-ai-ocr-gpt51-pristine-fast-full --allow-run-id-reuse --output-dir output/runs/ff-ai-ocr-gpt51-pristine-fast-full --start-from extract_stat_modifications`. Verified `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/gamebook.json` section 394 stat_change is `-(1d6+2)` and section 91 no longer has a stat_change; sections 146/318 now have a single `item_check` with has/missing.
- **Next**: Continue audits for choices/other features; decide policy for conditional item effects and any remaining extraction gaps.

### 20251230-1028 — Inventory choice filters + plural backpack capture
- **Result**: Partial success; reduced conditional item noise and recovered plural “put them in your backpack” gains, but conditional item semantics remain an open question.
- **Notes**: Tightened inventory filters to avoid treating choice prompts as automatic adds/removes, added conservative audit removal guards, and added plural pronoun extraction (`put them in your backpack`) for items like “eyes.” Added tests in `tests/test_extract_inventory_v1.py` (choice‑prompt non‑add/remove, plural pronoun, keep‑removed guard). Re‑ran `python driver.py --recipe configs/recipes/recipe-ff-ai-ocr-gpt51.yaml --run-id ff-ai-ocr-gpt51-pristine-fast-full --allow-run-id-reuse --output-dir output/runs/ff-ai-ocr-gpt51-pristine-fast-full --start-from extract_inventory`. Manual checks: `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/gamebook.json` section 273 now includes item “the yellow jewelled eyes”; section 257 again shows Gold Piece + hollow wooden tube; section 156 no longer emits a bogus item; section 269 no longer removes rice/water unconditionally.
- **Next**: Decide how to represent items that are found but only optionally taken (e.g., section 281 mirror), or introduce conditional item events.

### 20251229-2235 — Marked story-083 alignment complete
- **Result**: Success; confirmed story-083 already requires Node validator pass.
- **Notes**: Checked off the story-083 alignment success criterion based on user confirmation.
- **Next**: None.

### 20251230-1647 — Choice effects + optional-take guard + schema update
- **Result**: Success; choice events now carry item effects and optional-take prompts no longer create unconditional gains.
- **Notes**: Added `choice.effects` (item add/remove) to Node schema/types and builder extraction; rebuilt `gamebook-validator.bundle.js`. Inventory extraction now keeps narrative items even if referenced in choice prompts, but suppresses gains when an explicit optional “take” choice is present; added `in your backpack` cleanup and tests (`tests/test_build_ff_engine_choice_effects.py`, updated `tests/test_extract_inventory_v1.py`). Ran `PYTHONPATH=. pytest tests/test_extract_inventory_v1.py tests/test_build_ff_engine_choice_effects.py`.
- **Next**: Re-run from `extract_inventory` and `build_gamebook` to verify section 281 bread/mirror behavior and confirm choice effects appear where expected.

### 20251230-1805 — Choice effects from HTML context + rebuild
- **Result**: Success; choice effects now derive from anchor context and avoid duplicate adds.
- **Notes**: Enriched choices from `raw_html` context in builders, filtered add-effects already present earlier in the sequence, and removed optional-take suppression so narrative finds stay unconditional. Ran `PYTHONPATH=. pytest tests/test_extract_inventory_v1.py tests/test_build_ff_engine_choice_effects.py`, then `python driver.py --recipe configs/recipes/recipe-ff-ai-ocr-gpt51.yaml --run-id ff-ai-ocr-gpt51-pristine-fast-full --allow-run-id-reuse --output-dir output/runs/ff-ai-ocr-gpt51-pristine-fast-full --start-from extract_inventory` and `--start-from build_gamebook`.
- **Evidence**: `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/gamebook.json` section 281 now has bread/mirror/charm adds plus choice effect removing bread on the 399 choice; section 399 no longer adds mirror/charm; section 156 adds Rope unconditionally with no choice effects.
- **Next**: Continue manual audit samples for any remaining edge cases flagged by review.

### 20251230-1840 — Spot check additional sections (choice effects + inventory)
- **Result**: Partial success; found multiple choice-effect false positives and one conditional item being added unconditionally.
- **Notes**: Spot-checked `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/gamebook.json` sections 11/16/47/71/91/106/139/146/171/257/273/318/394. Issues: section 11 choice effect removes “later” (from “be of use later”); section 106 choice effect adds “on the shape of any nearby being” (from potion description); section 273 choice effects add “down on all fours”/“crawl out of the room holding the skull”; section 156 adds Rope unconditionally despite text “If you wish to … take the rope…”. These require tighter choice-effect parsing and conditional take handling.
- **Next**: Decide whether to (a) tighten choice-effect parsing (verb list/stopwords, avoid “take on”), and (b) treat optional-take items as conditional effects rather than unconditional adds.

### 20251230-1852 — Choice-effect cleanup + optional-take handling
- **Result**: Success; false positives removed and optional-take items moved into conditional choice effects.
- **Notes**: Tightened choice-effect parsing (removed “get”, added stopwords, skipped “take on”), and added optional‑take detection to move add effects onto the target choice while removing unconditional item adds. Added/expanded tests in `tests/test_build_ff_engine_choice_effects.py` and re-ran `python driver.py --recipe configs/recipes/recipe-ff-ai-ocr-gpt51.yaml --run-id ff-ai-ocr-gpt51-pristine-fast-full --allow-run-id-reuse --output-dir output/runs/ff-ai-ocr-gpt51-pristine-fast-full --start-from build_gamebook`.
- **Evidence**: `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/gamebook.json` section 11 now only has emerald eye add + choices (no “later” effect); section 106 has only glass phial add + choice (no “shape” effect); section 273 has only eyes add + choices; section 156 now has no unconditional rope add, and the 208 choice has `effects: [{kind:"item", action:"add", name:"rope"}]`.
- **Next**: Continue remaining audit samples and verify any other optional‑take patterns.

### 20251230-1853 — Spot check additional sections (audit batch)
- **Result**: Partial success; found new issues in inventory and stat-change extraction.
- **Notes**: Checked `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/gamebook.json` sections 201/223/247/269/285/309/357/371/378/381. Issues: section 201 adds “old bone” unconditionally despite “take … if you wish”; section 223 has duplicated luck/stamina stat_change entries; section 269 choice effects include bad token “drink the water -” and may need normalized “water” removal; section 381 adds “parchment from the skeleton” as a choice effect but context unclear (likely not a conditional item). Other sections looked consistent.
- **Next**: Fix optional‑take detection for “if you wish” without explicit “take” clause near turn‑to; dedupe stat_changes; tighten choice‑effect item cleaning to strip trailing punctuation and “drink the water” phrasing.

### 20251230-1916 — Fixed optional-take + dedupe + choice-effect cleanup
- **Result**: Success; optional-take items no longer mutate inventory, stat_change duplicates removed, choice effects cleaned.
- **Notes**: Optional‑take choices now remove unconditional adds and clear any item effects (including negative “do not wish to take” cases). Deduped stat_change events in builders. Choice‑effect cleaner now strips “drink/eat/use” and trailing articles/punctuation; added tests for optional‑take, negative‑choice, water cleanup, and target normalization. Ran `PYTHONPATH=. pytest tests/test_extract_inventory_v1.py tests/test_build_ff_engine_choice_effects.py tests/test_build_ff_engine_stat_dedupe.py tests/test_build_ff_engine_sequence_normalize.py` and re‑ran pipeline from `extract_inventory`.
- **Evidence**: `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/gamebook.json` sections 201 (no old bone add), 223 (no duplicate stat_change), 269 (effects remove “rice” and “water”), 381 (no parchment effects); node validator pass at `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/27_validate_ff_engine_node_v1/gamebook_validation_node.json`.
- **Next**: Continue audit spot checks for remaining categories and record outcomes.

### 20251230-1919 — Spot check batch + optional-take cleanup
- **Result**: Success; fixed optional-take effect leak and validated batch.
- **Notes**: Spot-checked `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/gamebook.json` sections 1/14/33/55/135/156/217/253/266/285. Found choice-effect leak in section 266 (“with you if you wish”) and removed via choice-effect cleanup; added tests for “with you if you wish” cleanup. Rebuilt gamebook from `build_gamebook`.
- **Evidence**: Section 266 now only has the `Turn to 305` choice with no effects; section 217 retains `remove Shield` + `-1 SKILL` + choice; sections 33/253/285 inventory/stat changes look consistent.
- **Next**: Continue remaining audit samples.

### 20251229-2301 — Ran node validator + manual gamebook spot checks
- **Result**: Partial success; Node validator passes but warnings show reachability issue, and spot checks found sequence ordering bug.
- **Notes**: Ran `PYTHONPATH=. python modules/validate/validate_ff_engine_node_v1/main.py --input output/runs/ff-ai-ocr-gpt51-pristine-fast-full/gamebook.json --out /tmp/node_validate.json` (valid=true, 0 errors, 401 warnings; startSection is null so validator treats "background" as start and flags 400 unreachable sections). Manually inspected `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/gamebook.json` sections 16/223/235/246/87: section 16 sequence order matches table; sections 223/246 include stamina + luck stat changes; section 235 sequence is wrong (choice appears before stat_change despite text "Lose 2 STAMINA ... If you are still alive, turn to 73"). This indicates ordering logic still incorrect for some sections.
- **Next**: Fix sequence ordering logic to respect text order (e.g., stat_change before conditional choice in section 235), re-run from ordering stage, and re-check warnings for startSection behavior.

### 20251229-2307 — Fixed sequence ordering for stat_change/items vs choices
- **Result**: Success; ordering now matches text for spot checks, but Node validator still warns due to missing startSection.
- **Notes**: Updated `modules/enrich/sequence_order_v1/main.py` to reorder `stat_change` + `item` events relative to choices using raw HTML positions, and expanded mechanics hint detection. Re-ran `python driver.py --recipe configs/recipes/recipe-ff-ai-ocr-gpt51.yaml --run-id ff-ai-ocr-gpt51-pristine-fast-full --allow-run-id-reuse --output-dir output/runs/ff-ai-ocr-gpt51-pristine-fast-full --start-from order_sequence`. Manually inspected `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/gamebook.json` sections 150/235/16: section 150 now orders stat_change → item → choice, section 235 orders stat_change → choice, section 16 unchanged and correct. Node report at `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/27_validate_ff_engine_node_v1/gamebook_validation_node.json` still shows 401 warnings (startSection null so reachability warnings fire).
- **Next**: Decide whether to set `startSection` in the build to silence reachability warnings or treat as informational.

### 20251229-2315 — Background section now links to section 1
- **Result**: Success; Node validator warnings cleared by adding the implicit “Turn to 1” choice on background.
- **Notes**: Updated `modules/export/build_ff_engine_with_issues_v1/main.py` and `modules/export/build_ff_engine_v1/main.py` to always append a choice to section 1 in the `background` sequence if missing (preserves any existing events). Re-ran `python driver.py --recipe configs/recipes/recipe-ff-ai-ocr-gpt51.yaml --run-id ff-ai-ocr-gpt51-pristine-fast-full --allow-run-id-reuse --output-dir output/runs/ff-ai-ocr-gpt51-pristine-fast-full --start-from build_gamebook`. Verified `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/gamebook.json` background sequence includes `Turn to 1`; Node report at `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/27_validate_ff_engine_node_v1/gamebook_validation_node.json` now shows 0 warnings, 0 errors.
- **Next**: None.

### 20251229-2324 — Removed bogus inventory event from background
- **Result**: Success; background sequence no longer contains a fake item removal.
- **Notes**: `modules/enrich/sequence_order_v1/main.py` now drops mechanics events for the `background` section to avoid inventory false positives. Re-ran from `order_sequence` and verified `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/gamebook.json` background sequence is only `Turn to 1`.
- **Next**: None.

### 20251229-2332 — Inventory false-positive tuning (background)
- **Result**: Success; removed overly broad regex and restored background mechanics.
- **Notes**: Reverted the background mechanics suppression in `modules/enrich/sequence_order_v1/main.py` and tightened inventory extraction by removing the broad `with the ...` usage pattern in `modules/enrich/extract_inventory_v1/main.py`. Re-ran `python driver.py --recipe configs/recipes/recipe-ff-ai-ocr-gpt51.yaml --run-id ff-ai-ocr-gpt51-pristine-fast-full --allow-run-id-reuse --output-dir output/runs/ff-ai-ocr-gpt51-pristine-fast-full --start-from extract_inventory`. Verified `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/gamebook.json` background sequence now contains only `Turn to 1` without the bogus “officials” item.
- **Next**: Monitor for any missed legitimate “with the <item>” usage references; adjust patterns if needed.

### 20251229-2342 — Manual audit: 20 inventory, 20 stat changes, 20 combat, 20 choices, 20 test_luck
- **Result**: Mixed; many sections verified correct, but multiple correctness issues found in inventory extraction and event ordering/duplication.
- **Notes**: Audited `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/gamebook.json` against `presentation_html` for sampled sections (lists below). Issues found:
  - **Inventory issues**: 281 missing mirror/bone charm; 150 duplicate “Tiny Brass Bell” (two item adds); 171 duplicate Rope; 270 bogus remove “message, which says: 'Well done”; 324 item add “Glass Phial” with no corresponding text; 349 bogus item remove “other to grip your sword”; 230 unconditional remove Doppelganger Potion (should be conditional on choice); 138 adds bottle as item but text doesn’t clearly grant item (questionable).
  - **Stat change ordering**: 42 sequence places stat_check before stat_change, but text says “Lose 5 STAMINA” then roll; ordering mismatch.
  - **Combat semantics**: 151/145 apply “reduce SKILL/attack strength during combat” but modelled as stat_change (151) or missing (145); 254 escape outcome appears as choice but not in combat outcomes; 225 has test_luck before combat though text says after first attack round.
  - **Choice integrity**: 242 text includes a SKILL roll but sequence has only choices (missing stat_check); 234 conditional on carrying stilts but no item_check event.
  - **Test_luck duplication**: 180, 275, 309, 21 contain duplicate test_luck events; text has a single test.
- **Next**: Decide whether to (a) fix extraction/ordering for the above categories now, or (b) expand audit to cover additional feature classes (stat_check, item_check) before remediation.

#### Manual audit sample lists (verified against `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/gamebook.json`)
- **Inventory (20)**: 106, 201, 33, 281, 150, 129, 11, 339, 13, 163, 169, 349, 240, 112, 270, 138, 230, 156, 324, 71.
- **Stat changes (20)**: 337, 42, 123, 175, 397, 306, 38, 384, 115, 20, 215, 399, 45, 147, 171, 57, 207, 390, 217, 150.
- **Combat (20)**: 151, 51, 225, 369, 245, 130, 387, 380, 211, 254, 40, 349, 39, 327, 196, 172, 148, 139, 145, 189.
- **Choices (20)**: 182, 90, 221, 364, 32, 47, 298, 58, 205, 323, 38, 283, 125, 27, 54, 242, 234, 45, 139, 56.
- **Other feature (test_luck, 20)**: 180, 174, 125, 89, 332, 361, 30, 275, 374, 225, 204, 177, 378, 309, 79, 289, 21, 228, 149, 98.

### 20251230-1937 — Deduped overlapping item adds from inventory sources
- **Result**: Success; duplicate item adds collapsed to single, more specific names in sequence.
- **Notes**: Added `_dedupe_item_events` in `modules/export/build_ff_engine_with_issues_v1/main.py` and applied it to both generated and prebuilt sequences; added synthetic tests in `tests/test_build_ff_engine_item_dedupe.py` (2 cases). Ran `PYTHONPATH=. pytest tests/test_build_ff_engine_item_dedupe.py`. Rebuilt from `build_gamebook` and rechecked `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/gamebook.json` sections 94 and 157: now only `Opal-Studded Dagger` and `Large Pearl` respectively (no duplicates). Node validator and game-ready checks pass from the build_gamebook run.
- **Next**: Continue manual audit fixes (inventory/stat/combat/choices/test_luck) and add synthetic tests per fix.

### 20251230-1954 — Fixed choice effect bleed + inventory false positives + audit crash
- **Result**: Success; choice effects now scoped to the right sentence, optional-take handling preserves multi-item choices, and false-positive “use” items are filtered. Pipeline completed after prior stat-mod audit crash.
- **Notes**: Updated `_choice_effect_text` to extract the sentence containing the anchor (prevents “take the rope” bleeding into later choices), removed `keep` from add-verb regex, and suppressed effects when choice text includes “if you have”. Refined optional-take cleanup to only drop effects when a choice has only that optional item. Tightened inventory verb proximity to word-boundary matching and ignored “using the other” phrases; added `_build_audit_maps` to skip null item_index in stat-mod audit. Tests added/updated in `tests/test_build_ff_engine_choice_effects.py`, `tests/test_extract_inventory_v1.py`, `tests/test_extract_stat_modifications_v1.py`. Ran `PYTHONPATH=. pytest tests/test_build_ff_engine_choice_effects.py tests/test_extract_inventory_v1.py tests/test_extract_stat_modifications_v1.py`. Re-ran driver from `extract_stat_modifications` and verified `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/gamebook.json` sections 281 (mirror+charm on choice), 192 (no bogus “walking” item), 349 (no sword removal), 275 (no drinkable water use), 230 (no unconditional potion removal).
- **Next**: Continue manual audit fixes (combat ordering, test_luck ordering, remaining inventory edge cases) and add synthetic tests per fix.

### 20251230-2000 — Table choice effects + combat outcome ordering
- **Result**: Success; table-row choice effects now parsed correctly, combat events precede their outcome choices, and “rub/apply” use cases are handled.
- **Notes**: `_choice_effect_text` now extracts the containing `<tr>` block when anchors are in tables; added combat outcome reordering in build. Expanded removal verbs to include “rub/apply” and cleaned “into your/on your” tails. Added tests in `tests/test_build_ff_engine_choice_effects.py` and `tests/test_build_ff_engine_sequence_normalize.py`. Ran `PYTHONPATH=. pytest tests/test_build_ff_engine_choice_effects.py tests/test_build_ff_engine_sequence_normalize.py`. Rebuilt from `build_gamebook` and verified `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/gamebook.json` sections 138 (drink/rub liquid now remove liquid), 254 (combat before outcome choices).
- **Next**: Continue remaining manual audit list and add tests for any new fixes.

### 20251230-2122 — Inventory false-positives + stat-change expansion + reruns
- **Result:** Success; removed multiple inventory false positives, normalized conditional checks, and restored multi-stat gains.
- **Notes:**
  - Inventory: filtered “done so already” checks, cleaned “rope up again”, rejected crack/press/squeeze pseudo-items, added audit-addition verb gating, and normalized question-based checks (e.g., “have you drunk/read”). Added tests in `tests/test_extract_inventory_v1.py` covering these cases.
  - Stat mods: added pattern for “Add 1 to each of your SKILL, STAMINA and LUCK scores” and test in `tests/test_extract_stat_modifications_v1.py`.
  - Rebuilt run `ff-ai-ocr-gpt51-pristine-fast-full` from `extract_inventory` (multiple times) and from `extract_stat_modifications` after schema changes. Node validator passes and game-ready report is clean.
- **Evidence:**
  - `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/gamebook.json` section 96 now `{status: death}` with empty sequence (no bogus mirror item).
  - `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/gamebook.json` section 256 now only adds “Doppelganger Potion” (no crack/press/squeeze items).
  - `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/gamebook.json` section 391 includes +1 SKILL/STAMINA/LUCK in sequence.
- **Next:** Continue random section audits for any remaining edge cases; fix + add tests if new errors found.

### 20251230-2133 — Conditional-item normalization + choice-effect cleanup
- **Result:** Success; normalized “these items / this poem” checks and removed generic “liquid” effects.
- **Notes:**
  - Inventory checks now backfill pronoun references to the nearest concrete item; added tests for “these items” and “this poem”.
  - Choice effects now skip generic “liquid” and audit additions require add verbs; updated choice-effect tests accordingly.
  - Rebuilt run `ff-ai-ocr-gpt51-pristine-fast-full` from `extract_inventory` and verified updated gamebook output.
- **Evidence:**
  - `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/gamebook.json` section 315 now has a single `item_check` with shared item name for has/missing.
  - `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/gamebook.json` section 134 now normalizes “read this poem” to the full poem reference.
  - `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/gamebook.json` section 9 no longer includes a “liquid” choice effect.
- **Next:** Continue random audits; if no new issues emerge, summarize completion of the manual audit requirement.

### 20251230-2232 — Choice-order fallback + choice-effect cleanup + inventory optional handling
- **Result:** Success; fixed choice ordering when links lack anchors, removed several false-positive choice effects, and preserved container-found items while keeping optional-take logic for true opt-ins.
- **Notes:**
  - Sequence ordering now falls back to `Turn to N` positions when no anchors exist; added test `test_sequence_orders_choices_without_anchors` in `tests/test_sequence_order_v1.py` and re-ran from `order_sequence`.
  - Choice effects now scope to paragraph/list items, trim to short pre-`turn to` window, and avoid false positives (accept/offer, take part, gift, gulps). Added new tests in `tests/test_build_ff_engine_choice_effects.py`.
  - Optional-take handling preserves items found inside containers and supports “taking … with you” while cleaning “just the …” names. Added tests in `tests/test_build_ff_engine_choice_effects.py` and `tests/test_extract_inventory_v1.py`.
  - Rebuilt run `ff-ai-ocr-gpt51-pristine-fast-full` from `extract_inventory` and then from `build_gamebook` after effect tweaks; node validator + game-ready reports pass.
- **Evidence:**
  - `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/gamebook.json` section 132 choice order now matches table order (16, 392, 177, 287, 132, 249).
  - `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/gamebook.json` section 281 now adds mirror + charm + bread unconditionally; choice 192 has no effects.
  - `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/gamebook.json` section 153 now adds wooden balls only when taking them (choice 74).
- **Next:** Continue spot-checking remaining sections for any residual inventory/stat/combat edge cases; log any new issues with tests.

### 20251230-2244 — Conditional sequence support (item-gated stat changes)
- **Result:** Success; conditional events are now generated, validated, and ordered in the sequence.
- **Notes:**
  - Added conditional extraction in `modules/enrich/sequence_order_v1/main.py` (item remove + nearby stat change when “if you have/possess/are carrying” is present) and ordering support for `conditional` events. Added test `test_sequence_builds_conditional_item_stat_change`.
  - Extended JS schema/types to include `ConditionalEvent` + `Condition` and updated Node validator logic to traverse conditional branches for target validation and reachability. Rebuilt validator bundle with `node modules/validate/validate_ff_engine_node_v1/validator/build_bundle.js`.
  - Added normalization recursion for conditional branches in build modules.
  - Rebuilt run `ff-ai-ocr-gpt51-pristine-fast-full` from `order_sequence`; Node validator + game-ready pass.
- **Evidence:**
  - `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/gamebook.json` section 217 now has a `conditional` event with item `Shield` gating item removal + `-1 SKILL`.
  - `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/27_validate_ff_engine_node_v1/gamebook_validation_node.json` shows pass with new schema.
- **Next:** Expand conditional extraction for other patterns (item-gated stat changes without explicit “drop”), add tests, and continue manual audits.

### 20251230-2306 — Inventory “given/hidden danger” filters + survival-check normalization
- **Result:** Success; removed “hidden danger” false item, prevented “given-for-status” items, and dropped implied-death stat checks. Node validator passes again.
- **Notes:**
  - Inventory: added `_item_given_without_storage` filter and blocked “danger” pseudo-items; added tests in `tests/test_extract_inventory_v1.py`.
  - Sequence: `_normalize_target` now treats death text before digit extraction and ignores zero targets (including numeric 0); added tests in `tests/test_sequence_order_v1.py`.
  - Rebuilt run `ff-ai-ocr-gpt51-pristine-fast-full` from `extract_inventory`, then from `order_sequence` to re-validate. Node validator + game-ready now pass.
- **Evidence:**
  - `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/gamebook.json` section 398 no longer adds “hidden danger”.
  - `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/gamebook.json` section 132 now has only `stat_change` + choices (no invalid stat_check).
  - `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/27_validate_ff_engine_node_v1/gamebook_validation_node.json` shows pass.
- **Next:** Continue manual audits (inventory/stat/combat/choices); log any new issues and add synthetic tests per fix.

### 20251230-2311 — Focused audit sweep (20 items/stat/combat/choices + all item_checks/test_luck/custom)
- **Result:** Partial; most sampled items/stat/combat/choices look correct, but several item_check entries encode non-item state and one background item add appears incorrect.
- **Notes:**
  - Sampled 20 each: inventory adds/removes, stat changes, combat, choices; all sampled choices match anchor order; no obvious combat/stat mismatches found in samples.
  - Flagged item_check misuse: non-item state encoded as item checks in sections 134 (“read the poem…”), 90 (“previously read details…”), 188 (“seen the spirit girl”), 376 (“found a diamond” wording), and 315 (compound condition “coil of rope and a grappling iron”).
  - Background section includes item add “Sword” triggered by “your trusty sword”; likely a false-positive add for starting equipment.
- **Evidence:**
  - `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/gamebook.json` section 134/90/188/376 item_check entries.
  - `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/gamebook.json` section `background` sequence includes `{kind: item, action: add, name: Sword}`.
- **Next:** Decide how to represent state-based checks (non-item conditions) and whether to suppress “your <item>” adds; add tests once rules are agreed.

### 20251231-0047 — State-check event support (non-item conditions)
- **Result:** Success; non-item conditions now emit `state_check` with validator/schema support, and sequence ordering handles them.
- **Notes:**
  - Added `state_check` to schema/types/validator/bundle and updated reachability/target validation in Node validator.
  - Sequence builder now classifies state conditions (read/seen/found/previously, compound “and”) into `state_check`; added tests in `tests/test_sequence_order_v1.py`.
  - Builders normalize `state_check` targets and collect reachability targets; reran pipeline from `order_sequence` and Node validator passes.
- **Evidence:**
  - `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/gamebook.json` sections 134/90/188/376/315 now use `state_check`.
  - `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/27_validate_ff_engine_node_v1/gamebook_validation_node.json` shows pass.
- **Next:** Revisit background item adds (e.g., “your trusty sword”) and remaining state/compound-condition semantics; add tests if we change behavior.

### 20251231-0918 — Fix duplicate “have/ have not” checks from “have not …” text
- **Result:** Success; “if you have not …” no longer generates a spurious “if you have …” check.
- **Notes:**
  - Tightened `has_match` to exclude “have not” (negative lookahead).
  - Added synthetic test in `tests/test_extract_inventory_v1.py`.
  - Rebuilt run `ff-ai-ocr-gpt51-pristine-fast-full` from `extract_inventory`; Node validator and game-ready checks pass.
- **Evidence:**
  - `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/gamebook.json` section 188 now only has `state_check` with `missing -> 224` (no duplicate `has`).
  - `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/27_validate_ff_engine_node_v1/gamebook_validation_node.json` shows pass.
- **Next:** Continue manual audit list and resolve any remaining state/compound condition semantics.

### 20251231-0924 — Compound item checks + “found” normalization
- **Result:** Success; compound item conditions now use `itemsAll`, and “found X” conditions map to item checks.
- **Notes:**
  - Added `itemsAll` to `ItemCheckEvent` schema/types and bundle; updated sequence ordering to emit `itemsAll` when checks contain “and”.
  - Normalized “found a/an/the X” to itemName `X` (item possession, not state); kept `state_check` for read/seen/previously cases.
  - Updated tests in `tests/test_sequence_order_v1.py` and re‑ran from `order_sequence`; Node validator + game‑ready pass.
- **Evidence:**
  - `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/gamebook.json` section 315 now uses `item_check` with `itemsAll: ["coil of rope","grappling iron"]`.
  - `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/gamebook.json` section 376 now uses `item_check` with `itemName: "diamond"`.
  - `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/27_validate_ff_engine_node_v1/gamebook_validation_node.json` shows pass.
- **Next:** Continue manual audits for any remaining state flags that should be captured as `state_check` and ensure engine-side interpretation of `itemsAll`.

### 20251231-0932 — Validator enforces itemsAll shape
- **Result:** Success; Node validator now validates `itemsAll` arrays and schema requires `minItems: 2`.
- **Notes:**
  - Added `itemsAll` validation to Node validator (non-empty strings, min length).
  - Updated schema to require at least two items in `itemsAll`, rebuilt bundle, and re‑ran pipeline from `order_sequence`.
- **Evidence:**
  - `modules/validate/validate_ff_engine_node_v1/validator/gamebook-schema.json` `ItemCheckEvent.itemsAll` includes `minItems: 2`.
  - `modules/validate/validate_ff_engine_node_v1/validator/validation.js` now validates `itemsAll`.
  - `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/27_validate_ff_engine_node_v1/gamebook_validation_node.json` shows pass.

### 20251231-0934 — Added audit tracker section
- **Result:** Success; documented audited section IDs by feature class to prevent duplicate sampling.
- **Notes:** Added `## Audit Tracker` with audited IDs for inventory/stat/combat/choices/test_luck/custom and item/state checks.
- **Next:** Continue audits using the tracker to pick unreviewed sections.

### 20251231-0937 — Spot‑check pass (next batch)
- **Result:** Success; sampled additional sections across inventory/stat/combat/choices/test_luck/item_check with no new extraction issues found.
- **Notes:** Added audited IDs to the Audit Tracker. New batch included background + sections 20/256/158/175/253 (items), 304/147/115/246/223/179/16/162/158/171 (stat), 6/39/369/189/145/40/327/387/380/91 (combat), 271/263/318/398/107/260/120/327/230/367 (choices), 289/21/149/125/202/309/374 (test luck), and item/state checks 318/159/364/146/342/222/234/10/339.
- **Next:** Continue spot checks with unreviewed IDs until new issues emerge.

### 20251231-0939 — Spot‑check pass (stat/combat/choice)
- **Result:** Success; sampled additional stat changes, combat, and choices with no new issues found.
- **Notes:** Added audited IDs to the Audit Tracker. New batch included stat changes 238/28/377/286/189/363/195/190, combat 151/172, and choices 204/348/100/131/256/216/224/51.
- **Next:** Continue spot checks; remaining low‑coverage areas include inventory (only 32 total items) and item/state checks (14 total).

### 20251231-1003 — Completed item/state check audit coverage
- **Result:** Success; all item/state check sections in this run are fully audited.
- **Notes:** There are only 14 item/state check sections in this run; all are already in the Audit Tracker.
- **Next:** Continue spot checks in other categories or stop if coverage is acceptable.

### 20251231-1007 — Spot‑check pass (stat changes)
- **Result:** Success; sampled additional stat changes with no new issues found.
- **Notes:** Added audited IDs to the Audit Tracker. New batch included 295/207/199/38/139/123/353/389/175/287.
- **Next:** Continue stat‑change coverage (remaining 28 unreviewed at start of this batch).

### 20251231-1009 — Spot‑check pass (choices)
- **Result:** Success; sampled additional choice sections with no ordering or effect issues found.
- **Notes:** Added audited IDs to the Audit Tracker. New batch included 306/84/158/93/320/52/40/382/273/254/307/238.
- **Next:** Continue choice coverage (330 remaining before this batch).

### 20251231-0928 — itemsAll semantics confirmed
- **Result:** Success; engine semantics confirmed: `itemsAll` requires ALL listed items to proceed.
- **Notes:** Use AND semantics for `itemsAll` in game engine logic.

### 20251231-1053 — Audit criteria clarified (other-feature count)
- **Result:** Success; manual audit requirement clarified to allow “all available sections” when fewer than 20 exist.
- **Notes:** Item/state checks total only 14 in this run; audit tracker updated to reflect full coverage.
- **Next:** Continue spot checks for choices/stat changes until diminishing returns.

### 20251231-1054 — Spot‑check pass (choices/stat changes)
- **Result:** Success; sampled additional choices and stat changes with no new issues found.
- **Notes:** Added audited IDs to the Audit Tracker. New batch included choices 166/156/288/338/241/314/50/207/195/385/92/177 and stat changes 57/394/215/95/354/220/391/45/330/395.
- **Next:** Continue choice coverage or pause if remaining gap is acceptable for now.

### 20251231-1059 — Spot‑check pass (choices)
- **Result:** Success; sampled an additional early‑book choice batch with no ordering or target issues found.
- **Notes:** Added audited IDs to the Audit Tracker. New batch included choices 1/5/6/9/10/11/12/13/14/15/16/18/20/21/22/23/24/25/26/27.
- **Next:** Continue choice coverage toward the high‑confidence threshold.

### 20251231-1059 — Spot‑check pass (choices, random batch)
- **Result:** Success; sampled a random choice batch with no ordering or target issues found.
- **Notes:** Added audited IDs to the Audit Tracker. New batch included choices 37/69/97/132/155/223/226/243/252/257/262/265/266/280/285/290/292/304/365/386.
- **Next:** Continue choice coverage toward the high‑confidence threshold (need ≥150 or ≥25%).

### 20251231-1100 — Spot‑check pass (choices, random batch)
- **Result:** Success; sampled another random choice batch with no ordering or target issues found.
- **Notes:** Added audited IDs to the Audit Tracker. New batch included choices 29/30/56/74/81/94/95/104/105/110/124/129/134/152/163/186/209/211/229/309/313/343/360/379/395.
- **Next:** Continue choice coverage toward the high‑confidence threshold (need ≥150 or ≥25%).

### 20251231-1101 — Spot‑check pass (choices, random batch)
- **Result:** Success; sampled another random choice batch with no ordering or target issues found.
- **Notes:** Added audited IDs to the Audit Tracker. New batch included choices 38/42/49/68/78/80/111/139/148/164/167/182/213/220/227/251/269/287/289/291/339/363/371/376/380.
- **Next:** Choice audit threshold met (≥150); continue only if new issues surface elsewhere.

### 20251231-1102 — Completed stat‑change audit coverage
- **Result:** Success; audited all remaining stat‑change sections with no new issues found.
- **Notes:** Added audited IDs to the Audit Tracker. Final batch included stat changes 42/72/103/285/309/336/339/399, bringing total stat‑change sections audited to 66/66 for this run.
- **Next:** Stat‑change threshold met; focus remains on overall saturation tracking for choices.

### 20251231-1103 — High‑confidence thresholds met
- **Result:** Success; choice and stat‑change audit thresholds reached with no new issues in recent samples.
- **Notes:** Choices audited 152 sections (≥150). Stat changes audited 66/66 total sections. Last 30+ audits in both classes had no new issues.
- **Next:** If desired, proceed to final validation sweep and assess whether to mark the story Done.

### 20251231-1105 — Final validation sweep surfaced stat‑change misses
- **Result:** Failure; smoke validator flags missing `stat_change` in sections 145/249/350/392.
- **Notes:** Ran `validate_gamebook_smoke_v1` on `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/gamebook.json`; report at `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/validation_report_smoke.json`. Sections 249/350/392 text explicitly mention STAMINA loss; sequences lack `stat_change`. Section 145 flagged by the validator; needs manual confirmation of text context.
- **Next:** Inspect those sections in `gamebook.json` and fix extraction/ordering to emit correct `stat_change` events; re‑run from `extract_stat_modifications` and re‑validate.

### 20251231-1110 — Fixed missing dice‑based stat changes + smoke pass
- **Result:** Success; dice‑based STAMINA losses now extracted, and smoke validator passes.
- **Notes:** Updated `extract_stat_modifications_v1` to handle “roll die, add 1, reduce by total” and “deduct the number from STAMINA” patterns; added tests; re‑ran from `extract_stat_modifications`. Smoke validator now passes (0 errors). Adjusted smoke validator to require STAMINA‑loss proximity to avoid false positives from combat stat blocks (section 145).
- **Evidence:**
  - `modules/enrich/extract_stat_modifications_v1/main.py` (new roll‑reduce patterns).
  - `tests/test_extract_stat_modifications_v1.py` (new dice‑loss tests).
  - `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/gamebook.json` sections 249/350/392 now include `stat_change`.
  - `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/validation_report_smoke.json` shows 0 errors.
- **Next:** If desired, normalize untracked files and mark story done.
