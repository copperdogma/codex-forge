# Story: Edge-Case Scanner + Patch Module (Post-Extraction)

**Status**: Done

---

## Problem Statement

Even with generalized extraction rules, some books will contain rare or book-specific mechanics that are too brittle to handle with global heuristics. We need a dedicated post-extraction scanner that identifies likely edge cases, routes them to targeted AI analysis, and writes deterministic patch artifacts that repair the gamebook output without baking book-specific hacks into core modules.

## Goals

- Detect edge cases after the gamebook is assembled (combat, checks, choices, stat mods, etc.).
- Escalate only flagged sections to AI for structured interpretation.
- Emit a patch artifact keyed by section/event id with explicit edits.
- Apply patches in a dedicated module to keep core extraction generic.
- Make patch generation repeatable, auditable, and reversible.
- Track every “turn to X” link early, then mark links as handled by downstream modules; surface unhandled links as high-confidence edge cases.

## Acceptance Criteria

- [x] Scanner produces a structured report of candidate edge cases with reason codes and pointers to source artifacts.
- [x] AI verification is only invoked for flagged sections, defaults to no-change unless explicit evidence, and returns structured patch entries when required.
- [x] AI patching logs section-level verification metrics (reviewed, no-change, patched, low-confidence).
- [x] Patch artifact format is documented and versioned.
- [x] Patch apply module runs after build_gamebook and updates the final gamebook deterministically.
- [x] Patch application is idempotent and logs every change (before/after diff)
- [x] Patch application is optional and recipe-controlled (opt-in).
- [ ] At least one real book run demonstrates detection + patching of a combat edge case.
- [x] “Turn to X” link tracking exists: early extraction produces per-section link set; downstream modules explicitly mark links as claimed; final report lists unclaimed links per section with pointers.

## Tasks

- [x] Define edge-case signals per mechanic (combat, stat checks, choices, stat mods, inventory).
- [x] Add a scanner module that consumes `gamebook.json` and emits a JSONL report with reason codes and pointers.
- [x] Draft patch schema (target path, operation, provenance, AI rationale).
- [x] Update AI analysis module to verify current JSON against HTML, returning empty patches when correct.
- [x] Record AI verification metrics (reviewed/no-change/patch/low-confidence) in run logs.
- [x] Implement patch apply module (post-build) that applies patch entries to gamebook.
- [x] Add recipe hook/flag for patch application.
- [x] Add tests for patch schema + idempotent patch application.
- [x] Update docs with patch workflow and recommended usage.
- [x] Design and implement early `turn_to_links` extraction (anchor-derived) in portionization.
- [x] Add explicit link-claiming in downstream modules (choices/combat/luck/etc.).
- [x] Emit a report of unclaimed links per section and wire it into edgecase scanning.

## Design: Turn-to Link Tracking (Option A)

**Goal:** Capture all “turn to X” targets early, then let downstream modules claim targets they encode. Unclaimed targets become high-confidence edge cases.

**Artifacts**
- `turn_to_links.jsonl` (`turn_to_links_v1`): one row per section with `section_id`, `pageStart`, `pageEnd`, and a list of `links` (target + source + snippet).
- `turn_to_link_claims.jsonl` (`turn_to_link_claims_v1`): one row per claimed target with `section_id`, `target`, `claim_type`, `evidence_path`, `module_id`.
- `turn_to_unclaimed.jsonl` (`turn_to_unclaimed_v1`): a single report row with summary counts and issue list (section_id + target + sources).

**Tracker extraction rules**
- Parse anchors only: `<a href="#123">` → target 123 (anchor-derived source of truth).

**Reconciliation**
- For each section, unclaimed = (all targets) - (claimed targets).
- Emit report with `reason_code: unclaimed_turn_to` for edgecase scanner integration.
- [ ] Manually verify all flagged special combat sections (combat correctness vs HTML).
  - [x] Section 91
  - [x] Section 124
  - [x] Section 130
  - [x] Section 143
  - [x] Section 145
  - [x] Section 148
  - [x] Section 151
  - [x] Section 166
  - [x] Section 172
  - [x] Section 189
  - [x] Section 225
  - [x] Section 236
  - [x] Section 294
  - [x] Section 327
  - [x] Section 369
  - [x] Section 380

## Work Log

<!-- Append-only log entries. -->

### 20260102-1104 — Created story stub for edge-case scanner + patch workflow
- **Result:** Success.
- **Notes:** Added problem statement, acceptance criteria, and tasks for a post-extraction edge-case scanner and patch module.
- **Next:** Prioritize signal definitions and draft patch schema.

### 20260102-1322 — Implemented edge-case scanner v1 and wired Story 111 signals
- **Result:** Success.
- **Notes:** Added `edgecase_scanner_v1` module to scan `gamebook.json` and emit `edgecase_scan_v1` report with reason codes (survival gate, conditional branches, dual checks, dice damage without branch, terminal outcomes, multi-item requirements). Added schema + validation mapping and unit tests.
- **Next:** Draft patch schema + apply module; add recipe hook for optional patching; run scanner on a real book and inspect report output.

### 20260102-1334 — Added patch schema + apply module and idempotency tests
- **Result:** Success.
- **Notes:** Added `edgecase_patch_v1` + `edgecase_patch_report_v1` schemas, implemented `apply_edgecase_patches_v1` module to apply JSONL patches to `gamebook.json` with before/after reporting and idempotent checks. Added unit tests for add/replace/remove and idempotent skip behavior.
- **Next:** Add recipe hook/flag for patch application and implement AI analysis module that generates patch JSONL from scanner output.

### 20260102-1339 — Added resume recipe hook for edgecase scan + patch
- **Result:** Success.
- **Notes:** Added `configs/recipes/recipe-ff-ai-ocr-gpt51-resume-edgecase-scan.yaml` with optional patch application (`allow-missing`) for post-build patching.
- **Next:** Implement AI analysis module and run scanner on a real book to inspect report output.

### 20260102-1331 — Implemented AI patch generator module
- **Result:** Success.
- **Notes:** Added `edgecase_ai_patch_v1` to generate `edgecase_patch_v1` JSONL from scan issues using targeted prompts; wired into resume recipe before patch application.
- **Next:** Run scanner + AI patch pipeline on a real book and inspect `edgecase_scan.jsonl` and `edgecase_patch_report.jsonl`.

### 20260102-1331 — Ran edgecase scanner/apply unit tests
- **Result:** Success.
- **Notes:** `pytest tests/test_edgecase_scanner_v1.py tests/test_edgecase_patch_apply_v1.py`
- **Next:** Execute resume edgecase scan recipe against a real run and manually inspect outputs.

### 20260102-1354 — Ran resume edgecase scan + AI patch on real run and inspected outputs
- **Result:** Partial success.
- **Notes:** Run `edgecase-scan-20260102b` via `configs/recipes/recipe-ff-ai-ocr-gpt51-resume-edgecase-scan.yaml` against `ff-ai-ocr-gpt51-pristine-fast-full-vnext-20260101f`. Artifacts:
  - `output/runs/edgecase-scan-20260102b/02_edgecase_scanner_v1/edgecase_scan.jsonl` (51 issues).
  - `output/runs/edgecase-scan-20260102b/03_edgecase_ai_patch_v1/edgecase_patches.jsonl` (3 terminal_outcome_text patches).
  - `output/runs/edgecase-scan-20260102b/04_apply_edgecase_patches_v1/edgecase_patch_report.jsonl` (3 applied).
  - `output/runs/edgecase-scan-20260102b/04_apply_edgecase_patches_v1/gamebook_patched.json` (patched).
  - Manual verification: sections 7/17/19 now include `death` events with `terminal.kind: "death"` in `gamebook_patched.json`.
- **Next:** Expand AI patching to handle more issue codes (or allow manual triage), and demonstrate a combat edge-case patch as required by Acceptance Criteria.

### 20260102-1406 — Tightened edgecase scanner to avoid low-risk flags
- **Result:** Success.
- **Notes:** Removed terminal-outcome phrase flagging and added sequence-kind gating so issues only emit when related structured events are missing (choices, item/state checks, luck/skill, stat changes). Updated `modules/adapter/edgecase_scanner_v1/main.py` accordingly.
- **Next:** Re-run resume scan on the same run to confirm reduced false positives and identify true high-risk cases.

### 20260102-1410 — Re-ran edgecase scan with tighter gating
- **Result:** Success (no issues flagged).
- **Notes:** Resume run on `edgecase-scan-20260102b` (`--start-from scan_edgecases`) now yields 0 issues after gating by existing sequence kinds.
- **Next:** Refine scanner to target truly complex mechanics (combat special rules, multi-stage checks) instead of broad pattern matches.

### 20260102-1415 — Added complexity scoring + special combat flagging
- **Result:** Success.
- **Notes:** Scanner now emits `high_complexity` when score ≥ 5 and always flags `special_combat` (combat with special rules, extra metadata, or multiple enemies). Added text signals for test-your-luck, one-at-a-time, roll-die, and multi-item phrases.
- **Next:** Re-run resume scan and inspect flagged sections to validate targeting.

### 20260102-1416 — Refined special combat detection to reduce false positives
- **Result:** Success.
- **Notes:** Treats combat as special only when `mode != single`, multiple enemies, explicit `rules/modifiers/triggers`, or special_rules. Removed generic "extra keys" check (which incorrectly flagged normal combats using `mode`).
- **Next:** Re-run resume scan and inspect new issue counts.

### 20260102-1417 — Re-ran scan with complexity + special combat gating
- **Result:** Success.
- **Notes:** Resume scan on `edgecase-scan-20260102b` now flags 17 issues: 16 `special_combat`, 1 `high_complexity` (section 189). AI patch stage produced 1 patch for section 145 (`/sections/145/sequence/0/modifiers/0`).
- **Next:** Inspect flagged special combats to confirm true edge cases and decide which should be escalated to AI patching.

### 20260102-1426 — Switched AI patcher to verification-first flow
- **Result:** Success.
- **Notes:** Updated `edgecase_ai_patch_v1` prompt to verify JSON vs HTML and return empty patches when correct; added confidence gating (only apply patches when confidence=high) and metrics (reviewed/no-change/patched/low-confidence) in run logs. Added unit tests in `tests/test_edgecase_ai_patch_v1.py`.
- **Next:** Run resume edgecase scan + AI verify on a real run and inspect metrics + patch output.

### 20260102-1430 — Ran AI verification and captured metrics
- **Result:** Success.
- **Notes:** Resume run on `edgecase-scan-20260102b` produced 0 patches. Metrics file `output/runs/edgecase-scan-20260102b/03_edgecase_ai_patch_v1/edgecase_ai_patch_metrics.json` shows 5 sections processed, 5 no-change, 0 patched, 0 low-confidence.
- **Next:** Review flagged special combats to confirm true mismatches and expand AI verification to more sections if needed.

### 20260102-1433 — Verified 16 flagged sections with max-sections=20
- **Result:** Success.
- **Notes:** Set `max-sections: 20` and reran resume scan; AI verification processed 16 sections (all flagged special combats). Metrics: 16 no-change, 0 patched, 0 low-confidence in `output/runs/edgecase-scan-20260102b/03_edgecase_ai_patch_v1/edgecase_ai_patch_metrics.json`.
- **Next:** Decide whether to expand AI verification beyond special combats or adjust scanner signals for more coverage.

### 20260102-1436 — Manually reviewed flagged special combats vs HTML
- **Result:** Partial success.
- **Notes:** Reviewed special-combat sections using `output/runs/ff-ai-ocr-gpt51-pristine-fast-full-vnext-20260101f/gamebook.json` (HTML + sequence). Marked correct: 91, 124, 130, 145, 151, 166, 172, 189, 225, 236, 294, 380. Suspect mismatches:
  - 143: HTML shows trigger “Attack Strength totals 22 → 2” and link to 163, but no explicit “if you lose → 2”; current JSON includes `lose → 2`.
  - 148: HTML shows “If you win, turn to 175 315” without explicit lose clause; JSON includes `lose → 315`.
  - 327: HTML shows “If Mirror Demon’s Attack Strength is greater… turn to 8 92” without explicit win clause; JSON includes `win → 92` and `lose → 8`.
  - 369: Text indicates Throm fights one Cave Troll while you fight the other; JSON models two enemies (`split-target`), likely incorrect for player combat.
- **Next:** Decide how to resolve the four suspect sections (manual correction vs AI verification with more explicit prompt) and update patches accordingly.

### 20260102-1455 — Added turn-to link tracking requirement + tasks
- **Result:** Success.
- **Notes:** Added requirement to extract all “turn to X” links early, track claims by downstream modules, and surface unclaimed links as edge cases. Added tasks to design a link tracker, claim marking, and unclaimed-link report integration.
- **Next:** Identify the earliest viable stage to compute link sets (likely after HTML normalization) and decide how to represent link claims across modules.

### 20260102-1503 — Added turn-to link tracker + reconciler modules (spec + tests)
- **Result:** Success.
- **Notes:** Implemented `turn_to_link_tracker_v1` and `turn_to_link_reconciler_v1` modules, added schemas (`turn_to_links_v1`, `turn_to_link_claims_v1`, `turn_to_unclaimed_v1`), and wired optional unclaimed merge into `edgecase_scanner_v1`. Added unit tests for tracker/reconciler.
- **Next:** Run module tests and decide where to insert tracker + reconciler in a resume recipe; update docs with workflow guidance.

### 20260102-1503 — Ran unit tests for turn-to link tracker/reconciler
- **Result:** Success.
- **Notes:** `pytest tests/test_turn_to_link_tracker_v1.py tests/test_turn_to_link_reconciler_v1.py`
- **Next:** Add a resume recipe stage to emit `turn_to_links.jsonl` and `turn_to_unclaimed.jsonl`, then rerun edgecase scanner with `--unclaimed`.

### 20260102-1509 — Wired turn-to tracker/reconciler into resume recipe and ran
- **Result:** Success (baseline run, no claims yet).
- **Notes:** Updated `recipe-ff-ai-ocr-gpt51-resume-edgecase-scan.yaml` to run `turn_to_link_tracker_v1` and `turn_to_link_reconciler_v1` before `edgecase_scanner_v1`, and pass unclaimed links via `--inputs`. Resume run `edgecase-scan-20260102b` produced:
  - `output/runs/edgecase-scan-20260102b/02_turn_to_link_tracker_v1/turn_to_links.jsonl` (401 sections)
  - `output/runs/edgecase-scan-20260102b/03_turn_to_link_reconciler_v1/turn_to_unclaimed.jsonl` (1078 unclaimed)
  - `output/runs/edgecase-scan-20260102b/04_edgecase_scanner_v1/edgecase_scan.jsonl` (1095 issues total, dominated by unclaimed links)
- **Next:** Implement link-claim emission in downstream modules to reduce unclaimed count before using this signal for AI verification.

### 20260102-1514 — Added gamebook-based link claims and reran reconciliation
- **Result:** Success (baseline claims).
- **Notes:** Added `turn_to_link_claims_from_gamebook_v1` (claims from gamebook sequence targets) and wired it into the resume recipe. Rerun `edgecase-scan-20260102b` from `load_gamebook` produced:
  - `output/runs/edgecase-scan-20260102b/03_turn_to_link_claims_from_gamebook_v1/turn_to_link_claims.jsonl` (637 claims)
  - `output/runs/edgecase-scan-20260102b/04_turn_to_link_reconciler_v1/turn_to_unclaimed.jsonl` (0 unclaimed; links_total 1078)
- **Next:** Decide whether to emit claims from upstream modules (choices/combat/luck) to identify mismatched semantics, since gamebook-level claims only prove the target exists, not that the logic is correct.

### 20260102-1527 — Moved turn-to tracking to pre-gamebook portions + portion-based claims
- **Result:** Success.
- **Notes:** Updated `turn_to_link_tracker_v1` to accept portions JSONL (`raw_text`/`raw_html`) and added `turn_to_link_claims_from_portions_v1` to emit claims from choices/test_luck/stat_checks/inventory/combat. Resume run from `load_enriched_portions` produced:
  - `output/runs/edgecase-scan-20260102b/03_turn_to_link_tracker_v1/turn_to_links.jsonl` (links_total 619)
  - `output/runs/edgecase-scan-20260102b/04_turn_to_link_claims_from_portions_v1/turn_to_link_claims.jsonl` (632 claims)
  - `output/runs/edgecase-scan-20260102b/05_turn_to_link_reconciler_v1/turn_to_unclaimed.jsonl` (unclaimed_total 0)
- **Next:** Reduce over-claiming (choices currently claim most links) or introduce claim-type validation to surface misclassification (e.g., combat vs choice).

### 20260102-1534 — Reordered recipes to run extract_choices last
- **Result:** Success.
- **Notes:** Moved `extract_choices_relaxed_v1` (and repair/validation) after combat/inventory/stat modules in `recipe-ff-ai-ocr-gpt51.yaml`, `recipe-ff-ai-ocr-gpt51-pristine-fast.yaml`, `recipe-ff-ai-ocr-gpt51-old-fast.yaml`, and `recipe-ff-smoke.yaml`. Updated downstream dependencies for `validate_reachability` and `ending_guard_v1` to consume `validate_choice_links` output.
- **Next:** Validate on a resume run (from `extract_combat` or later) to ensure downstream modules still receive expected fields.

### 20260102-1545 — Resumed canonical run from extract_combat after reorder
- **Result:** Partial success (validation failed at end).
- **Notes:** Resumed `ff-ai-ocr-gpt51-pristine-fast-full` from `extract_combat` using updated recipe ordering. Pipeline reached `validate_choice_completeness_v1` and failed with 85 flagged sections (choices missing for text refs). Artifacts updated through `gamebook.json` in `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/`.
- **Next:** Decide whether to update `validate_choice_completeness_v1` to account for non-choice mechanics (combat/luck) or keep it as a strict guard and adjust extraction outputs accordingly.

### 20260102-1607 — Embedded turn_to_links into portions and gamebook
- **Result:** Success (pipeline run completes; choice completeness still fails as before).
- **Notes:** Added `turn_to_links` to `EnrichedPortion` schema and propagate into gamebook sections via `build_ff_engine_with_issues_v1`. `turn_to_link_tracker_v1` now annotates portions directly (output is `enriched_portion_v1`). Resume run from `extract_turn_to_links` wrote new `gamebook.json` with `turn_to_links` present (e.g., section 16 has anchor targets). Validation still fails at `validate_choice_completeness_v1` with 85 flagged sections.
- **Next:** Decide how to handle choice completeness validation now that non-choice mechanics are extracted before choices.

### 20260102-1612 — Dropped turn_to_links snippet field
- **Result:** Success.
- **Notes:** `turn_to_link_tracker_v1` no longer emits `snippet` for links; only `target` and `source` remain to reduce noise and duplication.
- **Next:** Decide whether to keep `source` or collapse to target-only links.

### 20260102-1629 — Simplified turn_to_links to target-only anchors
- **Result:** Success.
- **Notes:** `turn_to_links` now stores only targets (anchor-derived), no `source`/`snippet`. Tracker now parses anchors only. Resumed run from `extract_turn_to_links` updated `gamebook.json` with target-only arrays (e.g., section 16 has `['16','392','177','287','132','249']`).
- **Next:** Decide whether to keep a separate text-pattern pass or rely solely on HTML anchors as source of truth.

### 20260102-1632 — Merged turn_to_links into portionize_html_extract_v1
- **Result:** Success.
- **Notes:** `portionize_html_extract_v1` now extracts anchor targets directly into `turn_to_links` and the separate `turn_to_link_tracker_v1` stage was removed from recipes. Added unit coverage for anchor extraction in portionize module.
- **Next:** Rerun a resume pipeline from `portionize_html` (or later) to confirm downstream modules consume `turn_to_links` without the tracker stage.

### 20260102-1641 — Resumed canonical run from portionize_html after merge
- **Result:** Partial success (validation failed).
- **Notes:** Ran `ff-ai-ocr-gpt51-pristine-fast-full` from `portionize_html` to end. Pipeline completed through `gamebook.json` and Node validation, but failed at `validate_choice_completeness_v1` with 85 flagged sections (same as before). Outputs updated in `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/` including `10_portionize_html_extract_v1/portions_enriched.jsonl` (now with `turn_to_links`) and `gamebook.json`.
- **Next:** Decide whether to adjust `validate_choice_completeness_v1` to account for non-choice mechanics or leave it strict and fix extraction outputs.

### 20260102-1648 — Updated choice completeness validator to count mechanic claims
- **Result:** Success (code change only).
- **Notes:** `validate_choice_completeness_v1` now compares `turn_to_links` (or text refs) against all `targetSection` claims in `sequence` plus legacy `choices`, instead of choices only. This should eliminate false failures for combat/luck/stat outcomes.
- **Next:** Rerun the pipeline from `validate_choice_completeness` (or `build_gamebook`) to confirm flag count drops appropriately.

### 20260102-1650 — Reran choice completeness validation after update
- **Result:** Success.
- **Notes:** Resumed `ff-ai-ocr-gpt51-pristine-fast-full` from `validate_choice_completeness`. Validator now reports 0 flagged sections. `validate_game_ready_v1` passes and packaging completed. Reports at `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/28_validate_choice_completeness_v1/choice_completeness_report.json` and `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/29_validate_game_ready_v1/game_ready_validation_report.json`.
- **Next:** Decide whether to add tests for validator coverage (sequence outcomes + turn_to_links) and whether to keep text-ref fallback long-term.

### 20260102-1650 — Added unit tests for choice completeness coverage
- **Result:** Success.
- **Notes:** Added `tests/test_validate_choice_completeness_v1.py` to cover turn_to_links + combat outcomes, missing claims, and text fallback.
- **Next:** Run the new unit test or include it in the next test batch.

### 20260102-1658 — Added explicit turn_to claim marking in extractors
- **Result:** Success (code change only).
- **Notes:** Added `turn_to_claims` to `EnrichedPortion` and populated it in `extract_combat_v1`, `extract_stat_checks_v1`, `extract_inventory_v1`, and `extract_choices_relaxed_v1`. Updated `turn_to_link_claims_from_portions_v1` to emit explicit claims when present, plus a unit test for explicit claims.
- **Next:** Resume a pipeline from `extract_combat` (or later) and confirm claims flow through `turn_to_link_claims_from_portions_v1` and unclaimed reporting.

### 20260102-1659 — Ran turn_to_link_claims unit tests
- **Result:** Success.
- **Notes:** `pytest tests/test_turn_to_link_claims_from_portions_v1.py`
- **Next:** Resume edgecase scan recipe to confirm explicit claims flow into unclaimed reporting.

### 20260102-1709 — Resumed pipeline and edgecase scan with explicit claims
- **Result:** Success (edgecase scan completed; 0 unclaimed).
- **Notes:** Resumed `ff-ai-ocr-gpt51-pristine-fast-full` from `extract_combat` to regenerate portions with `turn_to_claims`. Then ran `edgecase-scan-20260102c` (resume recipe). Artifacts:
  - `output/runs/edgecase-scan-20260102c/03_turn_to_link_claims_from_portions_v1/turn_to_link_claims.jsonl` (718 claims)
  - `output/runs/edgecase-scan-20260102c/04_turn_to_link_reconciler_v1/turn_to_unclaimed.jsonl` (0 unclaimed)
  - `output/runs/edgecase-scan-20260102c/05_edgecase_scanner_v1/edgecase_scan.jsonl` (25 issues)
  - `output/runs/edgecase-scan-20260102c/06_edgecase_ai_patch_v1/edgecase_patches.jsonl` (0 patches)
- **Next:** Review edgecase scan issues for remaining triggers and wire unclaimed report into scanner output if any unclaimed appear in other runs.

### 20260102-1711 — Documented edgecase scanner + patch workflow
- **Result:** Success.
- **Notes:** Added a concise workflow section and resume recipe usage to `README.md`.
- **Next:** Review remaining edgecase scan issues (25) and decide which warrant AI verification/patching.

### 20260102-1719 — Reran pipeline from extract_combat after claim coercion fix
- **Result:** Success.
- **Notes:** Resumed `ff-ai-ocr-gpt51-pristine-fast-full` from `extract_combat` after fixing `turn_to_claims` serialization. Pipeline completed end-to-end with no serializer warnings; `validate_choice_completeness_v1` passes (0 flagged).
- **Next:** Decide whether to re-run the edgecase scan to reflect refreshed artifacts and then review the 25 flagged issues.

### 20260102-1725 — Reran edgecase scan after claim serialization fix
- **Result:** Success.
- **Notes:** Ran `edgecase-scan-20260102d` using the resume recipe. Artifacts:
  - `output/runs/edgecase-scan-20260102d/03_turn_to_link_claims_from_portions_v1/turn_to_link_claims.jsonl` (783 claims)
  - `output/runs/edgecase-scan-20260102d/04_turn_to_link_reconciler_v1/turn_to_unclaimed.jsonl` (0 unclaimed)
  - `output/runs/edgecase-scan-20260102d/05_edgecase_scanner_v1/edgecase_scan.jsonl` (25 issues)
  - `output/runs/edgecase-scan-20260102d/06_edgecase_ai_patch_v1/edgecase_patches.jsonl` (0 patches)
- **Next:** Review the 25 remaining edgecase issues and decide whether to manually correct or enable AI patches.

### 20260102-1728 — Manual review of conditional-branch and high-complexity issues
- **Result:** Success (no corrections needed).
- **Notes:** Inspected `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/gamebook.json` for sections flagged by edgecase scan: 10, 146, 159, 234, 315, 318, 342, 364 (conditional_choice_branch) and 189 (high_complexity). All conditional branches are correctly represented as `item_check` events with matching `has`/`missing` targets; section 189 correctly includes `stat_change` and a sequential combat with win→257. No patches required.
- **Next:** Decide whether to adjust the scanner to suppress conditional_choice_branch when an `item_check` already encodes the branch.

### 20260102-1730 — Suppressed conditional_choice_branch when item checks exist
- **Result:** Success.
- **Notes:** Updated `edgecase_scanner_v1` to avoid matching `if you do not...` as a positive branch and to skip conditional-choice flags when an `item_check` already exists. This reduces false positives for inventory-gated branches.
- **Next:** Rerun edgecase scan to confirm conditional_choice_branch count drops.

### 20260102-1731 — Reran edgecase scan after conditional-branch suppression
- **Result:** Success.
- **Notes:** Ran `edgecase-scan-20260102e`. Issue count dropped to 17 (all special_combat + 1 high_complexity). No unclaimed links and no patches generated.
- **Next:** Decide whether to keep special_combat as informational-only or tighten further (e.g., only when rules/modifiers/triggers present).

### 20260102-1741 — Tightened special_combat to rules/modifiers/triggers only
- **Result:** Success.
- **Notes:** `edgecase_scanner_v1` now flags special combats only when explicit `rules`, `modifiers`, or `triggers` (or per-enemy special_rules) are present, not merely multi-enemy or non-single mode.
- **Next:** Rerun edgecase scan to confirm special_combat count drops.

### 20260102-1742 — Reran edgecase scan after special_combat tightening
- **Result:** Success.
- **Notes:** Ran `edgecase-scan-20260102f`. Issue count dropped to 16. No unclaimed links and no patches generated.
- **Next:** Review remaining special_combat/high_complexity flags to decide if any should still trigger AI verification.

### 20260102-1746 — Marked AI verification/metrics/schema tasks complete
- **Result:** Success.
- **Notes:** Checked off AI verification + metrics tasks in the story and confirmed patch schema/versioning is documented via `edgecase_patch_v1` schema and tests.
- **Next:** Decide if story is ready to mark Done or if additional refinement is needed.

### 20260102-1844 — Refined split-target combat handling and reran from extract_combat
- **Result:** Success.
- **Notes:** Tightened ally-assisted pruning to avoid false positives and fixed split-target expansion to ignore generic “two creatures” phrasing and expand known parts (e.g., pincers). Reran pipeline from `extract_combat` in `ff-ai-ocr-gpt51-pristine-fast-full` and manually verified sections 143/148/327/369 in `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/gamebook.json`:
  - 143 now has split-target with two pincer enemies, trigger for Attack Strength 22 → 2, win → 163.
  - 148 includes escape → 315 and sequential dogs.
  - 327 encodes enemy_round_win trigger → 8 and win → 92.
  - 369 is a single CAVE TROLL with win → 288.
  - Validator emitted a new “suspicious link” warning for 11→140 during `validate_choice_links`; needs triage.
- **Next:** Confirm whether the 11→140 suspicion is a real error or a validator false positive, then decide if any additional combat edgecases require AI escalation.

### 20260102-2219 — Reran edgecase scan after combat fixes
- **Result:** Success.
- **Notes:** Ran resume scan `edgecase-scan-20260102g` after combat extraction adjustments. Artifacts:
  - `output/runs/edgecase-scan-20260102g/03_turn_to_link_claims_from_portions_v1/turn_to_link_claims.jsonl` (780 claims)
  - `output/runs/edgecase-scan-20260102g/04_turn_to_link_reconciler_v1/turn_to_unclaimed.jsonl` (0 unclaimed)
  - `output/runs/edgecase-scan-20260102g/05_edgecase_scanner_v1/edgecase_scan.jsonl` (16 issues)
  - `output/runs/edgecase-scan-20260102g/06_edgecase_ai_patch_v1/edgecase_patches.jsonl` (0 patches from 15 sections)
  - `output/runs/edgecase-scan-20260102g/07_apply_edgecase_patches_v1/gamebook_patched.json` (no changes)
- **Next:** Review remaining 16 issues and decide if any should be escalated to AI verification or adjusted in scan heuristics.

### 20260102-2225 — Reviewed 16 edgecase sections; added regression test
- **Result:** Success.
- **Notes:** Inspected `output/runs/edgecase-scan-20260102g/05_edgecase_scanner_v1/edgecase_scan.jsonl` and compared each flagged section with `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/gamebook.json`. All special_combat sections match the HTML. Section 189’s “Lose 3 STAMINA points” is present in the current gamebook sequence, so no extraction fix needed; added a regression test for simple lose‑points phrasing in `tests/test_extract_stat_modifications_v1.py`.
- **Next:** Decide if any remaining special_combat sections need AI verification beyond the current scan rules.

### 20260102-2236 — Synthetic patch demo via driver.py
- **Result:** Success.
- **Notes:** Created a synthetic gamebook + patch in `output/runs/edgecase-scan-synthetic-20260102a/inputs/` and ran `driver.py` with `configs/recipes/recipe-edgecase-patch-synthetic.yaml`. Patch applied to `output/runs/edgecase-scan-synthetic-20260102a/02_apply_edgecase_patches_v1/gamebook_patched.json` (choiceText changed to “Run away”).
- **Next:** Decide if Acceptance Criteria should accept this synthetic patch demo as sufficient for the combat‑edgecase requirement.

### 20260102-2245 — Integrated patch apply into canonical recipes
- **Result:** Success.
- **Notes:** Added `apply_edgecase_patches_v1` after `clean_presentation` in `recipe-ff-ai-ocr-gpt51.yaml`, `recipe-ff-ai-ocr-gpt51-pristine-fast.yaml`, `recipe-ff-ai-ocr-gpt51-old-fast.yaml`, and `recipe-ff-smoke.yaml`. Downstream validators now read `gamebook_patched.json` so patch application runs post-build and feeds final validation/packaging.
- **Next:** Decide if we should also add a non-resume edgecase scan stage to the canonical recipes or keep patch application opt-in via external patch files.

### 20260102-2249 — Coerced inventory turn_to_claims and ran stat-mod tests
- **Result:** Success.
- **Notes:** Added `TurnToLinkClaimInline` coercion for inventory claims in `modules/enrich/extract_inventory_v1/main.py` to address Pydantic serializer warnings; ran `python -m pytest tests/test_extract_stat_modifications_v1.py` (10 passed, 2 Pydantic deprecation warnings).
- **Next:** Rerun from `extract_combat` in the resume recipe to confirm no turn_to_claims warnings remain.

### 20260102-2256 — Reran pipeline from extract_combat to validate turn_to_claims
- **Result:** Partial success (pipeline aborted at packaging).
- **Notes:** Ran `python driver.py --recipe configs/recipes/recipe-ff-ai-ocr-gpt51-pristine-fast.yaml --output-dir output/runs/ff-ai-ocr-gpt51-pristine-fast-full --allow-run-id-reuse --start-from extract_combat`. No Pydantic turn_to_claims serializer warnings observed during extract_inventory/stat_checks. `validate_choice_links_v1` still flags suspicious links 11→140 and 392→177. Pipeline failed at `package_game_ready_v1` due to missing recipe snapshot under `26_apply_edgecase_patches_v1/snapshots/recipe.yaml` (see traceback in run output).
- **Next:** Decide whether to address the packaging snapshot lookup (e.g., pass `--recipe` or adjust snapshot location) or treat as expected when resuming mid‑pipeline.

### 20260102-2259 — Fixed recipe snapshot lookup for package_game_ready
- **Result:** Success.
- **Notes:** Updated `modules/export/package_game_ready_v1/main.py` to search upward from stage dirs for `snapshots/recipe.yaml|yml` (stops at repo root), preventing resume runs from failing when `run_dir` points at a module output folder.
- **Next:** Rerun `package_game_ready_v1` stage (or resume from `package_game_ready`) to confirm packaging completes in the resume run.

### 20260102-2259 — Reran package_game_ready after snapshot lookup fix
- **Result:** Success.
- **Notes:** Ran `python driver.py --recipe configs/recipes/recipe-ff-ai-ocr-gpt51-pristine-fast.yaml --output-dir output/runs/ff-ai-ocr-gpt51-pristine-fast-full --allow-run-id-reuse --start-from package_game_ready`. Packaging completed and wrote `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/output/`.
- **Next:** If needed, re-run edgecase scan to confirm no remaining warnings beyond suspicious link checks.

### 20260102-2303 — Documented suspicious link warnings as known‑legit
- **Result:** Success.
- **Notes:** Confirmed 11→140 and 392→177 are legitimate links; leaving `validate_choice_links_v1` warnings in place (non‑fatal) for now.
- **Next:** Consider adding an allowlist/suppression mechanism if warnings become noisy across books.

### 20260102-2306 — Marked story done with user sign-off on combat patch demo
- **Result:** Success.
- **Notes:** User approved marking story done without a real-book combat patch demo (synthetic patch accepted).
- **Next:** If needed, add a real-book combat patch demonstration in a follow-up story.
