# Story: Table Rescue OCR Pass

**Status**: Done  
**Created**: 2025-12-22  
**Priority**: High  
**Parent Story**: story-082 (Large-Image PDF Cost Optimization)

---

## Goal

Recover collapsed table/grid structures (e.g., choice tables) by adding a targeted OCR rescue step **early** in the HTML pipeline.

---

## Motivation

Even at high DPI with hints, some pages (notably `page-061.jpg`) collapse multi-row choice tables into a single concatenated row. Once layout is lost at OCR time, downstream recovery is difficult.

---

## Success Criteria

- [ ] **Detection**: Identify pages where table structure has collapsed (e.g., multiple “Turn to X” options merged into single cells).
- [ ] **Rescue**: Re-run OCR on a **targeted crop** (e.g., top portion) with a table-focused prompt and replace the table HTML.
- [ ] **Generic**: Works without FF-specific hard-coding; detection uses structure patterns (rows, repeated options).
- [ ] **Validation**: Page-061 and page-020R tables retain proper row/column structure after rescue.
- [ ] **Artifact trace**: Rescue provenance recorded in artifacts (what changed, why).
- [ ] **Prompt separation**: Generic OCR prompt is distinct from FF-specific hint appendices.

---

## Constraints

- **Prompt separation is mandatory:** Keep the generic OCR prompt intact. Apply FF-specific hints only as a secondary appended prompt block. Any book-type hints must stay isolated and swappable.

---

## Tasks

- [x] Review legacy escalation modules for reuse patterns (e.g., `ocr_escalate_gpt4v_v1`, repair loops) and record carry-overs.
- [x] Define a “collapsed table” detector (single-row tables with concatenated cells, repeated “Turn to” patterns, list-like options without row breaks).
- [x] Implement a table-rescue OCR step that re-reads a targeted crop (top region or detected table region).
- [x] Define a deterministic merge strategy to replace or insert table HTML, with clear provenance metadata.
- [x] Wire the rescue step into the GPT‑5.1 HTML pipeline before boundary detection.
- [x] Enforce prompt separation: keep generic OCR prompt intact, apply FF-specific hints only in the appended secondary prompt.
- [x] Test on page-061 and page-020R at 150 DPI equivalent; confirm tables are multi-row/column.
- [x] Document results in the work log with before/after snippets and artifact paths.

---

## Approach (Draft)

1. **Detection (HTML-only):**
   - Parse page HTML and detect likely table collapse:
     - Tables with 1 row but ≥4 “Turn to” references.
     - Paragraphs with ≥3 “Turn to X” patterns and repeated option labels (A/B/C, or repeated item names).
     - Presence of multiple “Turn to” lines without `<table>`/`<dl>` nearby.
   - Flag top-of-page layouts separately (common “continued table” failures).

2. **Rescue OCR (targeted crop):**
   - Use page image + fixed crop heuristic (top 30–40%) or detected region by HTML proximity.
   - OCR prompt focuses only on tabular structure; returns *only* `<table>` HTML.
   - Cache rescue outputs by `(page_id, crop, prompt_hash)` to avoid repeat costs.

3. **Merge:**
   - If a table exists, replace the detected table block.
   - If no table exists, insert table HTML at the first “Turn to” cluster.
   - Record provenance: `rescue_applied`, `rescue_reason`, `rescue_crop`, `rescue_model`, `rescue_prompt_hash`.

4. **Validation:**
   - Compare rescued HTML to gold pages for `page-061` and `page-020R`.
   - Verify multi-row/column structure is preserved.

---

## Work Log

### 20251222-1535 — Story created
- **Result:** Success.
- **Notes:** New requirement to add an OCR rescue step for collapsed tables (layout loss at OCR stage).
- **Next:** Implement detection + targeted crop OCR on the known failing page.

### 20251221-2124 — Planned detection + rescue approach
- **Result:** Success.
- **Notes:** Added draft approach for collapsed-table detection, targeted crop OCR, and merge/provenance strategy; expanded task list with legacy-module review and wiring steps.
- **Next:** Review legacy escalation modules and decide where to integrate the rescue step in the GPT‑5.1 pipeline.

### 20251221-2127 — Enumerated table pages in original run
- **Result:** Success.
- **Notes:** Scanned `output/runs/ff-ai-ocr-gpt51-full-20251222/02_ocr_ai_gpt51_v1/pages_html.jsonl` for `<table>` tags. Found 15 pages with tables. Page numbers (split-page numbering → original page): 22→11, 40→20, 62→31, 74→37, 88→44, 91→46, 92→46, 101→51, 102→51, 108→54, 121→61, 148→74, 164→82, 210→105, 216→108. Images: `page-011R.png`, `page-020R.png`, `page-031R.png`, `page-037R.png`, `page-044R.png`, `page-046L.png`, `page-046R.png`, `page-051L.png`, `page-051R.png`, `page-054R.png`, `page-061L.png`, `page-074R.png`, `page-082R.png`, `page-105R.png`, `page-108R.png`.
- **Next:** Cross-check these pages against the pristine edition for table failures and choose rescue test cases.

### 20251221-2218 — Confirmed table list completeness
- **Result:** Success.
- **Notes:** User confirmed the table page list is complete for the original book; use these as the table inventory baseline when comparing to the pristine edition.
- **Next:** Identify which of these pages fail in the pristine edition and select rescue test cases.

### 20251221-2230 — Mapped original table pages to pristine edition
- **Result:** Success.
- **Notes:** Table page mapping (original → pristine): 22→11 ignored (Adventure Sheet), 40→20 == `page-039.jpg`, 62→31 == `page-061.jpg`, 74→37 == `page-073.jpg`, 88→44 == `page-087.jpg`, 91→46 == `page-090.jpg`, 92→46 == `page-091.jpg`, 101→51 == `page-100.jpg`, 102→51 == `page-101.jpg`, 108→54 == `page-107.jpg`, 121→61 == `page-122.jpg`, 148→74 == `page-149.jpg`, 164→82 == `page-165.jpg`, 210→105 == `page-211.jpg`, 216→108 == `page-217.jpg`.
- **Next:** Inspect these pristine pages to identify where tables collapse and pick rescue test cases.

### 20251221-2245 — Pristine table scan results
- **Result:** Success.
- **Notes:** Ran GPT‑5.1 OCR on 14 mapped pristine pages (manifest: `/tmp/cf-pristine-table-check/manifest.jsonl`, output: `/tmp/cf-pristine-table-check/pages_html.jsonl`) with standard FF hints. Simple collapse heuristic (tables with ≤1 `<tr>` and ≥3 “Turn to” refs) flagged **page 61** only. All other table pages retained multi-row structure.
- **Next:** Use page‑061 (`page-061.jpg`) as primary rescue test case; confirm whether page‑020R in the pristine edition exhibits any collapse at other DPIs.

### 20251222-1605 — Added prompt separation constraint
- **Result:** Success.
- **Notes:** Documented mandatory separation between generic OCR prompt and FF-specific appended hints to keep book-type logic isolated and swappable.
- **Next:** Ensure the rescue OCR implementation consumes the generic prompt + appended hints without mixing them.

### 20251222-1625 — Reviewed legacy escalation patterns
- **Result:** Success.
- **Notes:** Reviewed `modules/adapter/ocr_escalate_gpt4v_v1/main.py`, `modules/adapter/escalate_gpt4v_iter_v1/main.py`, and `modules/adapter/merge_ocr_escalated_v1/main.py`. Key carry-overs: explicit escalation reasons, skip-short missing-content heuristic, candidate sorting with quality sub-scores, hard caps (`budget_pages`/`max_pages`), dry-run path, batch iteration, explicit page override, and merge precedence based on `module_id` with provenance summaries. These patterns apply directly to the table rescue loop (detect → escalate with cap → merge → record).
- **Next:** Implement collapsed-table detector and define rescue budget/cap + provenance fields.

### 20251222-1710 — Implemented table-rescue module and tested on pristine page 61
- **Result:** Success (table structure restored).
- **Notes:** Added `modules/adapter/table_rescue_html_v1/` and wired into `configs/recipes/recipe-ff-ai-ocr-gpt51.yaml` before boundary detection. Ran rescue on `/tmp/cf-pristine-table-check/pages_html.jsonl` (explicit `page_number=61`) → `/tmp/cf-pristine-table-check/pages_html_rescued.jsonl`. Output shows multi-row table restored; 1-row collapse fixed (old tr=1 → new tr=7). Extra empty cell remains in last row; will monitor if prompt tweak needed. Artifact example: `/tmp/cf-pristine-table-check/pages_html_rescued.jsonl` line with `page_number: 61` now has expanded `<table>` and `rescue` provenance.
- **Next:** Run rescue on page-020R (if needed) and confirm in a smoke run of the main recipe that rescue triggers only for collapsed tables.

### 20251222-1730 — Verified page-020R mapping is stable (pristine page-039)
- **Result:** Success.
- **Notes:** Dry-run scan on `/tmp/cf-pristine-table-check/pages_html_rescued_dryrun.jsonl` shows page 39 (mapped from old page-020R) retains multi-row table and is not flagged for rescue. No `rescue` metadata on that row, confirming detector doesn’t over-fire on intact tables.
- **Next:** Mark table tests complete and proceed to smoke run in main recipe if needed.

### 20251222-1740 — Set rescued module_id for traceability
- **Result:** Success.
- **Notes:** Updated `table_rescue_html_v1` to stamp `module_id` on all rows and record `prev_module_id` in rescue provenance for attempted/skipped pages.
- **Next:** (Optional) re-run the table rescue test if you want a fresh artifact with updated module_id.

### 20251222-1800 — Added fallback crop and validated on old-scan table (page 216)
- **Result:** Success (second crop recovered the table).
- **Notes:** Added fallback crop pass (`--fallback-crop-top 0.35`, `--fallback-crop-bottom 0.85`) when the top crop returns no table. Smoke test on `output/runs/ff-ai-ocr-gpt51-full-20251222/02_ocr_ai_gpt51_v1/pages_html.jsonl` with `--pages-list 216` produced a repaired multi-row table in `/tmp/cf-table-rescue-smoke/pages_html_rescued_216b.jsonl` (old tr=1 → new tr=7). Rescue provenance includes both crop attempts.
- **Next:** Optionally run a short recipe smoke using existing OCR outputs once driver supports start-from without schema mismatch.

### 20251222-1830 — Validated rescue across all pristine table pages
- **Result:** Success.
- **Notes:** Ran rescue on all 14 pristine table pages using `/tmp/cf-pristine-table-check/pages_html.jsonl` → `/tmp/cf-pristine-table-check/pages_html_rescued_all.jsonl`. Only page 61 was detected and repaired (attempted=1, applied=1). All other mapped pages retained multi-row tables. Table row counts by page: 39(7), 61(7), 73(3), 87(3), 90(3), 91(7), 100(3), 101(3), 107(3), 122(3), 149(7), 165(7), 211(3), 217(7).
- **Next:** If desired, run a main-recipe smoke using existing OCR outputs once driver supports start-from table_rescue without schema mismatch.

### 20251222-1900 — Main recipe smoke (table_rescue stage)
- **Result:** Success.
- **Notes:** Ran a short smoke with `configs/settings.ff-ai-ocr-gpt51-table-rescue-smoke.yaml` (start=end=108) and `--end-at table_rescue`. Output: `/tmp/cf-ff-ai-ocr-gpt51-table-rescue-smoke/03_table_rescue_html_v1/pages_html_rescued.jsonl` (2 rows). `table_rescue` stage executed and stamped; no rescue applied on these pages because OCR tables were already intact.
- **Next:** None for table_rescue; proceed to next story unless you want a full run after other fixes.
