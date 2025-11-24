# codex-forge
AI-first, modular pipeline for turning scanned books into structured JSON with full traceability.

## What it does (today)
- Ingest PDF or page images
- OCR → per-page raw text
- Multimodal LLM cleaning → per-page clean text + confidence
- Sliding-window portionization (LLM, optional priors, multimodal)
- Consensus/dedupe/normalize, resolve overlaps, guarantee coverage
- Assemble per-portion JSON (page spans, source images, raw_text)
- Run outputs stored under `output/runs/<run_id>/` with manifests and state

## Repository layout
- CLI modules/scripts: `pages_dump.py`, `clean_pages.py`, `portionize.py`, `consensus.py`, `dedupe_portions.py`, `normalize_portions.py`, `resolve_overlaps.py`, `build_portion_text.py`, etc.
- `docs/requirements.md`: system requirements
- `snapshot.md`: current status and pipeline notes
- `output/`: git-ignored; run artifacts live at `output/runs/<run_id>/`
- `settings.example.yaml`: sample config
- Shared helpers for module entrypoints live in `modules/common/` (utils, OCR helpers).

## Modular driver (current)
- Modules live under `modules/<stage>/<module_id>/`; recipes live in `configs/recipes/`.
- Driver orchestrates stages, stamps artifacts with schema/module/run IDs, and tracks state in `pipeline_state.json`.
- Swap modules by changing the recipe, e.g. OCR vs text ingest.

Examples:
```bash
# Dry-run OCR recipe
python driver.py --recipe configs/recipes/recipe-ocr.yaml --dry-run

# Text ingest with mock LLM stages (for tests without API calls)
python driver.py --recipe configs/recipes/recipe-text.yaml --mock --skip-done

# OCR pages 1–20 real run
python driver.py --recipe configs/recipes/recipe-ocr-1-20.yaml --force

# Swap modules: edit configs/recipes/*.yaml to choose a different module per stage
# (e.g., set stage: extract -> module: extract_text_v1 instead of extract_ocr_v1)
```

### DAG recipes (coarse+fine merge example)
```bash
# Dry-run DAG OCR with adapter merge
python driver.py --recipe configs/recipes/recipe-ocr-dag.yaml --dry-run

# Text ingest DAG with mock LLM stages (fast, no API calls)
python driver.py --recipe configs/recipes/recipe-text-dag.yaml --mock --skip-done

# Quick smoke: coarse+fine+continuation on first 10 pages (manual)
python driver.py --recipe configs/recipes/recipe-ocr-coarse-fine-smoke.yaml --force

# Continuation regression check (after a run)
python scripts/regression/check_continuation_propagation.py \
  --hypotheses output/runs/deathtrap-ocr-dag/adapter_out.jsonl \
  --locked output/runs/deathtrap-ocr-dag/portions_locked_merged.jsonl \
  --resolved output/runs/deathtrap-ocr-dag/portions_resolved.jsonl
```
Key points:
- Stages have ids and `needs`; driver topo-sorts and validates schemas.
- Adapter `merge_portion_hyp_v1` dedupes coarse+fine portion hypotheses before consensus.
- Override per-stage outputs via either a stage-level `out:` key (highest precedence) or the recipe-level `outputs:` map.

### Parameter validation & output overrides
- Each module can declare `param_schema` (JSON-Schema-lite) in its `module.yaml` to type-check params before the run. Supported fields per param: `type` (`string|number|integer|boolean`), `enum`, `minimum`/`maximum`, `pattern`, `default`; mark required via a top-level `required` list or `required: true` on the property.
- Driver merges `default_params` + recipe `params`, applies schema defaults, and fails fast on missing/unknown/invalid params with a message that includes the stage id and module id.
- Example: `Param 'min_conf' on stage 'clean_pages' (module clean_llm_v1) expected type number, got str`.
- Set custom filenames per stage with `out:` inside the stage config; this overrides recipe `outputs:` and the built-in defaults, and the resolved name is used for resume/skip-done and downstream inputs.
- Example snippet with stage-level `out`:
  ```yaml
  stages:
    - id: clean_pages
      stage: clean
      module: clean_llm_v1
      needs: [extract_text]
      out: pages_clean_custom.jsonl
  ```

Artifacts appear under `output/runs/<run_id>/` as listed in the recipe; use `--skip-done` to resume and `--force` to rerun stages.

## Output conventions
- `output/runs/<run_id>/` contains all artifacts: images/, ocr/, pages_raw/clean, hypotheses, locked/normalized/resolved portions, final JSON, `pipeline_state.json`.
- `output/run_manifest.jsonl` lists runs (id, path, date, notes).

## Instrumentation (timing & cost)
- Enable per-stage timing and LLM cost reporting with `--instrument` (off by default).
- Optional price sheet override via `--price-table configs/pricing.default.yaml` or recipe `instrumentation.price_table`.
- Outputs land beside artifacts: `instrumentation.json` (machine-readable), `instrumentation.md` (summary tables), and raw `instrumentation_calls.jsonl` when present. Manifest entries link to the reports.
- Modules can emit call-level usage via `modules.common.utils.log_llm_usage(...)`; the driver aggregates tokens/costs per stage and per model.

## Pipeline visibility dashboard
- Serve from repo root: `python -m http.server 8000` then open `http://localhost:8000/docs/pipeline-visibility.html`.
- The page polls `output/run_manifest.jsonl` for run ids, then reads `output/runs/<run_id>/pipeline_state.json` and `pipeline_events.jsonl` for live progress, artifacts, and confidence stats.
- A ready-to-use fixture run lives at `output/runs/dashboard-fixture` (listed in the manifest) so you can smoke the dashboard without running the pipeline.

## Roadmap (high level)
- Enrichment (choices, cross-refs, combat/items/endings)
- Turn-to validator (CYOA), layout-preserving extractor, image cropper/mapper
- Coarse+fine portionizer; continuation merge
- AI planner to pick modules/configs based on user goals

## Dev notes
- Requires Tesseract installed/on PATH.
- Models configurable; defaults use `gpt-4.1-mini` with `--boost_model gpt-5`.
- Artifacts are JSON/JSONL; runs are append-only and reproducible via configs.
- Driver unit tests run in CI via `tests.yml`. Run locally with:
  ```bash
  python -m unittest discover -s tests -p "driver_*test.py"
  ```
