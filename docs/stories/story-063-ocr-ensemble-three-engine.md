# Story: OCR Ensemble Three-Engine Voting

**Status**: Done
**Created**: 2025-12-10
**Parent Story**: story-061 (OCR Ensemble Fusion - DONE)
**Depends On**: story-065 (EasyOCR Reliability)  _(formerly referenced as story-055)_

## Goal

Complete the OCR ensemble fusion improvements by enabling EasyOCR as a third engine and implementing three-engine voting. This story contains work deferred from story-061 that requires story-055 to be completed first.

## Background

Story-061 implemented significant improvements to OCR fusion:
- Removed document-level Apple OCR discard (R1)
- Character-level voting within lines (R2)
- Levenshtein distance outlier detection (R4)
- Confidence-weighted selection for Apple Vision (R5 partial)
- Inline GPT-4V escalation for critical failures (R6)
- Form page threshold improvements (Task 5.1)
- Two-column fragment filtering (Task 5.2)

However, EasyOCR integration was blocked by a numpy version conflict (numpy 2.x vs 1.x required by easyocr). This story completes the remaining work once story-055 resolves EasyOCR reliability issues.

## Requirements

### R1: Enable EasyOCR as Third Engine (from story-061 R3)

**Problem**: EasyOCR fails on full runs due to numpy version conflict and initialization issues.

**Prerequisites**: story-055 must resolve EasyOCR installation/reliability issues.

**Solution**: Once EasyOCR is stable, enable it in the OCR ensemble:

1. Force language to `en` for all pages
2. Add warmup step before page loop
3. Retry with `download_enabled=True` on error

**Acceptance Criteria**:
- [x] EasyOCR runs successfully on a canonical 20-page subset with Apple Vision enabled (3-engine run)
- [x] `engines_raw` includes `easyocr` text for ≥95% of emitted outputs on that subset (spread-aware)
- [x] Three-engine voting produces better results than two-engine

### R2: Implement Three-Engine Voting

**Problem**: Current fusion only handles Tesseract + Apple Vision. With EasyOCR enabled, need true 3-way voting.

**Solution**: Extend `align_and_vote()` and `fuse_characters()` to handle 3+ engines:

1. Use existing outlier detection to identify garbage engines
2. For character-level fusion, use majority voting across 3 engines
3. If 2 engines agree and 1 differs, use majority
4. If all 3 differ, use confidence weighting

**Acceptance Criteria**:
- [x] `align_and_vote()` handles 3+ engine inputs
- [x] `fuse_characters()` uses majority voting with 3 engines
- [x] Outlier detection excludes garbage engines before voting
- [x] Test coverage for 3-engine scenarios

### R3: Extract Tesseract Confidence (from story-061 R5)

**Problem**: Only Apple Vision confidence is used; Tesseract word-level confidence could improve fusion.

**Solution**: Extract confidence scores from Tesseract output:

1. Use `pytesseract.image_to_data()` with `output_type=Output.DICT`
2. Extract `conf` field for each word
3. Pass to fusion functions for weighted voting

**Acceptance Criteria**:
- [x] Tesseract confidence extracted via `image_to_data()`
- [x] Confidence passed to `align_and_vote()` for weighted voting (multi-engine `confidences_by_engine["tesseract"]`)
- [x] Both engine confidences used in character-level fusion

### R4: Test Inline Escalation on Real Data

**Problem**: Inline GPT-4V escalation was implemented but not tested on actual critical failure pages.

**Solution**: Run the OCR pipeline with `--inline-escalation` on pages known to have critical failures:

1. Identify pages with high corruption or disagreement from previous runs
2. Run with inline escalation enabled
3. Compare output quality before/after escalation
4. Document cost/quality tradeoffs

**Acceptance Criteria**:
- [x] Test run with `--inline-escalation` on 5+ critical failure pages
- [x] Quality comparison documented
- [x] Cost per escalation tracked
- [x] Recommendations for threshold tuning

## Tasks

### Phase 1: Enable EasyOCR (requires story-055)
- [x] Verify EasyOCR installs and runs after story-065 fixes.  
  _Done in Story 065/067 via smoke runs and SHM/GPU hardening; see `docs/stories/story-065-easyocr-reliability.md` work log._
- [x] Add warmup/retry logic to OCR module.  
  _Done in Story 065 in `extract_ocr_ensemble_v1` (warmup + retries + debug logging)._
- [x] Run 20-page subset with all three engines and inspect artifacts
- [x] (De-scoped 20251212) Test on full book (113 pages)
- [x] Record EasyOCR coverage stats (pages with non-empty text, %)
- [x] Update histogram to show EasyOCR contribution

### Phase 2: Three-Engine Voting
- [x] Extend `align_and_vote()` for 3+ engines
- [x] Implement majority voting in `fuse_characters()`
- [x] Ensure outlier detection can drop 1+ engines (3+ total) before voting
- [x] Add a deterministic tie-breaker when all 3 disagree (confidence → stable fallback)
- [x] Add tests for 3-engine scenarios
- [x] Run regression test comparing 2-engine vs 3-engine

### Phase 3: Tesseract Confidence
- [x] Extract confidence from Tesseract
- [x] Pass to fusion functions
- [x] Plumb confidence through `engines_raw` (or equivalent debug payload) for auditing
- [x] Test confidence-weighted 3-engine voting

### Phase 4: Inline Escalation Testing
- [x] Identify critical failure test pages
- [x] Run with `--inline-escalation`
- [x] Document results and recommendations
- [x] Save a small “before/after” artifact bundle (page ids + snippets) for review

## Related Stories

- story-055-easyocr-reliability.md - **PREREQUISITE** - Must be completed first
- story-061-ocr-ensemble-fusion.md - Parent story (DONE)
- story-057-ocr-quality-column-detection.md - Original OCR quality story

## Work Log

### 2025-12-10 — Story created
- **Context**: Created to track work deferred from story-061 due to EasyOCR numpy conflict
- **Deferred items**: R3 (EasyOCR), 3-engine voting, Tesseract confidence, inline escalation testing
- **Blocking**: Requires story-055 (EasyOCR reliability) to be completed first
### 20251212-1325 — Checklist sync with completed work
- **Result:** Success; checked off Phase 1 warmup/retry/install items already delivered in Story 065/067. 
- **Notes:** Full-book EasyOCR coverage and all true 3‑engine voting work remain open here.
- **Next:** Resume after Story 065 completes a full‑book coverage validation.
### 20251212-0745 — Expanded task checklist to map to acceptance criteria
- **Result:** Success; added explicit checklist items for coverage stats, multi-engine outlier handling, tie-breaking, and audit artifacts.
- **Notes:** Keeps work measurable (coverage %, regression comparison, deterministic behavior).
- **Next:** Start by locating `align_and_vote()` / `fuse_characters()` call sites and current engine data model, then implement 3-engine voting behind existing settings.
### 20251212-0806 — Implemented 3-engine voting + Tesseract confidences; validated via tests + artifacts
- **Result:** Partial success.
- **What changed (code):**
  - Added `modules/common/ocr.py` `run_ocr_with_word_data()` + export in `modules/common/__init__.py`.
  - Updated `modules/extract/extract_ocr_ensemble_v1/main.py`:
    - Derives `tesseract_confidences` (per OCR line) from `image_to_data()` and stores `tesseract_page_confidence`.
    - `align_and_vote()` now supports multi-engine inputs via `{engine: [lines]}` and does majority/confidence voting.
    - Single-column + multi-column paths now vote across available engines (tesseract/easyocr/apple), excluding outliers.
    - Gated `_mps_available()` (torch import) behind `"easyocr" in args.engines` to avoid aborts when EasyOCR is disabled.
- **Validation (unit tests):**
  - `pytest -q tests/test_ocr_quality_checks.py` → **PASS** (48 tests), including new 3-engine cases.
- **Validation (artifact inspection):**
  - Ran: `python -m modules.extract.extract_ocr_ensemble_v1.main --pdf testdata/tbotb-mini.pdf --outdir output/runs/story063-ocr-smoke-2pg-noeasy --start 1 --end 2 --engines tesseract apple --run-id story063-ocr-smoke-2pg-noeasy`
  - Inspected: `output/runs/story063-ocr-smoke-2pg-noeasy/ocr_ensemble/pages_raw.jsonl`
    - Pages 1–2 include `engines_raw.tesseract_confidences` with lengths matching `lines` (51, 48).
    - `engines_raw.tesseract_page_confidence` populated (~0.93–0.94).
    - Apple Vision failed on this host; see `output/runs/story063-ocr-smoke-2pg-noeasy/ocr_ensemble/apple_errors.jsonl` (`kern.hv_vmm_present` sysctl failure), so apple text did not participate in voting.
- **Notes / blockers:**
  - Enabling EasyOCR in this environment still aborts the process (SIGABRT) due to torch import; likely requires running under the repo’s documented `codex-arm-mps` environment from `story-065` guidance.
- **Next:** Re-run OCR on a small page set with `"easyocr"` enabled in a known-good env; then do full-book coverage (% pages with `engines_raw.easyocr` non-empty) and the 2-engine vs 3-engine regression comparison.
### 20251212-0845 — EasyOCR smoke run in `codex-arm-mps` + coverage stats emitted
- **Result:** Success (CPU; MPS unavailable on this host).
- **Run:** `python -m modules.extract.extract_ocr_ensemble_v1.main --pdf testdata/tbotb-mini.pdf --outdir /tmp/cf-story063-easyocr-smoke-3pg --start 1 --end 3 --engines tesseract easyocr --run-id story063-easyocr-smoke-3pg --write-engine-dumps`
- **Inspected artifacts:**
  - `/tmp/cf-story063-easyocr-smoke-3pg/ocr_ensemble/pages_raw.jsonl` → `engines_raw.easyocr` non-empty on 3/3 pages; `fusion_sources` shows mixed per-line winners (tesseract/easyocr/fused).
  - `/tmp/cf-story063-easyocr-smoke-3pg/ocr_ensemble/ocr_source_histogram.json` now includes `engine_coverage.easyocr_pages_with_text` + `%`.
- **Notes:** `scripts/check_arm_mps.py` fails (MPS not available), but EasyOCR runs on CPU without SIGABRT in this env. Also, all 3 pages flagged `needs_escalation=true` on this mini PDF; may be expected and should be revisited during full-book evaluation.
- **Next:** Run the full 113-page book with `--engines tesseract easyocr` (and `apple` only if the helper works on the target host), then record EasyOCR coverage ≥95% and do a 2-engine vs 3-engine regression comparison on a fixed page set.
### 20251212-0922 — 20-page Deathtrap Dungeon run with all three engines (verified artifacts)
- **Result:** Success.
- **Run:** `source ~/miniforge3/bin/activate codex-arm-mps && python -m modules.extract.extract_ocr_ensemble_v1.main --pdf "input/06 deathtrap dungeon.pdf" --outdir /tmp/cf-story063-3eng-20 --start 1 --end 20 --dpi 300 --lang en --engines tesseract easyocr apple --run-id story063-3eng-20 --write-engine-dumps`
- **Artifacts inspected:**
  - `/tmp/cf-story063-3eng-20/ocr_ensemble/pages_raw.jsonl` (40 outputs due to spread splitting; `spread_decision.json` set `is_spread=true`).
  - `/tmp/cf-story063-3eng-20/ocr_ensemble/ocr_source_histogram.json` and `/tmp/cf-story063-3eng-20/ocr_ensemble/easyocr_debug.jsonl`.
- **Coverage (outputs, not PDF pages):** `easyocr` non-empty on 40/40; `apple` non-empty on 30/40; `tesseract` non-empty on 34/40. `outlier_engines` flagged: apple 6, easyocr 2, tesseract 2 (output-count basis).
- **Notes:** Fixed `ocr_source_histogram.json` denominators to use emitted output count (spread-aware) and added `total_pdf_pages` alongside `total_pages`; verified with `/tmp/cf-story063-3eng-2/ocr_ensemble/ocr_source_histogram.json` (`total_pages=4`, `total_pdf_pages=2`).
- **Next:** If we still want a canonical “enough” regression: run a fixed page list both with and without `apple` and compare header recall / corruption/missing-content metrics; otherwise proceed to a full-book EasyOCR coverage run for the original ≥95% target.
### 20251212-0929 — Regression: 2-engine vs 3-engine comparison (subset)
- **Result:** Success; evidence recorded from actual artifacts.
- **Runs (Deathtrap Dungeon pages 1–20, spread-aware):**
  - 2-engine: `/tmp/cf-story063-2eng-20/ocr_ensemble/pages_raw.jsonl` (`--engines tesseract easyocr`)
  - 3-engine: `/tmp/cf-story063-3eng-20/ocr_ensemble/pages_raw.jsonl` (`--engines tesseract easyocr apple`)
- **Coverage (40 emitted outputs due to spread splitting):**
  - 2-engine non-empty: tesseract 33/40, easyocr 33/40
  - 3-engine non-empty: tesseract 34/40, easyocr 40/40, apple 30/40
- **Header recall proxy:** numeric-only line count increased **54 → 70** (2-engine → 3-engine).
- **Quality report averages (40 entries):**
  - Disagreement score avg **0.700 → 0.816** (expected to rise with a third engine).
  - Corruption score avg **0.1575 → 0.0000**; missing-content score avg **0.2025 → 0.0525** (large improvement signal).
  - Disagree-rate avg **0.229 → 0.188**.
- **Notes:** The `ocr_source_histogram.json` percentages in the earlier 3-engine run were generated before the spread-aware denominator fix; regression metrics above are computed directly from `pages_raw.jsonl` + `ocr_quality_report.json`.
- **Next:** Inline escalation testing remains open (Phase 4). Full-book 113-page coverage requirement removed per user request; leave as optional follow-up only.
### 20251212-0934 — Investigated low Apple coverage; fixed spread filtering + ROI clamp
- **Result:** Success; identified root causes and validated a targeted fix.
- **Root causes observed in `/tmp/cf-story063-3eng-20/ocr_ensemble/`:**
  - Apple was missing on 10/40 outputs: 5 due to `apple_excluded_as_outlier=true` (spread halves compared against full-page Apple text), and 4 due to Apple helper ROI errors (Vision Code=14) in `apple_errors.jsonl` (pages 17–18); 1 due to all engines flagged as outliers.
  - Apple OCR run failures were not reliably reflected in `engines_raw` (error lost), making diagnosis harder.
- **Fixes:**
  - `modules/extract/extract_ocr_ensemble_v1/main.py`: for spread books, filter Apple OCR lines by `bbox` center using `gutter_position` to produce L/R apple text that’s comparable to half-page OCR; also plumb `apple_error` into `engines_raw`.
  - `modules/extract/extract_ocr_ensemble_v1/apple_helper.swift`: clamp `regionOfInterest` to avoid float-rounding ROI boundary exceptions.
- **Validation:** reran pages 17–18 with 3 engines: `/tmp/cf-story063-3eng-17-18/ocr_ensemble/pages_raw.jsonl` shows Apple text present on 4/4 outputs and `apple_errors.jsonl` is empty.
### 20251212-0944 — Re-ran 20-page 3-engine subset; Apple coverage recovered
- **Result:** Success; Apple now contributes text on the vast majority of emitted outputs and is no longer being excluded as an outlier.
- **Run:** `/tmp/cf-story063-3eng-20-v2/ocr_ensemble/pages_raw.jsonl` (`--start 1 --end 20 --engines tesseract easyocr apple`)
- **Coverage (40 emitted outputs due to spread splitting):** apple 33/40 (82.5%), easyocr 40/40 (100%), tesseract 34/40 (85%).
- **Health checks:** `apple_excluded_as_outlier=0`, `apple_error_present=0`, and no `apple_errors.jsonl` produced. `ocr_source_histogram.json` shows spread-aware totals (`total_pages=40`, `total_pdf_pages=20`) and engine coverage (`apple_text_pct=0.825`).
### 20251212-1010 — Inline escalation test run (5+ targets) + cost/quality notes
- **Result:** Success, with one refusal handled safely.
- **Baseline (no inline):** `/tmp/cf-story063-3eng-20-v2/ocr_ensemble/pages_raw.jsonl`
- **Inline run:** `/tmp/cf-story063-inline-1-20-v2/ocr_ensemble/pages_raw.jsonl` using `--inline-escalation --inline-escalation-budget 6 --critical-corruption-threshold 0.25 --critical-disagree-threshold 0.4`
  - **Note:** Default critical thresholds (0.8/0.8) did not trigger on this 20-page subset; thresholds were lowered to exercise the inline path on high-disagree outputs.
- **Escalation outcomes (spread-aware output keys):**
  - **Replaced with `gpt4v_inline`**: `004L`, `005R`, `011L`, `011R`, `017L`, `018L` (6 outputs).
  - **Refusal (not replaced; recorded)**: `014L` (`engines_raw.inline_escalation_failed.error=\"refusal\"`), preserving original OCR output.
- **Cost tracking:** Added OpenAI `usage` capture to `engines_raw.inline_escalation{usage,model}` and wrote a before/after bundle with per-item estimated USD costs using `configs/pricing.default.yaml`:
  - Bundle: `/tmp/cf-story063-inline-before-after-v2.json` (includes token counts, estimated per-item cost, and before/after line snippets)
  - Estimated total (replaced + refusal attempt): **$0.0557** for 7 calls on this subset.
- **Quality notes (spot checks in bundle):**
  - `004L` publisher/address block: fixed several obvious OCR errors (“Penguie Boois…” → “Penguin Books…”).
  - `011L/011R` Adventure Sheet: cleaned headings and box labels vs garbled/fragmented OCR.
- **Recommendations:**
  - Keep refusal detection: never overwrite OCR with refusal text; treat as a failed escalation with provenance (`inline_escalation_failed`).
  - Consider adding a “text-likelihood” guard before calling vision (skip pages that are mostly illustration) to reduce wasted spend; also consider higher disagree thresholds in production to keep call volume low.

### 20251212-1033 — Marked Story 063 Done (docs + acceptance sync)
- **Result:** Success; story status set to Done and acceptance criteria checkboxes synced to recorded evidence and current implementation.
- **Notes:** Full-book 113-page run explicitly de-scoped by user (task marked complete-as-de-scoped). Full `pytest` suite is green (96 passed, 3 skipped).
- **Next:** None.
