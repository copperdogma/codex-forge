# Story 128: Onward Table Fidelity Verification

**Status**: In Progress (Golden References & Baseline Eval Complete)

---
**Depends On**: story-026 (Onward to the Unknown pipeline)
**Blocks**: story-129 (HTML output polish)

## Goal
Verify that every genealogy table in *Onward to the Unknown* faithfully represents the original scan — no LLM normalization, no column drift, no invented/dropped data. Fix anything that's wrong.

This is the hardest problem in the Onward pipeline. The genealogy tables use an unusual NAME / BORN / MARRIED / SPOUSE / BOY / GIRL / DIED column layout where data doesn't always align rationally with headers (remarriages span rows, BOY/GIRL counts are sometimes combined, dates appear in unexpected columns). LLMs consistently try to "fix" or normalize this data, which corrupts it.

## Context
- **Full book**: 127 pages (Image000–Image126); only ~60 have been processed so far.
- **Genealogy table pages** (identified by pipeline): ~18 pages in the 60-page subset. More expected in the remaining 67 pages.
- **Known failure modes** (from Story 026 iterations):
  - LLM normalization: reordering, reformatting, or "correcting" irregular data
  - BOY/GIRL count merging (e.g., "11 4" in one cell instead of split columns)
  - Continuation-row misalignment (remarriage lines, multi-line spouse names)
  - Date drift (dates shifting to adjacent rows)
  - Column count mismatches (missing or extra columns vs. the scan)
  - Running heads / page numbers leaking into table cells

## Acceptance Criteria
- [x] **Full book processed**: All 127 pages run through the Onward pipeline (Completed in `onward-full-127-table-fidelity`).
- [ ] **Every genealogy table manually verified**: 3 of 3 Multi-page Golden References are verified (covering ~15 images). 50 individual pages in checklist remain `Pending`.
- [ ] **All critical discrepancies fixed**: Resolved in Golden References for eval. Production module fix pending.
- [x] **Verification checklist recorded**: Fully populated with 53 table-bearing pages.
- [ ] **No regressions on passing pages**: Pending final pipeline run with improved module logic.

## Approach
This is primarily a **manual verification story** — the human compares pipeline output against scans and the pipeline is iterated until the output is faithful. The workflow:

1. **Run the full 127-page pipeline** (expand beyond the 60-page subset).
2. **Identify all genealogy table pages** in the full output.
3. **For each table page**: open the scan image and the pipeline HTML side-by-side. Compare every cell. Record pass/fail + specific issues.
4. **Batch fix**: Group similar failures (e.g., "all BOY/GIRL merges") and fix at the prompt/post-processing level rather than per-page patches.
5. **Re-run and re-verify** until all tables pass or remaining issues are documented as accepted limitations.

## Verification Checklist
<!-- Full 127-page run `output/runs/onward-full-127-table-fidelity/07_table_fix_continuations_v1/pages_html_onward_tables_fixed.jsonl`. -->
| Page (Artifact `page`) | Printed Page | Chapter | Status | Issues |
|------|-------------|---------|--------|--------|
| 8 | vii | TBD | Pending | TO VERIFY against `input/onward-to-the-unknown-images/Image007.jpg` |
| 10 | 1 | TBD | Pending | TO VERIFY against `input/onward-to-the-unknown-images/Image009.jpg` |
| 12 | 3 | TBD | Pending | TO VERIFY against `input/onward-to-the-unknown-images/Image011.jpg` |
| 20 | 11 | TBD | Pending | TO VERIFY against `input/onward-to-the-unknown-images/Image019.jpg` |
| 23 | 14 | TBD | Pending | TO VERIFY against `input/onward-to-the-unknown-images/Image022.jpg` |
| 24 | 15 | TBD | Pending | TO VERIFY against `input/onward-to-the-unknown-images/Image023.jpg` |
| 25 | 16 | TBD | Pending | TO VERIFY against `input/onward-to-the-unknown-images/Image024.jpg` |
| 26 | 17 | TBD | Pending | TO VERIFY against `input/onward-to-the-unknown-images/Image025.jpg` |
| 30 | 21 | TBD | Pending | TO VERIFY against `input/onward-to-the-unknown-images/Image029.jpg` |
| 31 | 22 | TBD | Pending | TO VERIFY against `input/onward-to-the-unknown-images/Image030.jpg` |
| 32 | 23 | TBD | Pending | TO VERIFY against `input/onward-to-the-unknown-images/Image031.jpg` |
| 33 | 24 | TBD | Pending | TO VERIFY against `input/onward-to-the-unknown-images/Image032.jpg` |
| 34 | 25 | TBD | Pending | TO VERIFY against `input/onward-to-the-unknown-images/Image033.jpg` |
| 35 | 26 | TBD | Pending | TO VERIFY against `input/onward-to-the-unknown-images/Image034.jpg` |
| 39 | 30 | TBD | Pending | TO VERIFY against `input/onward-to-the-unknown-images/Image038.jpg` |
| 40 | 31 | TBD | Pending | TO VERIFY against `input/onward-to-the-unknown-images/Image039.jpg` |
| 41 | 32 | TBD | Pending | TO VERIFY against `input/onward-to-the-unknown-images/Image040.jpg` |
| 42 | 33 | TBD | Pending | TO VERIFY against `input/onward-to-the-unknown-images/Image041.jpg` |
| 43 | 34 | TBD | Pending | TO VERIFY against `input/onward-to-the-unknown-images/Image042.jpg` |
| 44 | 35 | TBD | Pending | TO VERIFY against `input/onward-to-the-unknown-images/Image043.jpg` |
| 45 | 36 | TBD | Pending | TO VERIFY against `input/onward-to-the-unknown-images/Image044.jpg` |
| 49 | 40 | TBD | Pending | TO VERIFY against `input/onward-to-the-unknown-images/Image048.jpg` |
| 50 | 41 | TBD | Pending | TO VERIFY against `input/onward-to-the-unknown-images/Image049.jpg` |
| 51 | 42 | TBD | Pending | TO VERIFY against `input/onward-to-the-unknown-images/Image050.jpg` |
| 56 | 47 | TBD | Pending | TO VERIFY against `input/onward-to-the-unknown-images/Image055.jpg` |
| 57 | 48 | TBD | Pending | TO VERIFY against `input/onward-to-the-unknown-images/Image056.jpg` |
| 62 | 53 | TBD | Pending | TO VERIFY against `input/onward-to-the-unknown-images/Image061.jpg` |
| 63 | 54 | TBD | Pending | TO VERIFY against `input/onward-to-the-unknown-images/Image062.jpg` |
| 64 | 55 | TBD | Pending | TO VERIFY against `input/onward-to-the-unknown-images/Image063.jpg` |
| 67 | 58 | TBD | Pending | TO VERIFY against `input/onward-to-the-unknown-images/Image066.jpg` |
| 68 | 59 | TBD | Pending | TO VERIFY against `input/onward-to-the-unknown-images/Image067.jpg` |
| 69 | 60 | TBD | Pending | TO VERIFY against `input/onward-to-the-unknown-images/Image068.jpg` |
| 74 | 65 | TBD | Pending | TO VERIFY against `input/onward-to-the-unknown-images/Image073.jpg` |
| 75 | 66 | TBD | Pending | TO VERIFY against `input/onward-to-the-unknown-images/Image074.jpg` |
| 80 | 71 | TBD | Pending | TO VERIFY against `input/onward-to-the-unknown-images/Image079.jpg` |
| 81 | 72 | TBD | Pending | TO VERIFY against `input/onward-to-the-unknown-images/Image080.jpg` |
| 82 | 73 | TBD | Pending | TO VERIFY against `input/onward-to-the-unknown-images/Image081.jpg` |
| 83 | 74 | TBD | Pending | TO VERIFY against `input/onward-to-the-unknown-images/Image082.jpg` |
| 84 | 75 | TBD | Pending | TO VERIFY against `input/onward-to-the-unknown-images/Image083.jpg` |
| 88 | 79 | TBD | Pending | TO VERIFY against `input/onward-to-the-unknown-images/Image087.jpg` |
| 93 | 84 | TBD | Pending | TO VERIFY against `input/onward-to-the-unknown-images/Image092.jpg` |
| 94 | 85 | TBD | Pending | TO VERIFY against `input/onward-to-the-unknown-images/Image093.jpg` |
| 97 | 88 | TBD | Pending | TO VERIFY against `input/onward-to-the-unknown-images/Image096.jpg` |
| 98 | 89 | TBD | Pending | TO VERIFY against `input/onward-to-the-unknown-images/Image097.jpg` |
| 99 | 90 | TBD | Pending | TO VERIFY against `input/onward-to-the-unknown-images/Image098.jpg` |
| 104 | 95 | TBD | Pending | TO VERIFY against `input/onward-to-the-unknown-images/Image103.jpg` |
| 105 | 96 | TBD | Pending | TO VERIFY against `input/onward-to-the-unknown-images/Image104.jpg` |
| 106 | 97 | TBD | Pending | TO VERIFY against `input/onward-to-the-unknown-images/Image105.jpg` |
| 111 | 102 | TBD | Pending | TO VERIFY against `input/onward-to-the-unknown-images/Image110.jpg` |
| 112 | 103 | TBD | Pending | TO VERIFY against `input/onward-to-the-unknown-images/Image111.jpg` |
| 113 | 104 | TBD | Pending | TO VERIFY against `input/onward-to-the-unknown-images/Image112.jpg` |
| 117 | 108 | TBD | Pending | TO VERIFY against `input/onward-to-the-unknown-images/Image116.jpg` |
| 126 | 117 | TBD | Pending | TO VERIFY against `input/onward-to-the-unknown-images/Image125.jpg` |

## Golden References (Multi-page)
To create a rigorous `promptfoo` evaluation, we have built 3 perfect, AI-led golden references. Each represents a single logical table that spans multiple printed pages. The goal is 100% strict visual column alignment fidelity.

1. **Alma L'Heureux Alain** (Verified 100%)
   - Source Images: `Image022.jpg`, `Image023.jpg`, `Image024.jpg`, `Image025.jpg`
   - Golden Path: `benchmarks/golden/onward/alma.html`
2. **Arthur L'Heureux** (Verified 100%)
   - Source Images: `Image029.jpg`, `Image030.jpg`, `Image031.jpg`, `Image032.jpg`, `Image033.jpg`, `Image034.jpg`
   - Golden Path: `benchmarks/golden/onward/arthur.html`
3. **Marie Louise L'Heureux LaClare** (Verified 100%)
   - Source Images: `Image079.jpg`, `Image080.jpg`, `Image081.jpg`, `Image082.jpg`, `Image083.jpg`
   - Golden Path: `benchmarks/golden/onward/marie_louise.html`

## Tasks
- [x] Run full 127-page pipeline with `configs/recipes/recipe-onward-images-html-mvp.yaml` and a new run id (no subset limits in run config) (Started 2026-02-22)
- [x] Confirm artifact existence for table pipeline chain:
  - [x] `output/runs/<run_id>/02_ocr_ai_gpt51_v1/pages_html.jsonl`
  - [x] `output/runs/<run_id>/04_table_rescue_html_loop_v1/pages_html_rescued.jsonl`
  - [x] `output/runs/<run_id>/06_table_rescue_onward_tables_v1/pages_html_onward_tables.jsonl`
  - [x] `output/runs/<run_id>/07_table_fix_continuations_v1/pages_html_onward_tables_fixed.jsonl`
  - [x] `output/runs/<run_id>/09_build_chapter_html_v1/chapters_manifest.jsonl`
- [x] Enumerate all pages containing `<table` from `07_table_fix_continuations_v1/pages_html_onward_tables_fixed.jsonl`
- [x] Add every table-bearing page to the verification checklist (page id + printed page + source image path + chapter)
- [x] Create Multi-page Golden References for representative family groups (Alma, Arthur, Marie Louise)
- [x] Set up `promptfoo` benchmark with custom HTML table structural diff scorer
- [x] Run baseline evaluation sweep (Results: Single-pass VLM fails 100% fidelity goal)
- [ ] Manual verification pass #1 (cell-by-cell): classify remaining individual pages as `Pass`, `Fail`, or `Accepted Limitation`
- [ ] For each `Fail`, record normalized failure tag(s): `boy_girl_merge`, `continuation_drift`, `date_drift`, `column_count_mismatch`, `header_or_page_leak`, `other`
- [ ] Implement fixes in modules/prompts (no hand edits to output artifacts)
- [ ] Re-run from earliest changed stage using `--start-from` and inspect regenerated artifacts in `output/runs/<run_id>/`
- [ ] Manual verification pass #2 on all previously failing pages
- [ ] Regression sweep: re-check at least 5 previously passing table pages after fixes
- [ ] Final sign-off: 100% of discovered table pages are `Pass` or explicitly `Accepted Limitation` with rationale

## Execution Commands
```bash
# 1) Full 127-page run (new run id)
scripts/run_driver_monitored.sh \
  --recipe configs/recipes/recipe-onward-images-html-mvp.yaml \
  --run-id onward-full-127-table-fidelity \
  --output-dir output/runs \
  -- --instrument --force

# 2) Enumerate table-bearing pages from final table-fixed artifact
python - <<'PY'
import json
path = "output/runs/onward-full-127-table-fidelity/07_table_fix_continuations_v1/pages_html_onward_tables_fixed.jsonl"
for line in open(path):
    o = json.loads(line)
    html = (o.get("html") or "").lower()
    if "<table" in html:
        print({
            "page": o.get("page"),
            "printed_page": o.get("printed_page_number_text") or o.get("printed_page_number"),
            "image": o.get("image"),
        })
PY
```

## Non-Negotiables
- **No normalization**: Pipeline output must match the scan exactly, even when the original data looks "wrong" or inconsistent.
- **Cell-level fidelity**: Every cell in the HTML table must match the corresponding cell in the scan. Column assignment matters.
- **Fix at the pipeline level**: Don't manually edit HTML output. If something is wrong, fix the prompt, post-processing, or table rescue logic so it's correct for all similar cases.

## Work Log
### 20260222-0001 — Started full 127-page pipeline run
- **Result:** In Progress.
- **Notes:** Initiated the full pipeline run `onward-full-127-table-fidelity` using `scripts/run_driver_monitored.sh`. Verified the run directory was created and logs are active. The process is running in the background.
- **Next:** Monitor `output/runs/onward-full-127-table-fidelity/pipeline_events.jsonl` until completion, then proceed to artifact confirmation.

### 20260223-0400 — Fix: `ResponseUsage` serialization error
- **Result:** Success (code fixed, pipeline restarting).
- **Notes:** The initial run failed at 92% (page 117/127) during `onward_table_rescue` with `TypeError: Object of type ResponseUsage is not JSON serializable`. This was caused by the `google.generativeai` client returning a Pydantic-like usage object that `json.dumps` couldn't handle.
- **Fix:** Added a `_model_to_dict` helper to `modules/adapter/table_rescue_onward_tables_v1/main.py` to safely convert the usage object to a dict before serialization. Confirmed fix with a reproduction script.
- **Action:** Restarted the full 127-page run (`onward-full-127-table-fidelity`) from scratch, as the `--force` flag with `--start-from` inadvertently cleared the previous run's artifacts. The pipeline is now re-running from the OCR stage.
- **Next:** Wait for the full run to complete (ETA ~2 hours).

### 20260223-0415 — Run Paused: Daily Quota Exceeded
- **Result:** Blocked.
- **Notes:** The restarted run failed at page 10/127 with `429 RESOURCE_EXHAUSTED` (Gemini API daily quota exceeded). This likely occurred because the first run consumed most of the daily quota processing ~117 pages before crashing.
- **Status:** Paused. We must wait for the API quota to reset before resuming.
- **Next:** Resume the run (using `--start-from ocr_ai` or standard resume logic) once quota is available.

### 20260223-1400 — Run Resumed
- **Result:** In Progress.
- **Notes:** API quota has reset. Resumed the pipeline run `onward-full-127-table-fidelity` using `--start-from ocr_ai` and `--allow-run-id-reuse`.
- **Status:** Running (PID: 89248). OCR stage completed (127/127). Currently running `crop_illustrations` (processing 29 pages with images).
- **Next:** Monitor for full pipeline completion.

### 20260220-0002 — Story format + checklist audit
- **Result:** Success.
- **Notes:** Opened `/Users/cam/Documents/Projects/codex-forge/docs/stories/story-128-onward-table-fidelity-verification.md`; confirmed required house sections exist (`Status`, `Acceptance Criteria`, `Tasks`, `Work Log`). `## Tasks` existed but was too high-level for execution traceability.
- **Next:** Expand tasks into explicit, testable steps with concrete artifact paths and verification gates.

### 20260220-0002 — Baseline artifact reconnaissance for table pages
- **Result:** Success (planning data captured).
- **Notes:** Inspected `/Users/cam/Documents/Projects/codex-forge/configs/recipes/recipe-onward-images-html-mvp.yaml` and prior run artifacts under `/Users/cam/Documents/Projects/codex-forge/output/runs/onward-canonical/`. Extracted 19 table-bearing pages from `/Users/cam/Documents/Projects/codex-forge/output/runs/onward-canonical/07_table_fix_continuations_v1/pages_html_onward_tables_fixed.jsonl` with page ids and source images to seed verification.
- **Next:** Seed checklist rows with these baseline pages so future full-book verification has a concrete starting set and gap visibility.

### 20260220-0002 — Task expansion + checklist seeding
- **Result:** Success.
- **Notes:** Updated `## Tasks` with actionable checklist items tied to stage artifacts, rerun strategy, failure-tag taxonomy, and regression gate. Seeded `## Verification Checklist` with 19 baseline table pages from the existing subset run, each marked `Pending (subset baseline)` for manual side-by-side validation.
- **Next:** Execute the first unchecked task: run a full 127-page pipeline and replace/extend seeded rows with full-book table-page discovery.

### 20260220-0003 — Added execution command block for immediate kickoff
- **Result:** Success.
- **Notes:** Added `## Execution Commands` with copy-paste commands for the full 127-page run and deterministic extraction of table-bearing pages from stamped artifacts. This removes ambiguity around run id, artifact path, and table-page discovery mechanics.
- **Next:** Run the full pipeline with the command block, then populate checklist status per page (`Pass`/`Fail`/`Accepted Limitation`).

### 20260220-0003 — Corrected run command to monitored wrapper
- **Result:** Success.
- **Notes:** Replaced direct `driver.py --force` example with `scripts/run_driver_monitored.sh ... -- --instrument --force` to match repo guidance and avoid the `driver.py` `--force`/`output/runs` root conflict.
- **Next:** Execute monitored full run and track progress in `output/runs/onward-full-127-table-fidelity/pipeline_events.jsonl`.
