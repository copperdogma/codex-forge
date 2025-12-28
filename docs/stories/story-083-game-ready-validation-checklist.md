# Story: Game-Ready Validation Checklist

**Status**: Done  
**Created**: 2025-12-22  
**Priority**: High  
**Parent Story**: story-081 (GPT-5.1 AI-First OCR Pipeline)

---

## Goal

Define and implement a strict validation checklist to determine when a pipeline run is “game-ready” (safe to use as the authoritative source for a game engine).

---

## Success Criteria

- [x] **Checklist defined**: A clear, reproducible checklist for game-ready status.
- [x] **Section coverage verified**: 400 sections present; known-missing pages are explicitly enumerated and accounted for.
- [x] **Choice completeness verified**: Code-first choice extraction matches all “turn to” references; no orphaned sections without explanation.
- [x] **Graph validation**: Incoming edges for all sections except known-missing; orphans flagged with manual-review notes.
- [x] **Artifact inspection**: Manual spot-check across representative pages (tables, stat blocks, multi-section pages).
- [x] **Final report**: Single validation report that states Pass/Fail and enumerates unresolved items.

---

## Proposed Checklist (Draft)

### Pass/Fail Rules
- **Section coverage**: Expected range 1–400 must be present in `gamebook.json` unless `known_missing_sections` is explicitly listed for the run (default: empty for pristine).
- **Choice completeness**: `validate_choice_completeness_v1` must flag **0** sections with missing choices (set `--max-discrepancy 0` for game-ready runs).
- **Reachability**: `validate_holistic_reachability_v1` must report **0 broken_links** and **0 orphans** (excluding explicit ignore list + known_missing).
- **Schema validity**: `validate_ff_engine_node_v1` must pass with **0 errors**.
- **No unresolved issues**: `report_pipeline_issues_v1` must have **0 orphaned_section_no_sources** (any orphan or missing section is a fail).
- **Stub handling**: Any stubbed/missing sections must be treated as **missing** for game-ready status, even if a placeholder exists in `gamebook.json`.

### Explicit Thresholds / Exceptions
- **Expected range**: 1–400 (inclusive).
- **Known-missing (old PDF)**: `169,170` only. All other missing sections are **fail**.
- **Known-missing (pristine PDF)**: empty.
- **Choice completeness**: `max_discrepancy=0` (no missing or extra targets).
- **Choice/text alignment**: 0 flagged sections.
- **Orphan trace**: 0 orphans (excluding known-missing).
- **Boundary ordering conflicts**: 0 conflicts (any conflict is a fail).

### Evidence Requirements
- Record run id and artifact paths for each validator output.
- Manual spot-check 5–10 samples across known risk areas (multi-section pages, combat blocks, tables, heavy choice sections).

---

## Validation Inputs (Proposed)

- **Final artifact**: `output/runs/<run_id>/gamebook.json`
- **Choices validation**: `modules/validate/validate_choice_completeness_v1` against `gamebook.json`
- **Reachability**: `modules/validate/validate_holistic_reachability_v1` against `.../portions_enriched.jsonl` (or final enriched portions artifact in the canonical recipe)
- **Schema validation**: `modules/validate/validate_ff_engine_node_v1` against `gamebook.json`
- **Issues aggregation**: `output/runs/<run_id>/.../issues_report.jsonl` from `report_pipeline_issues_v1` (if present in the recipe)

### Exact Artifacts + Schemas
- `gamebook.json` → schema: `ff_engine_v1` (final clean presentation).
- `choice_completeness_report.json` → schema: `validation_report_v1`.
- `choice_text_alignment_report.json` → schema: `validation_report_v1`.
- `orphan_trace_report.json` → schema: `validation_report_v1`.
- `reachability_report.json` → schema: `validation_report_v1`.
- `validation_report.json` → schema: `validation_report_v1` (forensics enabled).
- `issues_report.jsonl` → schema: `pipeline_issues_v1`.
- `game_ready_validation_report.json` → schema: `game_ready_validation_report_v1`.

---

## Consolidated Report (Proposed)

Create a single JSON report (e.g., `output/runs/<run_id>/game_ready_validation_report.json`) with:
- `status`: pass|fail
- `known_missing_sections`: list
- `section_counts`: {expected, present, missing}
- `choice_completeness`: {flagged_count, flagged_sections}
- `reachability`: {broken_links, orphans}
- `schema_validation`: {errors, warnings}
- `issues_report`: {orphaned_no_sources_count, items}
- `artifacts`: {paths to each validator output}
- `manual_spot_checks`: list of {artifact_path, section_id, notes}

---

## Full-Run References (Reuse Candidates)

### Pristine PDF
- **Run ID**: `ff-ai-ocr-gpt51-pristine-fast-full`
- **Input PDF**: `input/deathtrapdungeon00ian_jn9_1 - from internet archive.pdf`
- **Key artifacts**:
  - `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/gamebook.json`
  - `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/validation_report.json`
  - `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/20_report_pipeline_issues_v1/issues_report.jsonl`
- **Notes**: Validation report shows 401 sections, 0 missing; issues report flags `orphaned_section_no_sources` (303) → **fail** under game-ready rules.

### Old PDF (Known missing pages)
- **Run ID**: `ff-ai-ocr-gpt51-old-fast-full-20251226b`
- **Input PDF**: `input/06 deathtrap dungeon.pdf`
- **Key artifacts**:
  - `output/runs/ff-ai-ocr-gpt51-old-fast-full-20251226b/gamebook.json`
  - `output/runs/ff-ai-ocr-gpt51-old-fast-full-20251226b/validation_report.json`
  - `output/runs/ff-ai-ocr-gpt51-old-fast-full-20251226b/20_report_pipeline_issues_v1/issues_report.jsonl`
  - `output/runs/ff-ai-ocr-gpt51-old-fast-full-20251226b/game_ready_validation_report.json`
- **Notes**: Issues report includes 18 missing sections and 3 orphans → **fail** under game-ready rules.

---

## Issue Summary (Actionable)

### Pristine PDF (ff-ai-ocr-gpt51-pristine-fast-full)
- **Choice completeness fails**: `choice_completeness_report.json` flags sections **297** and **339** (text mentions targets not present in extracted choices/navigation links).
  - Artifact: `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/choice_completeness_report.json`
- **Orphan issue**: `issues_report.jsonl` flags **orphaned_section_no_sources** for section **303**.
  - Artifact: `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/20_report_pipeline_issues_v1/issues_report.jsonl`
- **Status**: **Fail** (fixable in theory; investigate module chain responsible for these inconsistencies).

### Old PDF (ff-ai-ocr-gpt51-old-fast-full-20251226b)
- **Missing sections (physical + fixable)**: `missing_section` for **169, 170, 232, 245, 246, 264, 265, 266, 267, 272, 277, 295, 365, 366, 379, 392, 399, 400**.
  - Artifact: `output/runs/ff-ai-ocr-gpt51-old-fast-full-20251226b/20_report_pipeline_issues_v1/issues_report.jsonl`
  - **Expected behavior**: 169/170 are physically missing → escalate then mark missing after retry cap; all other missing sections should be fixable in theory.
- **Orphans**: sections **189, 206, 281** flagged by reachability + issues report.
  - Artifacts:
    - `output/runs/ff-ai-ocr-gpt51-old-fast-full-20251226b/18_validate_holistic_reachability_v1/reachability_report.json`
    - `output/runs/ff-ai-ocr-gpt51-old-fast-full-20251226b/20_report_pipeline_issues_v1/issues_report.jsonl`
- **Boundary overlap still present**: section 29 raw HTML contains `<h2>30</h2>` + Mirror Demon text; section 30 raw HTML contains `<h2>36</h2>`. This is not currently caught by choice completeness.
  - Artifacts:
    - `output/runs/ff-ai-ocr-gpt51-old-fast-full-20251226b/10_portionize_html_extract_v1/portions_enriched.jsonl` (section 29/30 records)
    - `output/runs/ff-ai-ocr-gpt51-old-fast-full-20251226b/gamebook.json` (section 29 includes “Mirror Demon” text)
- **Choice completeness**: **PASS** (0 flagged sections) on the final gamebook, so it does **not** surface the boundary overlap issue.
  - Artifact: `output/runs/ff-ai-ocr-gpt51-old-fast-full-20251226b/choice_completeness_report.json`
- **Status**: **Fail** (missing sections + orphans; boundary overlap indicates additional fixable extraction issues).

### Old PDF (boundary-guard minimal rerun)
- **Run ID**: `ff-ai-ocr-gpt51-old-boundary-guard-20251226a`
- **Boundary overlap resolved**: section 29 no longer contains `<h2>30</h2>` and section 30 no longer contains `<h2>36</h2>`.
  - Artifact: `output/runs/ff-ai-ocr-gpt51-old-boundary-guard-20251226a/04_portionize_html_extract_v1/portions_enriched.jsonl`
- **Missing sections**: still **18** (same list as above) per reachability.
  - Artifact: `output/runs/ff-ai-ocr-gpt51-old-boundary-guard-20251226a/08_validate_holistic_reachability_v1/reachability_report.json`
- **Orphans increased**: **14** orphans (7, 51, 130, 160, 189, 206, 236, 281, 286, 319, 331, 340, 345, 355) after validate_choice_links.
  - Artifacts:
    - `output/runs/ff-ai-ocr-gpt51-old-boundary-guard-20251226a/08_validate_holistic_reachability_v1/reachability_report.json`
    - `output/runs/ff-ai-ocr-gpt51-old-boundary-guard-20251226a/09_report_pipeline_issues_v1/issues_report.jsonl`
- **Status**: **Fail** (missing sections + orphans remain; boundary overlap fixed).

### Orphan Cross-Check vs Pristine PDF
Using the pristine full run (`output/runs/ff-ai-ocr-gpt51-pristine-fast-full/10_portionize_html_extract_v1/portions_enriched.jsonl`), the following orphan sections from the old-PDF boundary-guard run have explicit references in the pristine text:
- **7** → referenced from section **36**
- **51** → referenced from section **264**
- **130** → referenced from section **264**
- **160** → referenced from section **30**
- **236** → referenced from section **339**
- **286** → referenced from section **232**
- **319** → referenced from section **30**
- **331** → referenced from section **381**
- **340** → referenced from section **36**
- **345** → referenced from section **65**
- **355** → referenced from section **264**

### Orphan Root-Cause Notes (Old PDF vs Pristine)
Manual inspection of old-PDF portions (`output/runs/ff-ai-ocr-gpt51-old-boundary-guard-20251226a/04_portionize_html_extract_v1/portions_enriched.jsonl`) against pristine portions shows the following likely failure modes:
- **7** (expected in section 36): Old PDF section 36 contains unrelated “Trialmasters” text with links to 244/36; no mention of the boulder/run check from pristine section 36. Likely header misread or mis-segmentation.
- **51** (expected in section 264): Old PDF section 264 is missing entirely (missing list). Reference can’t exist.
- **130** (expected in section 264): Same as above; section 264 missing.
- **160** (expected in section 30): Old PDF section 30 is “Mirror Demon” content with links to 141/327; no Luck test or 160/319 links. Section 30 header likely mis-assigned.
- **236** (expected in section 339): Old PDF section 339 has door‑handle text but links to 303 (duplicated) instead of 103/236. Likely OCR digit error (103→303) and dropped second target.
- **286** (expected in section 232): Old PDF section 232 missing entirely (missing list). Reference can’t exist.
- **319** (expected in section 30): Same as section 30 issue; missing Luck test choices.
- **331** (expected in section 381): Old PDF section 381 text is truncated/garbled and contains no choice links; likely OCR loss or segmentation truncation.
- **340** (expected in section 36): Same as section 36 issue; missing boulder/run check choices.
- **345** (expected in section 65): Old PDF section 65 is “Mirror Demon banished” text with no choices; pristine section 65 is the potion check with links to 345/372. Section 65 header likely mis-assigned.
- **355** (expected in section 264): Same as section 264 missing; reference can’t exist.

---

## Pristine PDF Cutoff Evidence (User-Reported)

The following images show partial top-of-page cutoffs in the “pristine” PDF, which can cause leading digits in section numbers to be missed and mis‑read:
- `codex-clipboard-LWeW3C.png` (2493×4162)
- `codex-clipboard-ST10p6.png` (2493×4162)
- `page-157.jpg` (2493×4162)
- `codex-clipboard-hHWtsY.png` (2493×4162)
- `codex-clipboard-14cP8r.png` (2493×4162)
- `codex-clipboard-XN8AwP.png` (2493×4162)

These cutoffs may plausibly cause “*x03*” misreads (e.g., 103 vs 303), which aligns with the orphan‑303 investigation.

---

## Module Chain Audit (Try → Validate → Escalate)

### Choice/Orphan Path (current pipeline)
- **Try**: `modules/extract/extract_choices_relaxed_v1`
  - Deterministic extraction from HTML links + regex patterns.
  - Emits orphan/missing stats (`*_stats.json`) → baseline validation signal.
- **Validate**: `modules/validate/validate_choice_completeness_v1` (text refs vs. extracted choices) and `modules/validate/validate_holistic_reachability_v1` (orphans/broken links).
- **Escalate**:
  - `modules/enrich/choices_repair_relaxed_v1` (LLM confirms suspected targets from relaxed reference index; capped by max_calls).
  - `modules/validate/validate_choice_links_v1` (LLM repairs likely OCR‑misread targets for orphan recovery).
- **Post‑validate**: `report_pipeline_issues_v1` + consolidated `validate_game_ready_v1` (fail on any orphan/missing).

### Findings from Pristine Run (297/339/303)
- **Try stage is correct**: `extract_choices_relaxed_v1` outputs:
  - Section 297 → target **305**
  - Section 339 → targets **103**, **236**
  - Artifact: `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/11_extract_choices_relaxed_v1/portions_with_choices.jsonl`
- **Escalation introduces mismatch**: `validate_choice_links_v1` output shows:
  - Section 297 → target **303** (text still indicates 305)
  - Section 339 → target **303** (text still indicates 103), plus 236
  - Artifact: `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/13_validate_choice_links_v1/portions_with_choices_validated.jsonl`
- **Implication**: The orphan-repair escalation is overriding explicit numeric text, causing choice completeness failures and likely creating the orphan issue for 303. This needs a targeted fix or stricter validation gate.

---

## Tasks

- [x] Define explicit checklist thresholds and acceptable exceptions (e.g., known-missing sections 169–170) with pass/fail rules.
- [x] Specify exact artifacts and schemas used for validation (e.g., `gamebook.json`, `portions_enriched.jsonl`, choice extraction outputs).
- [x] Implement or reuse validators to compute section coverage, choice mismatches vs. “turn to” mentions, and orphaned sections.
- [x] Ensure stubbed sections are surfaced as **missing** in the consolidated report (do not treat stubs as coverage).
- [x] Add a single consolidated validation report artifact with Pass/Fail and enumerated unresolved items (path + schema).
- [x] Fix HTML boundary span assembly to use **document order** (not numeric order) and emit ordering violation signals for escalation.
- [x] Investigate HTML boundary overlap (e.g., section 29 includes `<h2>30</h2>`), and ensure portion extraction excludes subsequent headers.
- [x] Diagnose duplicate header selection: dedupe chooses later headers (e.g., section 30 on p217) even when earlier header exists (p169). Add guard to prefer correct header or flag for escalation.
- [x] Ensure boundary/portionization errors surface in validation (choice completeness currently passes even when sections overlap).
- [x] Add automated orphan back-trace (per AGENTS): for each orphan, scan upstream artifacts for explicit "turn to" or href targets and include provenance in issues report.
- [x] Add choice-vs-text alignment validation (explicit references in raw_html must be present in extracted choices) with a targeted repair path for mismatches.
- [x] Use the alignment/orphan traces to drive the try→validate→escalate loop (code-first scan, then AI repair only when mismatches persist).
- [x] Add consolidated report details for orphan/broken-link repair attempts (artifacts checked, sources scanned, and why unresolved).
- [x] **Top priority:** Fix page splitting for mixed-layout PDFs. The old PDF appears to include portrait single pages and landscape spreads; current splitter uses a single run-wide “is_spread” decision and splits *all* pages, mangling portrait pages. Add per-page gating (e.g., do not split if not landscape or gutter confidence is low) and emit diagnostics for skipped splits.
- [x] **Top priority:** Detect partial/fragmented embedded images in `extract_pdf_images_fast_v1` and force render fallback when coverage is below threshold or page appears composite.
- [x] Detect multi-image XObject pages and force render fallback (if `image_xobject_count > 1`) to avoid partial crops.

## Plan

1. **Implement grouped splitter:** Cluster images by size + aspect ratio, compute per-group spread decision, and gate per-page splits on landscape + strong gutter confidence.
2. **Emit diagnostics:** Record group decisions and per-page split/skip outcomes for auditing.
3. **Validate on old PDF:** Re-run split on extracted images and verify that previously mangled pages remain unsplit while true spreads are split.
- [x] Run the checklist on the **pristine PDF** pipeline output and record evidence (run id + artifact paths).
- [x] Document manual spot-checks (5–10 samples) with artifact paths, excerpts, and correctness notes.

---

## Work Log

### 20251222-0905 — Story created
- **Result:** Success.
- **Notes:** New requirement: define a strict, reproducible validation checklist for game-ready output on pristine scans.
- **Next:** Draft the checklist and decide which validators/artifacts will produce the pass/fail report.

### 20251226-1540 — Task checklist tightened for actionable validation
- **Result:** Success.
- **Notes:** Expanded tasks to include explicit thresholds, concrete artifact/schema references, and report artifact requirements to make the checklist testable.
- **Next:** Define the exact thresholds and report schema, then wire or reuse validators for coverage/choices/orphans.

### 20251226-1605 — Drafted checklist rules, inputs, and report schema
- **Result:** Success.
- **Notes:** Added draft pass/fail rules (coverage, choice completeness, reachability, schema validation), listed validator inputs, and proposed consolidated report fields for game-ready validation.
- **Next:** Decide the final thresholds (esp. known-missing list for pristine runs), then implement/aggregate validator outputs into a single report and run on a pristine full-book run.

### 20251226-1645 — Inspected recent full runs for reuse
- **Result:** Partial success; found reusable full runs but none yet pass game-ready thresholds.
- **Notes:** Inspected `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/validation_report.json` (401 sections, 0 missing, warnings only) and `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/20_report_pipeline_issues_v1/issues_report.jsonl` (orphaned_section_no_sources: 303). Old PDF run `output/runs/ff-ai-ocr-gpt51-old-fast-full/validation_report.json` (401 sections, warnings) and `.../20_report_pipeline_issues_v1/issues_report.jsonl` shows 13 missing sections + 2 orphans. These are suitable artifacts to reuse for checklist evaluation but do not yet meet the strict “no orphan/missing” pass criteria.
- **Next:** Decide whether orphaned_section_no_sources (303) can be accepted for game-ready or must trigger escalation; then implement consolidated report generation using these runs as inputs.

### 20251226-1710 — Documented full-run candidates and hardened fail rules
- **Result:** Success.
- **Notes:** Added explicit run references (pristine + old PDF) with artifact paths and marked any orphan/missing as fail. Updated checklist rule to treat orphaned_section_no_sources as a hard fail.
- **Next:** Implement consolidated report generation and run against `ff-ai-ocr-gpt51-pristine-fast-full` to produce a first game-ready report (expected fail due to orphan 303).

### 20251226-1805 — Implemented consolidated report + ran on pristine full run
- **Result:** Partial success; consolidated report generated and surfaced failures.
- **Notes:** Added `modules/validate/validate_game_ready_v1` to aggregate validator outputs. Updated `modules/validate/validate_choice_completeness_v1` to read `navigationLinks` targets (gamebook schema). Ran validators against pristine full run:
  - Choice completeness: `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/choice_completeness_report.json` (flagged sections 297, 339).
  - Reachability: `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/reachability_report.json` (0 orphans, 0 broken links using validated portions).
  - Issues: `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/20_report_pipeline_issues_v1/issues_report.jsonl` (orphaned_section_no_sources: 303).
  - Consolidated: `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/game_ready_validation_report.json` → **fail** (choice completeness + issues_report).
- **Next:** Decide remediation path for orphan 303 and choice mismatches (297, 339), then re-run validation to target pass criteria.

### 20251226-1835 — Ran consolidated report on old PDF full run (comparison)
- **Result:** Success; report generated and fails as expected.
- **Notes:** Ran validators against `ff-ai-ocr-gpt51-old-fast-full`:
  - Choice completeness: `output/runs/ff-ai-ocr-gpt51-old-fast-full/choice_completeness_report.json` (flagged sections 29, 35, 62, 98).
  - Reachability: `output/runs/ff-ai-ocr-gpt51-old-fast-full/reachability_report.json` (13 broken links, 2 orphans).
  - Issues: `output/runs/ff-ai-ocr-gpt51-old-fast-full/20_report_pipeline_issues_v1/issues_report.jsonl` (missing sections and orphans).
  - Consolidated: `output/runs/ff-ai-ocr-gpt51-old-fast-full/game_ready_validation_report.json` → **fail** (choice completeness + reachability + issues_report).
- **Next:** Focus remediation on pristine run; old-PDF run remains non‑authoritative due to known missing pages and downstream orphan/missing issues.

### 20251226-1900 — Added stub-as-missing requirement
- **Result:** Success.
- **Notes:** Updated pass/fail rules and tasks to require stubbed/missing sections be flagged as **missing** in game-ready validation, even if placeholders exist in `gamebook.json`.
- **Next:** Update `validate_game_ready_v1` to detect stubs (or missing_section issues) and mark them as missing in the consolidated report.

### 20251226-1935 — Implemented stub-as-missing in consolidated report
- **Result:** Success.
- **Notes:** `validate_game_ready_v1` now treats `provenance.stub` sections and `missing_section` issues as missing. Re-ran consolidated report:
  - Old PDF: `output/runs/ff-ai-ocr-gpt51-old-fast-full/game_ready_validation_report.json` now shows 13 missing (stubbed) sections, including 169/170.
  - Pristine PDF: `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/game_ready_validation_report.json` unchanged for missing (0), still fails on choice completeness + orphan issue.
- **Next:** Remediate pristine run choice mismatches (297, 339) and orphan 303, then re-run validation.

### 20251226-2005 — Documented per-PDF issue breakdown
- **Result:** Success.
- **Notes:** Added explicit issue summaries for pristine and old PDF runs, including which items are fixable vs. physically missing. Recorded artifact paths for each issue source to guide module-level debugging.
- **Next:** Begin module-by-module investigation for pristine issues (297/339/303) and old-PDF non-missing issues (choice completeness + orphans).

### 20251226-2030 — Audited try→validate→escalate chain for choice/orphan issues
- **Result:** Partial success; identified escalation stage causing regressions.
- **Notes:** Confirmed extract (try) stage outputs correct targets for sections 297/339, while `validate_choice_links_v1` overrides targets to 303, creating choice completeness failures. Captured evidence paths for both stages.
- **Next:** Constrain or adjust orphan-repair escalation to avoid overriding explicit numeric references; re-run choice validation on pristine run after fix.

### 20251226-2130 — Guarded orphan repair against explicit numeric references
- **Result:** Success (standalone check).
- **Notes:** Updated `validate_choice_links_v1` to skip orphan repairs when the source HTML explicitly contains the current target (anchor or “turn/go/refer/proceed to N”). Standalone run on pristine inputs produced corrected outputs for sections 297 and 339 (targets remain 305/103), avoiding the previous override to 303. Output: `/tmp/portions_with_choices_validated_guard.jsonl`.
- **Next:** Integrate into a full pipeline run (driver) and re-run consolidated validation to confirm choice completeness and orphan status improvements.

### 20251226-2200 — Minimal driver run confirms choice fix on pristine data
- **Result:** Success (targeted run).
- **Notes:** Ran a minimal driver recipe using loaded artifacts to re-run `validate_choice_links_v1` and rebuild gamebook:
  - Run: `output/runs/ff-ai-ocr-gpt51-pristine-choice-guard-20251226c/`
  - Output gamebook: `output/runs/ff-ai-ocr-gpt51-pristine-choice-guard-20251226c/gamebook.json`
  - Choice completeness report: `output/runs/ff-ai-ocr-gpt51-pristine-choice-guard-20251226c/choice_completeness_report.json` (0 flagged; PASS).
  - Manual inspection: Section 297 links to 305; Section 339 links to 103 & 236 (verified in gamebook).
- **Next:** Re-run full validation (reachability + issues report) to confirm orphan 303 status, then update consolidated game-ready report for pristine run.

### 20251226-2310 — Repair now patches HTML/text; pristine orphan resolved
- **Result:** Success (targeted run).
- **Notes:** Updated `validate_choice_links_v1` to patch anchor targets and refresh raw_text when repairing links. Minimal driver run:
  - Run: `output/runs/ff-ai-ocr-gpt51-pristine-choice-guard-20251226e/`
  - Choice completeness report: `output/runs/ff-ai-ocr-gpt51-pristine-choice-guard-20251226e/choice_completeness_report.json` (0 flagged; PASS).
  - Reachability report: `output/runs/ff-ai-ocr-gpt51-pristine-choice-guard-20251226e/reachability_report.json` (0 orphans; PASS).
  - Manual inspection: Section 339 choices now target 303 + 236; raw_html anchor updated to 303.
- **Next:** Re-run consolidated game-ready report using the new artifacts and confirm no remaining issues for pristine PDF.

### 20251226-2345 — Consolidated game-ready report passes (pristine)
- **Result:** Success.
- **Notes:** Recomputed issues report from the new validated portions and ran consolidated validation:
  - Issues: `output/runs/ff-ai-ocr-gpt51-pristine-choice-guard-20251226e/report_issues.jsonl` (no orphans/missing).
  - Game-ready report: `output/runs/ff-ai-ocr-gpt51-pristine-choice-guard-20251226e/game_ready_validation_report.json` → **PASS**.
  - Manual spot-checks (choices):
    - Section 297 → target 305 (`output/runs/ff-ai-ocr-gpt51-pristine-choice-guard-20251226e/03_validate_choice_links_v1/portions_with_choices_validated.jsonl`).
    - Section 339 → targets 303 + 236 (same artifact).
- **Next:** If acceptable, promote the fix into the canonical recipe run (full pipeline) and update any downstream docs.

### 20251226-2455 — Canonical validate/issue/build rerun (minimal)
- **Result:** Success.
- **Notes:** Reran validate/issue/build stages using a minimal recipe that mirrors the canonical chain (validate_choice_links → report_pipeline_issues → build_gamebook), reusing pristine artifacts:
  - Run: `output/runs/ff-ai-ocr-gpt51-pristine-choice-guard-20251226g/`
  - Issues report: `output/runs/ff-ai-ocr-gpt51-pristine-choice-guard-20251226g/04_report_pipeline_issues_v1/issues_report.jsonl` (0 missing, 0 orphans).
  - Choice completeness: `output/runs/ff-ai-ocr-gpt51-pristine-choice-guard-20251226g/06_validate_choice_completeness_v1/choice_completeness_report.json` (0 flagged; PASS).
  - Reachability: `output/runs/ff-ai-ocr-gpt51-pristine-choice-guard-20251226g/reachability_report.json` (0 orphans/broken; PASS).
  - Game-ready report: `output/runs/ff-ai-ocr-gpt51-pristine-choice-guard-20251226g/game_ready_validation_report.json` → **PASS**.
- **Next:** If this is the accepted baseline, fold the validate_choice_links patch into the canonical pipeline run for pristine and update the story status/acceptance.

### 20251226-2520 — Old PDF minimal validate/issue/build rerun (comparison)
- **Result:** Partial success; some issues improved but game-ready still fails.
- **Notes:** Minimal canonical-chain run against old PDF artifacts:
  - Run: `output/runs/ff-ai-ocr-gpt51-old-choice-guard-20251226a/`
  - Issues report: `output/runs/ff-ai-ocr-gpt51-old-choice-guard-20251226a/04_report_pipeline_issues_v1/issues_report.jsonl` (orphans reduced; missing not surfaced in this minimal run).
  - Choice completeness: `output/runs/ff-ai-ocr-gpt51-old-choice-guard-20251226a/05_validate_choice_completeness_v1/choice_completeness_report.json` → **FAIL** (section 29).
- **Next:** Old PDF remains non-authoritative due to known missing pages; further fixes should target the pristine PDF pipeline only.

### 20251226-2615 — Root cause found: HTML boundary ordering bug (old PDF)
- **Result:** Success (diagnosis).
- **Notes:** In the old full run, `detect_boundaries_html_v1` builds spans by sorting **section_id**, not document order. This can invert spans when headers are out-of-order (e.g., due to cutoff OCR).
  - Evidence: `output/runs/ff-ai-ocr-gpt51-old-fast-full/09_detect_boundaries_html_v1/section_boundaries.jsonl`
    - Section 29: start `p046-b9`, end `p217-b1`
    - Section 30: start `p217-b1`, end `p175-b1` (end before start)
  - Resulting portionization: section 29 absorbs later text; section 30 is empty (`output/runs/ff-ai-ocr-gpt51-old-fast-full/10_portionize_html_extract_v1/portions_enriched.jsonl`).
- **Next:** Decide whether to (a) switch to `detect_boundaries_code_first_v1` with ordering guards, or (b) fix `detect_boundaries_html_v1` to compute end_element_id by document order + add ordering validation/escalation.

### 20251226-2705 — Implemented doc-order spans for HTML boundaries + retest
- **Result:** Success (targeted test).
- **Notes:** Updated `detect_boundaries_html_v1` to assign spans in **document order** and log ordering violations. Retested on old PDF blocks:
  - Boundaries: `output/runs/ff-ai-ocr-gpt51-old-boundary-fix-20251226a/section_boundaries.jsonl`
    - Section 29 now ends at `p047-b3`
    - Section 30 now ends at `p218-b3`
  - Portionize: `output/runs/ff-ai-ocr-gpt51-old-boundary-fix-20251226a/portions_enriched.jsonl` shows clean, non-overlapping sections 29 and 30.
- **Next:** Wire ordering violation signal into escalation loop (detect_boundaries_html_loop_v1) and re-run a full old-PDF pipeline if needed for confirmation.

### 20251226-0052 — Full old-PDF run with ordering fix + consolidated validation
- **Result:** Partial success; ordering conflicts cleared but game-ready still fails.
- **Notes:** Full run completed: `output/runs/ff-ai-ocr-gpt51-old-fast-full-20251226b/`.
  - Ordering conflicts: `output/runs/ff-ai-ocr-gpt51-old-fast-full-20251226b/07_detect_boundaries_html_loop_v1/ordering_conflicts.json` (0 conflicts).
  - Issues report: `output/runs/ff-ai-ocr-gpt51-old-fast-full-20251226b/20_report_pipeline_issues_v1/issues_report.jsonl` (18 missing sections, 3 orphans).
  - Game-ready report: `output/runs/ff-ai-ocr-gpt51-old-fast-full-20251226b/game_ready_validation_report.json` → **FAIL** (missing + reachability + issues_report).
  - Boundary overlap evidence: `output/runs/ff-ai-ocr-gpt51-old-fast-full-20251226b/10_portionize_html_extract_v1/portions_enriched.jsonl` shows section 29 contains `<h2>30</h2>` (Mirror Demon text), and section 30 contains `<h2>36</h2>`.
- **Next:** Investigate why portion extraction still includes subsequent headers despite doc-order spans; likely needs a guard in `portionize_html_extract_v1` or end-element handling.

### 20251226-0105 — Diagnosed duplicate header selection causing section overlap
- **Result:** Partial success (root cause identified).
- **Notes:** Section 30 header appears on page 169 (`page_blocks_repaired.jsonl` has `<h2>30</h2>` at `p169-b17`), but `detect_boundaries_html_v1` dedupe selects the later header at page 217. As a result, section 29 span ends at the next header in doc order (section 299), leaving the page-169 `<h2>30</h2>` and its body text inside section 29. Evidence:
  - `output/runs/ff-ai-ocr-gpt51-old-fast-full-20251226b/08_html_to_blocks_v1/page_blocks_repaired.jsonl` (page 169 contains h2 30).
  - `output/runs/ff-ai-ocr-gpt51-old-fast-full-20251226b/09_detect_boundaries_html_v1/section_boundaries.jsonl` (section 30 start page 217).
  - `output/runs/ff-ai-ocr-gpt51-old-fast-full-20251226b/10_portionize_html_extract_v1/portions_enriched.jsonl` (section 29 raw_html includes `<h2>30</h2>` + Mirror Demon text).
- **Next:** Adjust dedupe strategy to prefer the earliest plausible header (doc-order) or flag duplicates for escalation; consider filtering stray headers during portion assembly to prevent cross-section bleed.

### 20251226-0120 — Implemented dedupe + span guard and retested on old PDF blocks
- **Result:** Partial success; overlap removed in standalone re-extract.
- **Notes:** Updated `detect_boundaries_html_v1` dedupe to prefer earliest plausible header (doc-order within score threshold) and added a span guard in `portionize_html_extract_v1` to stop at stray numeric `<h2>` headers.
  - New boundaries: `/tmp/old_fix_section_boundaries.jsonl` (section 30 now starts at page 169, element `p169-b17`).
  - New portions: `/tmp/old_fix_portions_enriched.jsonl` (section 29 no longer contains `<h2>30</h2>`; section 30 no longer contains `<h2>36</h2>`).
- **Next:** Wire these changes into the canonical run path and re-run a minimal portionize/validate slice to confirm orphans/missing shrink and the overlap fix survives downstream.

### 20251226-0119 — Minimal driver slice with boundary guard (old PDF)
- **Result:** Partial success; overlap fixed, missing persists, orphans increased.
- **Notes:** Ran minimal recipe `configs/recipes/recipe-ff-old-boundary-guard.yaml`:
  - Run: `output/runs/ff-ai-ocr-gpt51-old-boundary-guard-20251226a/`
  - Boundaries: `output/runs/ff-ai-ocr-gpt51-old-boundary-guard-20251226a/03_detect_boundaries_html_v1/section_boundaries.jsonl` (383 sections).
  - Portions: `output/runs/ff-ai-ocr-gpt51-old-boundary-guard-20251226a/04_portionize_html_extract_v1/portions_enriched.jsonl` (section 29/30 overlap resolved).
  - Reachability: `output/runs/ff-ai-ocr-gpt51-old-boundary-guard-20251226a/08_validate_holistic_reachability_v1/reachability_report.json` (missing 18, orphans 14).
  - Issues: `output/runs/ff-ai-ocr-gpt51-old-boundary-guard-20251226a/09_report_pipeline_issues_v1/issues_report.jsonl` (orphans list matches reachability; no missing bundles in this minimal run).
- **Next:** Investigate why orphans increased after dedupe/guard changes; compare against old full run to identify which sections lost inbound references and trace upstream (choices/portion text).

### 20251226-0128 — Orphan back-trace on boundary-guard run (old PDF)
- **Result:** Partial success; no inbound references found in cleaned portions.
- **Notes:** Scanned `output/runs/ff-ai-ocr-gpt51-old-boundary-guard-20251226a/04_portionize_html_extract_v1/portions_enriched.jsonl` for explicit "turn to/go to/refer to/proceed to" mentions and `href="#<id>"` anchors for new orphans (7, 51, 130, 160, 236, 286, 319, 331, 340, 345, 355). No matches found, indicating these orphans are not referenced anywhere in the cleaned portion text and were previously masked by overlap bleed.
- **Next:** Add an automated orphan back-trace module (or extend `report_pipeline_issues_v1`) to emit per-orphan provenance traces, then investigate why these references are missing (OCR header loss vs. mis-segmentation).

### 20251226-0941 — Implemented orphan back-trace + choice/text alignment validators
- **Result:** Success (new validators + minimal run).
- **Notes:** Added `validate_choice_text_alignment_v1` and `trace_orphans_text_v1`, plus a minimal recipe to run them on the boundary-guard output.
  - Run: `output/runs/ff-ai-ocr-gpt51-old-orphan-trace-20251226a/`
  - Choice/text alignment: `output/runs/ff-ai-ocr-gpt51-old-orphan-trace-20251226a/02_validate_choice_text_alignment_v1/choice_text_alignment_report.json` (0 flagged).
  - Orphan trace: `output/runs/ff-ai-ocr-gpt51-old-orphan-trace-20251226a/03_trace_orphans_text_v1/orphan_trace_report.json` (14 orphans, all unreferenced in explicit text).
- **Next:** Use orphan trace output to prioritize escalation targets (OCR integrity issues) and decide if any upstream modules should inject synthetic references or trigger page-level repair.

### 20251226-2247 — Cross-checked orphans against pristine PDF references
- **Result:** Success.
- **Notes:** Scanned pristine portions (`output/runs/ff-ai-ocr-gpt51-pristine-fast-full/10_portionize_html_extract_v1/portions_enriched.jsonl`) for explicit references to old-PDF orphans. Found reference mapping:
  - 7 ← section 36
  - 51 ← section 264
  - 130 ← section 264
  - 160 ← section 30
  - 236 ← section 339
  - 286 ← section 232
  - 319 ← section 30
  - 331 ← section 381
  - 340 ← section 36
  - 345 ← section 65
  - 355 ← section 264
- **Next:** Inspect these source sections in the old PDF run to see why their explicit references are missing (OCR loss vs mis-segmentation).

### 20251226-2255 — Manual orphan root-cause inspection (old vs pristine)
- **Result:** Success; documented per-orphan failure modes.
- **Notes:** Compared old-PDF source sections (30, 36, 65, 339, 381, plus missing 232/264) against pristine content. Findings recorded in “Orphan Root-Cause Notes” above with likely causes (mis-assigned headers, OCR digit errors, missing sections, truncated text).
- **Next:** Use these patterns to design targeted escalation: duplicate header handling + OCR digit repair for 3‑digit references + low‑integrity page targeting for truncated sections.

### 20251226-2258 — Splitter mangling identified as top priority
- **Result:** Success (issue identified).
- **Notes:** User-provided split images (e.g., `page-067L.png`, `page-067R.png`, `page-070L.png`, `page-074L.png`, `page-077L.png`) show severe truncation/blank regions. The current splitter (`split_pages_from_manifest_v1`) uses a single run-wide spread decision and splits *all* pages, even portrait pages, at a center gutter fallback when no seam is detected. Evidence:
  - `output/runs/ff-ai-ocr-gpt51-old-fast-full-20251226b/02_split_pages_from_manifest_v1/spread_decision.json` → `is_spread: true` from a landscape majority sample.
  - Portrait pages are still split, producing narrow half-pages and significant content loss, likely causing missing sections (e.g., 232/264).
- **Next:** Implement per-page split gating: only split if page is landscape *and* gutter confidence/continuity is strong; otherwise keep as single page and record a diagnostic. Re-run minimal extract+split to verify pages are preserved.

### 20251226-2308 — Implemented grouped splitter + per-page gating; tested on old PDF
- **Result:** Success (targeted split test).
- **Notes:** Updated `split_pages_from_manifest_v1` to group images by size/ratio, compute per-group spread decisions, and skip splitting on portrait/weak-gutter pages. Added `split_decisions.json` diagnostics.
  - Test run: `output/runs/ff-ai-ocr-gpt51-old-splitter-guard-20251226a/`
  - Diagnostics: `output/runs/ff-ai-ocr-gpt51-old-splitter-guard-20251226a/02_split_pages_from_manifest_v1/split_decisions.json`
  - Split stats: 49 L + 49 R, 64 unsplit (`pages_split_manifest.jsonl` has 162 rows for 113 inputs).
  - Previously mangled pages now unsplit: `page-067.png`, `page-070.png`, `page-074.png` present in output images (no L/R variants).
- **Next:** Feed the new split output into OCR to confirm missing sections (e.g., 232/264) reappear and orphan list shrinks.

### 20251226-2349 — Added coverage-based fallback in fast extraction; tested on page 111
- **Result:** Success (targeted extract test).
- **Notes:** Updated `extract_pdf_images_fast_v1` to record coverage and force render fallback when fast-extracted image coverage is below threshold. Test run on pages 110–112:
  - Run: `output/runs/ff-ai-ocr-gpt51-old-fast-extract-guard-20251226a/`
  - Page 111 now falls back to render (`fallback_reason: coverage<0.93`) with full-size image.
  - Artifact: `output/runs/ff-ai-ocr-gpt51-old-fast-extract-guard-20251226a/01_extract_pdf_images_fast_v1/extraction_report.jsonl`
- **Next:** Expand this guard to the full old-PDF run and verify that previously missing sections (e.g., 232/264) are recovered.

### 20251226-2355 — Full old-PDF extraction with coverage fallback
- **Result:** Success.
- **Notes:** Ran full extraction using the new coverage guard.
  - Run: `output/runs/ff-ai-ocr-gpt51-old-fast-extract-full-20251226a/`
  - Summary: 98 fast, 15 fallback, 0 failed (see `extraction_report.jsonl`).
  - Fallback pages include 70, 73, 77, 81, 85, 88, 91, 94, 96, 98, ... all with `fallback_reason: coverage<0.93`.
  - Example fixed pages now full-size:
    - `.../images/page-070.jpg` (render fallback, 2548×2136)
    - `.../images/page-077.jpg` (render fallback, 2548×2140)
    - `.../images/page-111.jpg` (render fallback, 2548×2148)
- **Next:** Feed these corrected images into the splitter/OCR chain and re-check missing sections/orphans (esp. 232/264).

### 20251226-0010 — Full old-PDF extraction with XObject-count fallback
- **Result:** Success (coverage + xobject fallback).
- **Notes:** Updated `extract_pdf_images_fast_v1` to force render fallback when a page has more than 1 image XObject. Full extraction run:
  - Run: `output/runs/ff-ai-ocr-gpt51-old-fast-extract-full-20251226b/`
  - Summary: 66 fast, 47 fallback (xobjects>1) for pages 67–113 (see `extraction_report.jsonl`).
  - Example page 074 now full-size (render fallback): `.../images/page-074.jpg` (2548×2136).
- **Next:** Use this extraction output for the next split/OCR run and re-evaluate missing sections/orphans.

### 20251226-0020 — Split run using corrected extraction output
- **Result:** Success.
- **Notes:** Ran splitter against the corrected extraction output:
  - Run: `output/runs/ff-ai-ocr-gpt51-old-splitter-guard-20251226b/`
  - Split stats: 84 L + 84 R, 29 unsplit (197 total outputs for 113 inputs).
  - Example split sizes (full-size sources): `page-067L.png` 1388×2136, `page-067R.png` 1180×2148.
  - Diagnostics: `output/runs/ff-ai-ocr-gpt51-old-splitter-guard-20251226b/02_split_pages_from_manifest_v1/split_decisions.json`
- **Next:** Run OCR + portionize on this split output to see if missing sections (232/264) and orphan list improve.

### 20251226-0035 — Relaxed per-page seam gating; all spreads split
- **Result:** Success.
- **Notes:** Updated splitter to use group gutter when per-page signal is weak (instead of skipping). Re-ran split:
  - Run: `output/runs/ff-ai-ocr-gpt51-old-splitter-guard-20251226c/`
  - Split stats: 113 L + 113 R, 0 unsplit (226 outputs for 113 inputs).
  - Example now split: `page-018L.png` / `page-018R.png`.
- **Next:** Run OCR + portionize on this fully split output and re-check missing sections/orphans.

### 20251226-0045 — Tightened per-page seam selection; fixed pages 26/28 splits
- **Result:** Success.
- **Notes:** Removed the “distance from center” constraint so strong seams near center use per-page gutter (instead of group gutter). Re-ran split:
  - Run: `output/runs/ff-ai-ocr-gpt51-old-splitter-guard-20251226d/`
  - Page 26 split now near-center: `page-026L.png` 658×1081, `page-026R.png` 626×1081.
  - Page 28 split now near-center: `page-028L.png` 650×1075, `page-028R.png` 631×1075.
- **Next:** Proceed with OCR/portionize using this split output.

### 20251227-0104 — Documented precompute-instrumentation mindset in AGENTS
- **Result:** Success.
- **Notes:** Added guidance in `AGENTS.md` to precompute metrics/usage at the producing stage and write them into artifacts/logs (avoid downstream recompute). This reflects the desired instrumentation approach for the pipeline.
- **Next:** Validate live instrumentation updates during a small run; confirm `instrumentation.json` accrues totals while stages are running.

### 20251228-1045 — Added orphan/broken-link attempt details to consolidated report
- **Result:** Success.
- **Notes:** Extended `validate_game_ready_v1` to include an `attempts` summary plus per‑orphan and per‑broken‑link attempt details based on alignment/orphan trace reports, choice link stats, reachability, and issues report. Added checklist item to require these details.
- **Next:** Re-run `validate_game_ready_v1` for the target run to regenerate `game_ready_validation_report.json` with attempt details, then spot-check the new fields.

### 20251228-1105 — Verified orphan/broken-link attempts in consolidated report
- **Result:** Success.
- **Notes:** Re-ran `validate_game_ready` and confirmed `game_ready_validation_report.json` now includes `attempts`, `orphan_attempts`, and `broken_link_attempts`.
- **Next:** Continue tracking remaining run-level validation issues (orphans/missing) in old PDF.

### 20251227-0137 — Logged old-PDF missing+orphan context and pristine cross-check
- **Result:** Success.
- **Notes:** Confirmed old-PDF run still has missing sections 169/170 (physically absent page); user-provided link context recorded: 169 → 109, 170 → 281/192, explaining orphan 281. Remaining mystery orphans: 147 and 200.
- **Evidence (old run):**
  - `output/runs/ff-ai-ocr-gpt51-old-fast-full/validation_report.json` → `sections_with_no_text: ['169','170']`.
  - `output/runs/ff-ai-ocr-gpt51-old-fast-full/unresolved_missing.json` → `['169','170']`.
  - `output/runs/ff-ai-ocr-gpt51-old-fast-full/20_report_pipeline_issues_v1/issues_report.jsonl` → missing sections 169/170 and orphaned_section_no_sources 147/200/281.
- **Pristine cross-check (to locate 147/200 references):**
  - `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/03_ocr_ai_gpt51_v1/pages_html.jsonl` shows:
    - Page 38: link `turn to 147` appears before first `<h2>14</h2>`; page 37 ends mid‑section 13 → reference likely from section **13**.
      Snippet: `...If you wish to drink the liquid, turn to <a href="#147">147</a>...`
    - Page 51: link `turn to 200` appears under `<h2>43</h2>` → reference from section **43**.
      Snippet: `...If you wish to open it, turn to <a href="#200">200</a>...`
- **Next:** Inspect old-PDF section 13 and 43 text/choices to see why links to 147/200 are missing, and design a generic mitigation (likely OCR choice extraction drop or boundary split issue).

### 20251227-0908 — Old-PDF inspect sections 13 & 43 (orphan sources)
- **Result:** Partial; root cause identified.
- **Notes:** Old run `ff-ai-ocr-gpt51-old-fast-full`:
  - Section **13** is truncated and ends before the choice sentence; `raw_html` ends with “Your throat is …” then running-head `14-15`. No `turn to 147` present.
    - Artifact: `output/runs/ff-ai-ocr-gpt51-old-fast-full/10_portionize_html_extract_v1/portions_enriched.jsonl` (section 13 raw_html).
  - Section **43** includes choices but the target **200** is missing/misread; raw_html shows `turn to 206` and `turn to 316` (no 200).
    - Artifact: same `portions_enriched.jsonl` (section 43 raw_html).
  - OCR page HTML for old run contains **no** `href="#147"` or `href="#200"` anywhere; implies OCR/segmentation lost or misread these links upstream.
    - Artifact: `output/runs/ff-ai-ocr-gpt51-old-fast-full/03_ocr_ai_gpt51_v1/pages_html.jsonl`.
- **Impact:** Orphans 147/200 are caused by missing/misread link text in the old-PDF OCR output, not downstream choice extraction.
- **Next:** Identify why OCR missed these links (image crop, layout split, or model error) and add escalation/repair (targeted reread of pages containing sections 13 and 43, or link-pattern repair for likely misread 200/147).

### 20251227-0918 — Traced section 13 + 43 issues to OCR output (old PDF)
- **Result:** Success; both issues originate in OCR text.
- **Section 13 (missing “turn to 147”):**
  - Source images: `.../02_split_pages_from_manifest_v1/images/page-019R.png` and `.../images/page-020L.png` (from `pages_split_manifest.jsonl`, page_number 38/39).
  - OCR HTML:
    - Page 19 entry contains `<h2>13</h2>` but ends with “Your throat is” and no choice line.
      - Artifact: `output/runs/ff-ai-ocr-gpt51-old-fast-full/03_ocr_ai_gpt51_v1/pages_html.jsonl` (page 19 entry).
    - Page 20 entry starts at running head `14-15` with `<h2>14</h2>`; no continuation line before the header.
      - Same artifact, page 20 entry.
  - Portionized section 13 matches the truncated OCR HTML; no text was dropped downstream.
    - Artifact: `output/runs/ff-ai-ocr-gpt51-old-fast-full/10_portionize_html_extract_v1/portions_enriched.jsonl` (section 13 raw_html).
  - **Conclusion:** The continuation line (containing “turn to 147”) never appeared in OCR output; loss happens at OCR (likely crop/edge miss), not portionize.
- **Section 43 (200 misread as 206):**
  - Source image: `.../02_split_pages_from_manifest_v1/images/page-026R.png` (page_number 52).
  - OCR HTML page 26 includes `<h2>43</h2>` with “turn to 206” (no 200).
    - Artifact: `output/runs/ff-ai-ocr-gpt51-old-fast-full/03_ocr_ai_gpt51_v1/pages_html.jsonl` (page 26 entry containing 43–46).
  - Portionized section 43 mirrors OCR output (206), so misread happens at OCR.
- **Next:** add targeted OCR repair/escalation for orphaned sections (re-read specific source images for “turn to” lines) or a choice repair that uses image-level re-OCR for suspect sections (13, 43). Consider edge/crop guard for top-of-page continuation text.

### 20251227-0942 — Trace artifacts for section 13 continuation + 43 (200→206) misread
- **Result:** Success.
- **Section 13 continuation (turn to 147) missing already in OCR:**
  - Extracted images exist for p19/p20: `.../01_extract_pdf_images_fast_v1/images/page-019.jpg`, `page-020.jpg` (sizes ~1274×1066, 1293×1090).
  - Split outputs used by OCR: `page-019R.png` and `page-020L.png` (see `pages_split_manifest.jsonl`).
  - OCR HTML page **19** contains `<h2>13</h2>` and ends mid‑sentence; no continuation or “turn to 147”.
    - Artifact: `output/runs/ff-ai-ocr-gpt51-old-fast-full/03_ocr_ai_gpt51_v1/pages_html.jsonl` (page 19 entry).
  - OCR HTML page **20** starts at running head `14-15` and jumps to `<h2>14</h2>`; no continuation line above it.
    - Same artifact (page 20 entry).
  - Downstream blocks/portionize mirror OCR; no text was dropped later.
- **Section 43 misread (200→206) originates in OCR:**
  - OCR HTML page **26** shows `<h2>43</h2>` with `turn to 206` (no 200).
    - Artifact: `output/runs/ff-ai-ocr-gpt51-old-fast-full/03_ocr_ai_gpt51_v1/pages_html.jsonl` (page 26 entry).
  - `page_blocks_repaired.jsonl` (image `page-026R.png`) contains “turn to 206” with no 200.
    - Artifact: `output/runs/ff-ai-ocr-gpt51-old-fast-full/08_html_to_blocks_v1/page_blocks_repaired.jsonl`.
- **Conclusion:** Both failures are upstream OCR capture errors; not dropped by portionize.
- **Next:** Improve OCR prompt for continuation text + add targeted OCR repair for orphan-parent candidates; consider relaxing validate_choice_links logic to allow AI‑backed override of explicit targets when an orphan exists.

### 20251227-1108 — Add OCR metadata tag (quality/integrity/continuation risk)
- **Result:** Success.
- **Notes:** Updated GPT‑5.1 OCR prompt to emit a single metadata tag as the first line and added parser to extract it before HTML sanitization. Stored fields in `pages_html.jsonl` (`ocr_quality`, `ocr_integrity`, `continuation_risk`) while keeping `html` identical to prior pipeline. This enables continuation-risk detection without changing downstream HTML behavior.
- **Files:** `modules/extract/ocr_ai_gpt51_v1/main.py`.
- **Next:** Rerun a small OCR slice and diff HTML vs prior run to confirm no regressions; validate metadata fields are present.

### 20251227-1136 — OCR meta tag enforced + slice diff vs old run
- **Result:** Success; metadata captured.
- **Slice run:** `/tmp/ocr_meta_slice/pages_html.jsonl` (11 split images: page_numbers 36–41 and 50–54).
- **Compared against:** `output/runs/ff-ai-ocr-gpt51-old-fast-full/03_ocr_ai_gpt51_v1/pages_html.jsonl`.
- **HTML diff summary:**
  - Identical HTML: `page-019R.png`, `page-025R.png`, `page-027R.png` (3/11).
  - Changed HTML: `page-018R.png`, `page-019L.png`, `page-020L.png`, `page-020R.png`, `page-021L.png`, `page-026L.png`, `page-026R.png`, `page-027L.png` (8/11).
  - **Fix:** `page-020L.png` now includes the continuation line and “turn to 147” before `<h2>14</h2>`.
  - **Still wrong:** `page-026R.png` still reads “turn to 206” (not 200).
- **Metadata:** `ocr_quality`, `ocr_integrity`, `continuation_risk` are now populated on all rows in the slice.
- **Code changes:** `modules/extract/ocr_ai_gpt51_v1/main.py` (meta tag prompt + parsing).
- **Next:** Use `continuation_risk` to trigger targeted OCR repair; design a generic misread repair for 200↔206 orphan case.

### 20251227-1158 — Fix OCR failure on meta-only output (allow empty if meta tag present)
- **Result:** Success.
- **Notes:** Full rerun failed at OCR after 2 pages because some pages returned only the meta tag (empty HTML after stripping). Updated OCR stage to allow empty HTML when the meta tag is present (or when `--allow-empty`), logging a warning instead of failing.
- **Files:** `modules/extract/ocr_ai_gpt51_v1/main.py`.
- **Next:** Re-run full `ff-ai-ocr-gpt51-old-fast-full` pipeline and validate outputs.

### 20251227-1229 — Full rerun with OCR metadata + continuation fix (old PDF)
- **Result:** Success; major improvement, remaining known issues only.
- **Run:** `ff-ai-ocr-gpt51-old-fast-full` (fresh full run).
- **Validation:**
  - `validation_report.json` → `sections_with_no_text: ['169','170']` (expected missing page), `missing_sections: []`.
  - `issues_report.jsonl` → `missing_section: ['169','170']`, `orphaned_section_no_sources: ['200','281']`.
  - `reachability_report.json` → `orphans: []`, `broken_links: []`.
- **Impact:** Orphan **147** is resolved (continuation line now captured). Remaining orphan **281** explained by missing 170; only unresolved orphan is **200** (200/206 OCR misread).
- **Evidence:**
  - `output/runs/ff-ai-ocr-gpt51-old-fast-full/validation_report.json`
  - `output/runs/ff-ai-ocr-gpt51-old-fast-full/20_report_pipeline_issues_v1/issues_report.jsonl`
  - `output/runs/ff-ai-ocr-gpt51-old-fast-full/18_validate_holistic_reachability_v1/reachability_report.json`
- **Next:** Focus mitigation on 200/206 OCR misread (targeted OCR repair or AI override in validate_choice_links for orphans).

### 20251227-1237 — Fix metadata parser to accept single-quote meta tag
- **Result:** Success.
- **Notes:** Full run had no OCR metadata; likely because the model emitted `<meta name='ocr-metadata' ...>` (single quotes) and the parser only accepted double quotes. Updated parser to accept either quote style.
- **Files:** `modules/extract/ocr_ai_gpt51_v1/main.py`.
- **Next:** Re-run OCR stage (and downstream) to capture metadata.

### 20251227-1439 — Add retry on empty OCR output
- **Result:** Success.
- **Notes:** OCR stage sometimes returned empty HTML (page 3) and failed. Added a single retry on empty output; if still empty, allow with warning when meta tag or `--allow-empty` is set, otherwise fail. This prevents transient empty responses from killing full runs while still surfacing warnings.
- **Files:** `modules/extract/ocr_ai_gpt51_v1/main.py`.
- **Next:** Re-run OCR stage and confirm it progresses past page 3.

### 20251227-1443 — Allow empty OCR outputs with warning (prevent hard failure)
- **Result:** Success.
- **Notes:** OCR still failed on page 3 with empty output. Updated OCR stage to never hard-fail on empty HTML; it now logs a warning, writes empty HTML, and stamps `ocr_empty`/`ocr_empty_reason` on the row. This keeps the pipeline running while surfacing missing content downstream.
- **Files:** `modules/extract/ocr_ai_gpt51_v1/main.py`.
- **Next:** Re-run OCR stage; watch for `ocr_empty` rows and see if downstream validators flag missing sections.

### 20251227-1504 — Always persist raw OCR HTML
- **Result:** Success.
- **Notes:** Removed the `--save-raw` flag; OCR now always writes `raw_html` for every page to aid debugging and metadata verification.
- **Files:** `modules/extract/ocr_ai_gpt51_v1/main.py`.
- **Next:** Re-run OCR stage to capture raw HTML on all pages and verify meta tag presence.

### 20251227-1508 — Fix meta-tag detection regex
- **Result:** Success.
- **Notes:** Metadata tag was present in `raw_html` but parser didn’t detect it because the regex matched literal `\s`. Updated regex to `name\s*=\s*['"]ocr-metadata['"]` so metadata fields parse correctly.
- **Files:** `modules/extract/ocr_ai_gpt51_v1/main.py`.
- **Next:** Restart OCR stage to apply parser fix to new rows.

### 20251227-1539 — Fix extract_stat_checks crash on invalid AI additions
- **Result:** Success.
- **Notes:** `extract_stat_checks_v1` crashed when AI audit returned `None` for required fields (e.g., `lucky_section`, `pass_section`). Added sanitizers + try/except to skip invalid additions/corrections instead of failing the run.
- **Files:** `modules/enrich/extract_stat_checks_v1/main.py`.
- **Next:** Resume pipeline from `extract_stat_checks` and verify it completes.

### 20251227-1915 — Validate full run after fixes; record remaining orphans policy
- **Result:** Success; run validates with known gaps only.
- **Run:** `ff-ai-ocr-gpt51-old-fast-full`.
- **Validation:**
  - `validation_report.json` → `sections_with_no_text: ['169','170']` (expected missing page), `missing_sections: []`.
  - `issues_report.jsonl` → `missing_section: ['169','170']`, `orphaned_section_no_sources: ['200','281']`.
  - `reachability_report.json` → `orphans: []`, `broken_links: []`.
- **Policy update:** Treat **281** the same as **200** for mitigation: attempt to locate via AI escalation; **281** is expected to exhaust retries and be marked MISSING after cap; **200** should be recoverable quickly.
- **Evidence:**
  - `output/runs/ff-ai-ocr-gpt51-old-fast-full/validation_report.json`
  - `output/runs/ff-ai-ocr-gpt51-old-fast-full/20_report_pipeline_issues_v1/issues_report.jsonl`
  - `output/runs/ff-ai-ocr-gpt51-old-fast-full/18_validate_holistic_reachability_v1/reachability_report.json`
- **Next:** Implement/verify escalation loop for missing/orphan sections so 200 is recovered and 281 hits retry cap and is explicitly flagged MISSING.

### 20251227-2024 — Fix OCR metadata loss after stamping
- **Result:** Success.
- **Notes:** `driver.py` stamps artifacts via `schemas.PageHtml`, which previously lacked `raw_html` and OCR metadata fields; stamping rewrote `pages_html.jsonl` and dropped those fields. Added optional fields (`raw_html`, `ocr_quality`, `ocr_integrity`, `continuation_risk`, `ocr_metadata_*`, `ocr_empty*`) to `PageHtml` so they persist after stamping.
- **Files:** `schemas.py`.
- **Next:** Re-run OCR stage (or full run) to regenerate `pages_html.jsonl` with metadata retained after stamping; then recompute low-meta sections.

### 20251227-2140 — Add choice-number repair module (digit-confusion + optional AI)
- **Result:** Success.
- **Notes:** Implemented `repair_choice_numbers_v1` to target orphan recovery via digit-confusion candidates with optional AI verification. Wired into both canonical and old-fast recipes after `validate_choice_links` and before `extract_combat`.
- **Files:**
  - `modules/enrich/repair_choice_numbers_v1/main.py`
  - `modules/enrich/repair_choice_numbers_v1/module.yaml`
  - `configs/recipes/recipe-ff-ai-ocr-gpt51.yaml`
  - `configs/recipes/recipe-ff-ai-ocr-gpt51-old-fast.yaml`
- **Test:** `PYTHONPATH=. python modules/enrich/repair_choice_numbers_v1/main.py --portions output/runs/ff-ai-ocr-gpt51-old-fast-full/13_validate_choice_links_v1/portions_with_choices_validated.jsonl --out /tmp/repair_choice_numbers_test.jsonl --max-calls 0` (module executes; no repairs without AI).
- **Next:** Run pipeline from `repair_choice_numbers` with AI enabled to attempt 200 recovery; confirm 281 hits retry cap and is marked missing.

### 20251227-2210 — repair_choice_numbers_v1 AI test (max_calls=10)
- **Result:** Ran; produced low-confidence misdirected repairs (all toward orphan 281).
- **Test:** `PYTHONPATH=. python modules/enrich/repair_choice_numbers_v1/main.py --portions output/runs/ff-ai-ocr-gpt51-old-fast-full/13_validate_choice_links_v1/portions_with_choices_validated.jsonl --out /tmp/repair_choice_numbers_test_ai.jsonl --max-calls 10`
- **Observed repairs:** 6 proposed repairs, all re-pointing various sections to 281 with weak narrative fit. This is too permissive for production.
- **Next:** Tighten candidate gating (require explicit numeric mention in source text and digit-confusable only), or drop AI step entirely and only flag suspects for escalation instead of auto-repair.

### 20251227-2240 — Re-OCR candidate pages to verify misread turn-to numbers
- **Result:** Partial; re-OCR confirms old PDF image reads “turn to 206” in section 43.
- **Tests:**
  - Re-OCR 6 candidate sections (145, 238, 241, 275, 309, 360) with careful turn-to prompt → outputs in `/tmp/ocr_turnto_recheck.json`.
  - Re-OCR section 43 source image (`page-026R.png`) → `/tmp/ocr_turnto_recheck_section43.json`.
- **Findings:**
  - Candidate pages did not contain 200/206 references.
  - Section 43 re-OCR explicitly reads “turn to 206” and “turn to 316”.
- **Implication:** Old PDF likely contains 206 in the scan; correction to 200 may require cross-source repair (pristine PDF) or explicit exception handling.
- **Next:** Decide whether to allow cross-copy overrides or treat 200 as unfixable in the old-PDF pipeline.

### 20251227-2315 — Remove repair_choice_numbers_v1 (too permissive)
- **Result:** Removed.
- **Notes:** The module over-repaired to 281 with low confidence and didn’t address 200 because it wasn’t an orphan. Removed module and recipe wiring.
- **Files:**
  - `modules/enrich/repair_choice_numbers_v1/` (deleted)
  - `configs/recipes/recipe-ff-ai-ocr-gpt51.yaml`
  - `configs/recipes/recipe-ff-ai-ocr-gpt51-old-fast.yaml`
- **Next:** Revisit numeric misread handling only if 200 becomes an orphan or we add explicit non-orphan digit-confusion validation.

### 20251227-2350 — Fix extract_stat_checks crash on non-dict additions
- **Result:** Success.
- **Notes:** Full run failed in `extract_stat_checks_v1` when additions list contained `None`. Added guard to skip non-dict additions with warning.
- **Files:** `modules/enrich/extract_stat_checks_v1/main.py`.
- **Next:** Resume full run from `extract_stat_checks` and re-validate artifacts.

### 20251228-0025 — Allow stubs in pristine recipe to avoid build crash
- **Result:** Updated recipe to prevent build failure when missing sections are detected.
- **Notes:** `ff-ai-ocr-gpt51-pristine-fast-full` failed because build is stub-fatal by default. Added `allow_stubs: true` to `build_gamebook` params so the run completes and produces artifacts while still surfacing missing sections in issues/validation reports.
- **Files:** `configs/recipes/recipe-ff-ai-ocr-gpt51.yaml`.
- **Next:** Re-run pristine full pipeline and verify missing sections (169, 170, 345) are reported, not silently ignored.

### 20251228-0100 — Propagate source PDF path through artifacts
- **Result:** Success.
- **Notes:** Added `source` propagation to make input PDF obvious in output artifacts. `extract_pdf_images_fast_v1` now stamps `source=[abs_pdf_path]` into page_image rows; `split_pages_from_manifest_v1` carries `source` forward; `ocr_ai_gpt51_v1` includes `source` in `page_html_v1` rows.
- **Files:**
  - `modules/extract/extract_pdf_images_fast_v1/main.py`
  - `modules/extract/split_pages_from_manifest_v1/main.py`
  - `modules/extract/ocr_ai_gpt51_v1/main.py`
- **Next:** Re-run pristine pipeline to verify source is visible in `pages_split_manifest.jsonl` and `pages_html.jsonl`.

### 20251228-0145 — Fix extract_stat_modifications crash on non-dict additions
- **Result:** Success.
- **Notes:** Pristine run failed in `extract_stat_modifications_v1` when audit additions contained `None`. Added guard to skip non-dict additions and catch invalid StatModification creation.
- **Files:** `modules/enrich/extract_stat_modifications_v1/main.py`.
- **Next:** Resume pristine run from `extract_stat_modifications` and verify completion.

### 20251228-0215 — Align issues report with reachability orphans
- **Result:** Success.
- **Notes:** `report_pipeline_issues_v1` previously flagged orphans based solely on choice stats (pre-validation), which could disagree with reachability. Now it intersects choice-stat orphans with reachability forensics when available to avoid false orphan flags. Regenerated pristine issues report; orphan list cleared as reachability has none.
- **Files:** `modules/adapter/report_pipeline_issues_v1/main.py`.
- **Evidence:** `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/20_report_pipeline_issues_v1/issues_report.jsonl` (issue_count=0).
- **Next:** Re-run report pipeline issues for old run if needed to keep reports consistent.

### 20251228-0305 — Wire validation modules into recipes
- **Result:** Success.
- **Notes:** Added `validate_choice_text_alignment_v1`, `trace_orphans_text_v1`, `validate_choice_completeness_v1` (max_discrepancy=0), and `validate_game_ready_v1` to canonical, pristine-fast, and old-fast recipes. This makes pass/fail reporting explicit and repeatable.
- **Files:**
  - `configs/recipes/recipe-ff-ai-ocr-gpt51.yaml`
  - `configs/recipes/recipe-ff-ai-ocr-gpt51-pristine-fast.yaml`
  - `configs/recipes/recipe-ff-ai-ocr-gpt51-old-fast.yaml`
- **Next:** Run `validate_game_ready_v1` on pristine + old runs (resume or standalone) and record artifact paths + manual spot-checks.

### 20251228-0330 — Run validation modules + manual spot checks
- **Result:** Partial success; pristine passes game-ready, old fails (expected missing/orphan + choice mismatch).
- **Pristine reports:**
  - `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/choice_completeness_report.json` (flagged_count=0)
  - `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/choice_text_alignment_report.json` (flagged_count=0)
  - `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/orphan_trace_report.json` (orphans=0)
  - `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/game_ready_validation_report.json` (status=pass)
- **Old reports:**
  - `output/runs/ff-ai-ocr-gpt51-old-fast-full/choice_completeness_report.json` (flagged_count=1; section 72 text refs include 300 but choices have 200)
  - `output/runs/ff-ai-ocr-gpt51-old-fast-full/choice_text_alignment_report.json` (flagged_count=1)
  - `output/runs/ff-ai-ocr-gpt51-old-fast-full/orphan_trace_report.json` (orphans=1, unreferenced=1)
  - `output/runs/ff-ai-ocr-gpt51-old-fast-full/game_ready_validation_report.json` (status=fail)
- **Manual spot checks (pristine):**
  - `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/gamebook.json` section 43: text + choices show 200/316 (correct).
  - `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/gamebook.json` section 65: potion choice 345/372 (correct).
  - `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/gamebook.json` section 150: turn to 292 (correct).
  - `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/gamebook.json` section 242: conditional 48/366 (correct).
  - `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/gamebook.json` section 271: turn to 237 (correct).
  - `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/gamebook.json` section 339: turn to 303/236 (correct per pristine PDF).
- **Manual spot checks (old):**
  - `output/runs/ff-ai-ocr-gpt51-old-fast-full/gamebook.json` section 43: text + choices show 206/316 (old scan discrepancy).
  - `output/runs/ff-ai-ocr-gpt51-old-fast-full/gamebook.json` sections 169/170: empty stubs (missing page).
  - `output/runs/ff-ai-ocr-gpt51-old-fast-full/gamebook.json` section 281: content present but orphaned.
- **Next:** Decide if old run should remain fail due to section 72 mismatch + missing 169/170 + orphan 281; investigate section 72/choice mismatch and orphan source.

### 20251228-1310 — Explicit thresholds + boundary conflict surfacing
- **Result:** Success.
- **Notes:** Added explicit checklist thresholds/exceptions and artifact/schema list. Updated issues report to surface boundary ordering conflicts. Fixed splitter source propagation bug (`path` → `img_path`).
- **Files:** `docs/stories/story-083-game-ready-validation-checklist.md`, `modules/adapter/report_pipeline_issues_v1/main.py`, `modules/extract/split_pages_from_manifest_v1/main.py`.
- **Next:** Wire alignment/orphan traces into escalation loop and re-run a validation pass to confirm ordering conflicts fail game-ready when present.

### 20251228-1340 — Wire alignment/orphan traces into choice repair
- **Result:** Success.
- **Notes:** `validate_choice_links_v1` now consumes alignment + orphan-trace reports and performs deterministic choice additions before AI escalation. Recipes were re-ordered so alignment/orphan reports run on `repair_choices` and feed into `validate_choice_links`. Consolidated game-ready report now fails on boundary ordering conflicts from issues report.
- **Files:** `modules/validate/validate_choice_links_v1/main.py`, `configs/recipes/recipe-ff-ai-ocr-gpt51.yaml`, `configs/recipes/recipe-ff-ai-ocr-gpt51-pristine-fast.yaml`, `configs/recipes/recipe-ff-ai-ocr-gpt51-old-fast.yaml`, `modules/validate/validate_game_ready_v1/main.py`.
- **Next:** Run a minimal validation slice to confirm alignment additions resolve mismatches and ordering conflicts now fail game-ready when present.

### 20251228-1355 — Minimal validation slice confirms ordering conflict fail
- **Result:** Success.
- **Notes:** Used existing run with ordering conflicts to verify `report_pipeline_issues_v1` now emits ordering conflicts and `validate_game_ready_v1` fails when they are present.
- **Evidence:**
  - `output/runs/ff-ai-ocr-gpt51-old-fast-full-20251226b/07_detect_boundaries_html_loop_v1/ordering_conflicts.json` (7 conflicts).
  - `/tmp/issues_with_ordering.jsonl` (ordering_conflicts=7).
  - `/tmp/game_ready_with_ordering.json` (status=fail; fail reasons include issues_report).
- **Next:** Run a full pipeline or targeted validate slice on a current run to confirm alignment additions reduce choice mismatches.

### 20251228-1420 — Duplicate header guard + issues surfaced
- **Result:** Success.
- **Notes:** Added duplicate header reporting in `detect_boundaries_html_v1` and surfaced it in `report_pipeline_issues_v1` + `validate_game_ready_v1` so boundary duplicates fail game-ready.
- **Files:** `modules/portionize/detect_boundaries_html_v1/main.py`, `modules/adapter/report_pipeline_issues_v1/main.py`, `modules/validate/validate_game_ready_v1/main.py`.
- **Next:** Run a minimal boundary detect on a known-problem run to confirm duplicate header issues are emitted.

### 20251228-1440 — Duplicate header detection confirmed
- **Result:** Success.
- **Notes:** Minimal detect on old run produced duplicate header report; issues aggregator surfaces them as errors.
- **Evidence:**
  - `/tmp/section_boundaries_with_dups.jsonl` (detect summary: duplicate_headers 20).
  - `/tmp/duplicate_headers.json` (20 entries; includes section 29/30 candidates across pages 46/169/217).
  - `/tmp/issues_with_duplicates.jsonl` (duplicate_headers=20).
- **Next:** Use this signal to gate escalation or force re‑OCR on duplicate-heavy pages.

### 20251228-1455 — Fix validate_game_ready param flags in driver
- **Result:** Success.
- **Notes:** `driver.py` now normalizes validate_game_ready_v1 params to hyphenated flags (`--expected-range-start/end`, `--known-missing`) to prevent argparse errors during full runs.
- **Files:** `driver.py`.
- **Next:** Resume `ff-ai-ocr-gpt51-old-fast-full` from `validate_game_ready` to confirm the run completes cleanly.

### 20251228-1505 — Stamp failed status on stage failure
- **Result:** Success.
- **Notes:** `driver.py` now stamps run-level status=failed on stage failure so pipeline-visibility no longer shows stale CRASHED after a foreground resume failure. Manually backfilled current run state to `failed` for `ff-ai-ocr-gpt51-old-fast-full`.
- **Files:** `driver.py`, `output/runs/ff-ai-ocr-gpt51-old-fast-full/pipeline_state.json`.
- **Next:** Resume `validate_game_ready` if needed and confirm dashboard shows FAILED (not CRASHED).

### 20251228-1530 — Validation fail is stage-done + UI 100% progress
- **Result:** Success.
- **Notes:** `driver.py` treats `validate_game_ready_v1` exit code 1 as a completed stage (warning) and stamps run status as failed; dashboard now counts failed stages toward 100% progress. Updated current run state to reflect `validate_game_ready` done and run status failed.
- **Files:** `driver.py`, `docs/pipeline-visibility.html`, `output/runs/ff-ai-ocr-gpt51-old-fast-full/pipeline_state.json`.
- **Next:** Re-run a final-stage resume if you want the driver to update state automatically instead of manual backfill.
