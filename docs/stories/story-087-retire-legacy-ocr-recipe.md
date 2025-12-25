# Story: Retire Legacy OCR-Only Recipe

**Status**: Done  
**Created**: 2025-12-22  
**Priority**: Medium  
**Parent Story**: story-081 (GPT‑5.1 AI‑First OCR Pipeline)

---

## Goal

Remove or deprecate legacy OCR‑ensemble recipes now superseded by the GPT‑5.1 HTML‑first pipeline.

---

## Motivation

The old OCR‑ensemble recipes are slower, less accurate, and no longer needed for active development. Keeping them as defaults risks accidental use and confusion.

---

## Success Criteria

- [x] Legacy OCR‑only recipe(s) identified and documented as deprecated.
- [x] New GPT‑5.1 pipeline is the default/recommended path in docs.
- [x] Legacy recipes removed or clearly marked obsolete in `docs/stories.md`, README/AGENTS as needed.
- [x] No pipeline depends on legacy recipes (or explicitly opts in for archival use).
- [x] Optional: legacy recipes archived under `configs/recipes/legacy/` if we want to keep them for reference.

---

## Tasks

- [x] Inventory legacy OCR recipes and where they’re referenced.
- [x] List legacy OCR recipe files (e.g., `recipe-ff-canonical.yaml`, `recipe-ocr.yaml`, `recipe-ocr-ensemble-gpt4v.yaml`, `recipe-ocr-enrich-sections-*.yaml`) and decide which to archive vs remove.
- [x] Decide keep‑as‑archive vs remove; update docs accordingly.
- [x] Update README/AGENTS to remove or clearly deprecate `recipe-ff-canonical.yaml` references and point to `recipe-ff-ai-ocr-gpt51.yaml`.
- [x] Update recommended order and references to use GPT‑5.1 pipeline.
- [x] Validate no active workflow depends on legacy recipes.
- [x] If archiving, move legacy recipes under `configs/recipes/legacy/` and add deprecation header comments.
- [x] Log decisions and any file moves in work log.

---

## Work Log

### 20251222-2355 — Story created
- **Result:** Success.
- **Notes:** Added to track deprecating/removing legacy OCR‑only recipes in favor of GPT‑5.1 HTML‑first pipeline.
- **Next:** Inventory legacy recipes and doc references.

### 20251225-1304 — Inventory legacy recipe references
- **Result:** Success (partial; inventory compiled).
- **Notes:** Found legacy OCR recipes under `configs/recipes/`: `recipe-ff-canonical.yaml`, `recipe-ocr.yaml`, `recipe-ocr-ensemble-gpt4v.yaml`, `recipe-ocr-coarse-fine-smoke.yaml`, `recipe-ocr-enrich-sections-*.yaml`, plus deprecated FF variants (`recipe-ff-ai-pipeline.yaml`, `recipe-ff-unstructured*.yaml`, `recipe-ff-engine.yaml`, `recipe-ff-redesign-v2*.yaml`). Docs references remain in `README.md` (multiple `recipe-ff-canonical.yaml` examples) and `AGENTS.md` (explicitly marked deprecated but still referenced for smoke settings).
- **Next:** Decide archive vs remove list; update README/AGENTS to point exclusively to `recipe-ff-ai-ocr-gpt51.yaml` and move any kept legacy recipes under `configs/recipes/legacy/`.

### 20251225-1308 — Archived legacy OCR recipes and updated docs
- **Result:** Success.
- **Notes:** Moved legacy OCR recipes to `configs/recipes/legacy/` and prepended deprecation headers. Updated `README.md` examples and references to use `recipe-ff-ai-ocr-gpt51.yaml`, and rewired legacy OCR commands to `configs/recipes/legacy/recipe-ocr.yaml`. Updated `AGENTS.md` smoke guidance to `configs/settings.ff-ai-ocr-gpt51-smoke-20.yaml` and clarified legacy recipe paths.
- **Next:** Validate no active workflow or scripts still depend on the legacy recipe paths.

### 20251225-1326 — Validated active workflows against legacy recipe paths
- **Result:** Success.
- **Notes:** Updated active scripts/tests/code to point to archived paths where legacy OCR is intentionally used: `scripts/smoke_easyocr_gpu.sh`, `scripts/run_driver_monitored.sh` example, `modules/intake/zoom_refine_v1/main.py`, `modules/intake/tests/test_intake_chain_e2e.py`, `configs/presets/README.md`, and `tests/test_ff_20_page_regression.py`. Remaining references to `recipe-ff-canonical.yaml` are confined to historical docs/stories and deprecation comments.
- **Next:** Optionally update deprecated recipe header comments (unstructured/engine/redesign) to reference GPT-5.1 canonical for clarity.

### 20251225-1328 — Updated deprecated recipe headers
- **Result:** Success.
- **Notes:** Repointed deprecation headers in `configs/recipes/recipe-ff-ai-pipeline.yaml`, `configs/recipes/recipe-ff-redesign-v2*.yaml`, `configs/recipes/recipe-ff-unstructured*.yaml`, and `configs/recipes/recipe-ff-engine.yaml` to reference the GPT-5.1 canonical recipe.
- **Next:** If desired, update historical docs/stories that mention `recipe-ff-canonical.yaml` for clarity (optional; historical record).

### 20251225-1332 — Smoke test run (GPT-5.1 canonical)
- **Result:** Failure.
- **Notes:** Ran `python driver.py --recipe configs/recipes/recipe-ff-ai-ocr-gpt51.yaml --settings configs/settings.ff-ai-ocr-gpt51-smoke-20.yaml --run-id ff-ai-ocr-gpt51-smoke-20 --output-dir /tmp/cf-ff-ai-ocr-gpt51-smoke-20 --force`. Driver failed immediately with `Stage validate_gamebook needs unknown stage 'load_boundaries'`.
- **Next:** Inspect recipe DAG (`configs/recipes/recipe-ff-ai-ocr-gpt51.yaml`) for a stale `needs: [load_boundaries]` reference and fix stage wiring.

### 20251225-1339 — Clarified smoke test definitions in docs
- **Result:** Success.
- **Notes:** Added “Smoke Tests (Quick Reference)” to `README.md` and `AGENTS.md` to distinguish canonical GPT‑5.1 smoke, offline fixture smoke, and legacy/archived smoke configs.
- **Next:** Re-run the GPT‑5.1 smoke after fixing the `load_boundaries` dependency in the recipe DAG.

### 20251225-1347 — Fixed GPT-5.1 smoke settings params
- **Result:** Success.
- **Notes:** Smoke run failed because `split_pages_from_manifest_v1` doesn't accept `dpi/start/end`. Moved params to `extract_pdf_images_capped` and set `dpi_cap: 300`, `start: 1`, `end: 20` in `configs/settings.ff-ai-ocr-gpt51-smoke-20.yaml`.
- **Next:** Re-run the GPT‑5.1 smoke test.

### 20251225-1352 — Allow stubs for GPT-5.1 smoke
- **Result:** Success.
- **Notes:** Build failed on missing sections for 20pp smoke; set `stage_params.build_gamebook.allow_stubs: true` in `configs/settings.ff-ai-ocr-gpt51-smoke-20.yaml`.
- **Next:** Re-run the GPT‑5.1 smoke test end-to-end.

### 20251225-1358 — GPT-5.1 canonical smoke run (20pp)
- **Result:** Success (completed with expected missing-section errors for smoke).
- **Notes:** Ran `python driver.py --recipe configs/recipes/recipe-ff-ai-ocr-gpt51.yaml --settings configs/settings.ff-ai-ocr-gpt51-smoke-20.yaml --run-id ff-ai-ocr-gpt51-smoke-20 --output-dir /tmp/cf-ff-ai-ocr-gpt51-smoke-20 --force`. Pipeline completed; build produced 42 sections with 24 stubs; validation report flags missing sections (expected for 20pp smoke). Spot-checked `gamebook.json` sections 1–5 for presence of html/nav.
- **Next:** If desired, create a smoke-specific validation config (expected range) to reduce noise in validation_report.json.

### 20251225-1401 — Marked story Done
- **Result:** Success.
- **Notes:** Checked all success criteria and set story status to Done; updated `docs/stories.md` status for Story 087.
- **Next:** None.
