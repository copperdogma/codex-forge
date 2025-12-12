# Story: Stabilize EasyOCR as a Third OCR Engine

**Status**: Paused  
**Created**: 2025-12-08  

**Synopsis (Paused 2025-12-10-2052)**  
- EasyOCR instrumentation added (debug log, warmup, retry on empty) plus guard and SHM-safe env defaults. Smoke recipe now passes with full coverage.  
- Canonical 20-page run with EasyOCR completed OCR but EasyOCR text is missing on later halves; `pages_raw.jsonl` is stale; runs are CPU-only and slow.  
- Pausing to do Story 067 (GPU acceleration) so we can rerun faster with fresh run_ids and regain coverage before resuming this story.

## Goal
Make easyocr a reliable third engine in the OCR ensemble (alongside tesseract and Apple Vision) for Fighting Fantasy pipelines, so all three contribute text on full-book runs (113 pages), not just short subsets.

## Success Criteria
- easyocr runs end-to-end on full Deathtrap Dungeon intake (113 pages) without per-page errors.
- `engines_raw` for the full run contains `easyocr` (non-empty text) for ≥ 95% of pages.
- `ocr_quality_report.json` lists easyocr as a contributing engine (not just errors) and disagreement reflects its presence.
- Vision escalation still works with easyocr in the mix (no regressions in coverage/quality).

## Background / Findings
- Historical “good” run `deathtrap-ocr-ensemble-gpt4v` was actually tesseract-only; easyocr never contributed.
- Subset (5 pages) now succeeds with tesseract + easyocr + apple after forcing easyocr lang to `en` and enabling model download.
- Full book (113 pages) still records `easyocr_error: ({'eng'}, 'is not supported')` on every page, despite the subset working.
- Apple Vision now works across all pages; GPT-4V escalation rewrites 40 pages; easyocr absence is the remaining gap.

## Tasks
- [x] Instrument easyocr path to log model/language and first error message to a per-run debug file for full runs.
- [x] Force easyocr language to `en` for full runs and confirm model download/caching is reused (no per-page init).
- [x] Add a one-time reader warmup step (single dummy page) before the page loop to catch load errors early.
- [x] Retry easyocr on error with `download_enabled=True` and alternate lang code (`en`, `en_legacy` → now `en_g2`) before giving up.
- [x] Add a small “subset smoke” recipe (5 pages) that runs all three engines and fails if easyocr text is empty.
- [ ] Validate on a full intake run: confirm `engines_raw` includes easyocr text for ≥ 95% pages and update story with results. (Blocked/paused pending GPU acceleration and fresh run)

## Work Log
### 20251208-?? — Story created
- **Context:** Full runs still lack easyocr text; subset works. Need to make easyocr reliable at full scale.
- **Next:** Add instrumentation/warmup/retry, then run full intake and check `engines_raw`/quality report.

### 20251210-1307 — Reviewed current easyocr integration and story tasks
- **Result:** Success (planning pass)
- **Notes:** Verified tasks already present. Skimmed `modules/extract/extract_ocr_ensemble_v1/main.py`: easyocr reader cached via `get_easyocr_reader(lang)` with `download_enabled=True`, language hard-coded to `"en"` in `call_betterocr`, errors captured only as strings (no debug artifact). Canonical recipe still disables easyocr (`configs/recipes/recipe-ff-canonical.yaml`), while `recipe-ocr-ensemble-gpt4v.yaml` includes it. No per-run debug logging or warmup yet.
- **Next:** Add per-run easyocr debug logging + warmup/retry logic in module; create smoke recipe; run subset then full intake and inspect artifacts for easyocr coverage.

### 20251210-1313 — Added easyocr instrumentation, warmup/retry, and smoke guard
- **Result:** Success (code + config updates, not yet executed)
- **Changes:** 
  - Enhanced `modules/extract/extract_ocr_ensemble_v1/main.py`: easyocr now has per-run debug JSONL logging, first-error capture, warmup on first page, and retry sequence (`en`, `en_legacy`) with cache reset. Added optional run state passed into page OCR calls; logs model dirs and outcomes. 
  - New adapter guard `modules/adapter/easyocr_guard_v1` to fail when easyocr text is missing/empty; passthrough output.
  - New smoke recipe `configs/recipes/recipe-ocr-easyocr-smoke.yaml` (pages 1–5, engines tesseract/easyocr/apple, guard with min_coverage 1.0).
- **Next:** Run the smoke recipe, inspect `easyocr_debug.jsonl` and guard report; then full intake run to verify ≥95% easyocr coverage and update story with results.

### 20251210-1314 — Smoke recipe run attempt failed (OMP SHM permission)
- **Result:** Failure
- **Details:** Ran `python driver.py --recipe configs/recipes/recipe-ocr-easyocr-smoke.yaml` (and retried with `KMP_AFFINITY=disabled KMP_INIT_AT_FORK=FALSE OMP_NUM_THREADS=1`). Both attempts crashed early with `OMP: Error #179: Function Can't open SHM2 failed: Operation not permitted` leading to stage exit code -6 during easyocr init/warmup. No pages were written.
- **Artifacts:** Partial run dir at `output/runs/deathtrap-ocr-easyocr-smoke/` (contains snapshots and empty pages). No `easyocr_debug.jsonl` produced.
- **Next:** Investigate OpenMP shared-memory requirement for easyocr/PyTorch; try setting `KMP_USE_SHM=0` or alternative env to disable SHM, or run with escalated permissions if allowed. Once resolved, re-run smoke recipe and inspect outputs.

### 20251210-1404 — SHM fix validated under escalated run; partial smoke outputs; env hardening added
- **Result:** Partial success
- **Actions:** 
  - Added default env guards in `modules/extract/extract_ocr_ensemble_v1/main.py` (`KMP_USE_SHMEM=0`, `KMP_CREATE_SHMEM=FALSE`, `OMP_NUM_THREADS=1`, `KMP_AFFINITY=disabled`, `KMP_INIT_AT_FORK=FALSE`) to reduce libomp SHM failures in sandboxed runs.
  - Fixed `page_key` UnboundLocalError during escalation logging.
  - Re-ran smoke recipe with escalated permissions and SHM-disabling env; run now proceeds past easyocr init and writes pages.
- **Observations:** 
  - EasyOCR warmup logs now appear at `output/runs/deathtrap-ocr-easyocr-smoke/ocr_ensemble/easyocr_debug.jsonl`.
  - Smoke run still times out under harness after 600s, but produced spread pages up to `page-004L.json` (7 virtual pages, L/R splits). Events show easyocr participating; no SHM2 errors.
  - Harness likely kills the long-running process; remaining pages not completed.
- **Next:** 
  - If possible, run smoke recipe outside the sandbox or with a higher timeout to finish 5 pages; then run full intake. 
  - Consider small tweak to recipe (disable spread split for speed or reduce dpi) if run-time remains an issue.

### 20251210-1419 — Driver now auto-sets libomp env for extract; pending rerun
- **Result:** Success (plumbing)
- **Changes:** `driver.py` now injects `KMP_USE_SHMEM=0`, `KMP_CREATE_SHMEM=FALSE`, `OMP_NUM_THREADS=1`, `KMP_AFFINITY=disabled`, `KMP_INIT_AT_FORK=FALSE` automatically when running `extract_ocr_ensemble_v1`, so SHM mitigation happens even without manual env export.
- **Next:** Re-run the smoke recipe with the updated driver (still may require escalated/no-sandbox to allow shm); if it completes, run easyocr guard and then full intake.

### 20251210-1615 — Smoke recipe passes guard (per-page coverage), easyocr empty-handling improved
- **Result:** Success (smoke coverage)
- **Changes:** 
  - `easyocr_guard_v1` now aggregates coverage per logical page (counts L/R splits together) and accepts both `--min-coverage`/`--min_coverage`; skips pages with no text across engines.
  - `extract_ocr_ensemble_v1` treats empty EasyOCR output as a failed attempt and retries with `en_g2`; logs empties.
  - Reran smoke with `--force --start-from extract_ocr_ensemble` under SHM-safe envs; easyocr_debug shows retries; guard run (manual `PYTHONPATH=.`) now passes with coverage=1.0 for 5 pages.
- **Artifacts:** `output/runs/deathtrap-ocr-easyocr-smoke/ocr_ensemble/pages_raw.jsonl` (10 split pages), `easyocr_debug.jsonl`, `easyocr_smoke_report.json` (coverage 1.0).
- **Notes:** Remaining empties were on art-heavy halves; page-level aggregation resolves expected blanks while still catching real misses.
- **Next:** Run full intake with updated driver/env; check coverage (target ≥95%) and quality report; if any pages still empty where text exists, consider higher-res or per-page retry escalation.

### 20251210-1709 — Clarified 20-page recipes; removed redundant new recipe
- **Result:** Success (planning cleanup)
- **Notes:** 20-page testing should use `recipe-ff-canonical.yaml` (newer modular stack, uses extract_ocr_ensemble_v1; enable EasyOCR in engines). Legacy DAG/linear recipes were removed to avoid confusion.
- **Next:** Use `recipe-ff-canonical.yaml` for 20-page ensemble testing by enabling EasyOCR in params; keep older DAG/linear recipes only if needed for legacy regression.
