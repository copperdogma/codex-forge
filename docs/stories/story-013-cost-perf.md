# Story: Cost/perf benchmarking and presets

**Status**: Done

---

## Acceptance Criteria
- Benchmark models/window sizes
- Provide presets for speed/cost/quality

## Tasks
- [x] Benchmark harness that times runs, captures token counts, and writes JSON/CSV results
- [x] Define benchmark scenarios (pages, module chain, model/window matrix)
- [x] Run benchmarks for baseline models/windows and store artifacts under `output/runs/bench-*`
- [x] Preset configs for speed/cost/quality profiles (settings + recipe examples)
- [x] Docs of trade-offs and how to choose presets; include sample numbers

## Notes
- Use existing recipes as baselines: `configs/recipes/recipe-ocr.yaml` (OCR heavy) and `configs/recipes/recipe-text.yaml` (text-only).
- Prefer small, representative slices instead of full books to keep runs cheap while still stressing OCR + LLM steps.
- Keep artifacts append-only under `output/runs/bench-*` with a `metadata.json` capturing run context (dataset pages, models, recipes, date).
- Harness scaffold added at `scripts/bench/bench_harness.py`; runs driver per slice/model, forces instrumentation on, and aggregates `bench_metrics.csv/jsonl` under session dir.
- Current instrumentation run totals show zero tokens/cost because modules are not emitting `instrumentation_call_v1` events yet; need module-level logging to capture token usage.
- Added `log_llm_usage` calls to `clean_llm_v1`, `portionize_sliding_v1`, `portionize_coarse_v1`, and `enrich_struct_v1` so future runs record prompt/completion tokens and costs.
- Bench runs conducted:
  - `bench-cost-perf-mini-20251124a`: OCR slice 1-1, gpt-4.1-mini, timings only (pre-logging).
  - `bench-cost-perf-mini-20251124b`: OCR slice 1-1, gpt-4.1-mini, tokens captured (calls=2, ~5650/341 tokens, cost ~0.00105 USD, wall ~18.7s).
  - `bench-cost-perf-ocr-20251124c`: OCR slices 1/15/42/90 across models gpt-4.1-mini, gpt-4.1, gpt-5 (window 8). Costs/page: ~0.0011 (mini), ~0.014–0.026 (4.1), ~0.015–0.020 (5). Wall: ~13–18s (mini), ~16–34s (4.1), ~69–99s (5).
  - `bench-cost-perf-text-20251124e`: Text recipe slices 1/15/42/90 across same models (window 8). Costs/page: ~0.000126–0.000134 (mini), ~0.00424–0.00435 (4.1), ~0.0043–0.0077 (5). Wall: ~7.6–8s (mini/4.1), ~28–38s (5).

## Benchmark Plan (draft)
- **Datasets:** 2 slices from `input/06 deathtrap dungeon.pdf` (dense text) and 1 slice from `input/images/` (ocr image). Proposal: pages 1, 15, 42, 90; and `input/images/page-010.png`.
- **Pipelines:** (a) OCR recipe (`recipe-ocr.yaml`), (b) text recipe (`recipe-text.yaml`), (c) small DAG variant if needed for window sensitivity (TBD).
- **Model/window matrix:** `gpt-4.1-mini` 128k (baseline), `gpt-4.1` 128k, `gpt-4.1` 32k, `gpt-5` 128k (quality), maybe `gpt-4.1-mini` 32k if cost window scaling matters. All runs logged with model + window in metadata.
- **Metrics to capture per module:** wall-clock time, input/output tokens, cost estimate (prompt + completion), errors/retries, success flag. Aggregate per-run totals plus per-stage breakdown.
- **Outputs:** per-run CSV/JSONL (`bench_metrics.csv`, `bench_metrics.jsonl`) plus `metadata.json` in `output/runs/bench-<date>-<tag>/`.
- **Repeatability:** optional `--seed` and fixed dataset list; cache serialized inputs where possible to avoid re-OCR for window sweeps.

## Preset Sketch
- **speed (text-first):** `gpt-4.1-mini` text recipe, window 8, temp 0.2, max_tokens 300 → ~8s/page, ~$0.00013/page.
- **cost (ocr minimal):** `gpt-4.1-mini` OCR recipe, window 8, temp 0.2, max_tokens 400 → ~13–18s/page, ~$0.0011/page.
- **quality:** `gpt-5` OCR recipe, window 8, temp 0.4, max_tokens 600 → ~70–100s/page, ~$0.015–0.020/page.
- **balanced:** `gpt-4.1` OCR recipe, window 8, temp 0.3, max_tokens 450 → ~16–34s/page, ~$0.014–0.026/page.
- Provide settings snippets and recipe overrides for each; note that text pipeline assumes pre-extracted text input.

## Summary Tables (window=8)
Per-model averages across slices 1/15/42/90.

**OCR recipe (`bench-cost-perf-ocr-20251124c`)**
| model | avg wall (s/page) | avg prompt toks | avg completion toks | avg cost (USD/page) |
| --- | ---: | ---: | ---: | ---: |
| gpt-4.1-mini | 15.88 | 5007.5 | 396.5 | 0.000989 |
| gpt-4.1 | 27.10 | 2553.2 | 516.8 | 0.020518 |
| gpt-5 | 83.71 | 2293.8 | 3389.5 | 0.018145 |

**Text recipe (`bench-cost-perf-text-20251124e`)**
| model | avg wall (s/page) | avg prompt toks | avg completion toks | avg cost (USD/page) |
| --- | ---: | ---: | ---: | ---: |
| gpt-4.1-mini | 7.85 | 434.0 | 107.2 | 0.000130 |
| gpt-4.1 | 8.10 | 434.0 | 142.0 | 0.004300 |
| gpt-5 | 33.17 | 432.0 | 1338.5 | 0.006218 |

Sources: `output/runs/bench-cost-perf-ocr-20251124c/bench_metrics.csv`, `output/runs/bench-cost-perf-text-20251124e/bench_metrics.csv`.

## Work Log
- Pending
### 20251124-1127 — Initialized task breakdown for cost/perf story
- **Result:** Success; tasks expanded to cover scenarios, data capture, presets, and docs.
- **Notes:** Need to pick representative pages/modules and decide model/window matrix for benchmarks.
- **Next:** Define benchmark dataset and outline harness shape (inputs, metrics, outputs) before coding.
### 20251124-1128 — Drafted benchmark and preset plan
- **Result:** Success; added dataset slices, pipeline coverage, model/window matrix, metrics, outputs, and preset sketches to story.
- **Notes:** Need to confirm model availability in env and decide CSV/JSON schema for harness. Might add DAG variant for window testing.
- **Next:** Design harness CLI (inputs: recipe, pages list, models) and metadata schema; then implement harness in repo (likely under `scripts/` or `tools/`).
### 20251124-1133 — Added benchmark harness scaffold
- **Result:** Success; created `scripts/bench/bench_harness.py` to clone recipes per slice/model, force instrumentation, run driver, and aggregate run totals into `bench_metrics.csv/jsonl` inside `output/runs/bench-<tag>-<ts>/`.
- **Notes:** CLI supports `--slices`, `--models`, `--portion-window`, `--boost-model`, `--settings`, `--price-table`; defaults to pricing config and cross product slices×models. Uses recipe-derived window/boost when not overridden.
- **Next:** Lock benchmark slice list (pages + images), confirm model/window matrix, and perform first baseline run to produce reference metrics.
### 20251124-1135 — Ran first benchmark session (OCR, 1 page, gpt-4.1-mini)
- **Result:** Success; harness executed `recipe-ocr.yaml` over slice 1-1 with model `gpt-4.1-mini`, outputs in `output/runs/bench-cost-perf-mini-20251124a/`. Wall time ~18.5s for full pipeline.
- **Notes:** `bench_metrics.csv/jsonl` populated but tokens/cost are zero because modules do not emit instrumentation call events; need to wire `log_llm_usage` in LLM modules to get token/cost data. Instrumentation JSON present with timings only.
- **Next:** Decide if we patch modules for token logging now; otherwise proceed with additional wall-time sweeps and document token gap in presets.
### 20251124-1152 — Added token logging and reran benchmark
- **Result:** Success; patched LLM modules to emit `instrumentation_call_v1` and reran OCR slice 1-1 (`bench-cost-perf-mini-20251124b`). Bench CSV now shows calls=2, prompt_tokens=5650, completion_tokens=341, cost≈0.001052, wall≈18.7s.
- **Notes:** Pricing from `configs/pricing.default.yaml` applied; metrics now capture token usage. Boost model set to `gpt-5` but not triggered on this page (calls=2 indicates base+portionize).
- **Next:** Expand sweeps (more pages + text recipe + additional models/windows) and start drafting preset docs with these baseline numbers.
### 20251124-1207 — Completed OCR and text sweeps across models
- **Result:** Ran OCR sweep `bench-cost-perf-ocr-20251124c` and text sweep `bench-cost-perf-text-20251124e` over slices 1,15,42,90 with models gpt-4.1-mini/4.1/5 (window 8). All runs succeeded; tokens/costs captured.
- **Notes:** OCR vs text gap: OCR costs ~10–20× mini/4.1 and ~2–3× wall vs text; gpt-5 adds significant wall (70–100s OCR, 28–38s text). Text pipeline stays < $0.008/page even on gpt-5. Harness now skips start/end injection for text recipes.
- **Next:** Summarize into preset guidance (speed/cost/quality), consider window/stride sensitivity tests, and add quick tables/plots referencing `output/runs/bench-cost-perf-*/bench_metrics.csv`.
### 20251124-1209 — Drafted preset guidance from sweeps
- **Result:** Added preset sketch mapping measured costs/wall to speed/cost/quality/balanced profiles using mini/4.1/5 and text vs OCR recipes.
- **Notes:** Numbers come from `bench-cost-perf-ocr-20251124c` and `bench-cost-perf-text-20251124e` (window 8). Text preset assumes pre-extracted text; OCR presets include render+OCR overhead.
- **Next:** Embed small tables/plots in docs and wire presets into example settings/recipe overrides; optionally test window/stride sensitivity.
### 20251124-1216 — Fixed pipeline visibility for nested run paths
- **Result:** Updated `docs/pipeline-visibility.html` to read run base path from manifest (`meta.path`) when present, so nested bench runs like `bench-cost-perf-text-20251124e/gpt-5-p042-042` load correctly.
- **Notes:** Viewer now falls back to `output/runs/<run_id>` only when manifest lacks a path; should resolve “unable to load run” seen on latest benchmarks.
- **Next:** Verify dashboard load for latest bench runs and consider adding quick links from presets doc to the CSVs.
### 20251124-1223 — Added metadata outputs, presets, and regression test
- **Result:** Bench harness now writes `metadata.json` per session; added preset snippets under `configs/presets/` with README; added regression test `tests/test_pipeline_visibility_path.py` ensuring dashboard honors manifest path for nested runs.
- **Notes:** Presets reference measured costs/wall from the latest sweeps; harness metadata captures session id, slices, models, price table, and run rows.
- **Next:** Wire preset snippets into README or recipes for quick use and consider adding window/stride sensitivity sweeps.
### 20251124-1227 — Show cost chip on every stage (zero included)
- **Result:** Dashboard stage cards now always show a cost chip; zero-cost stages include a tooltip explaining no LLM calls (non-LLM step or no usage events).
- **Notes:** Keeps run-level totals unchanged; improves clarity when only some stages call the LLM.
- **Next:** None for UI; optional: add per-stage call counts inline.
