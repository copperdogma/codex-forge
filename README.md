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

## Quick start (legacy linear)
```bash
cd codex-forge
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 1) OCR + images from a PDF
python pages_dump.py --pdf /path/book.pdf --outdir output/runs/<run_id>

# 2) Clean pages
python clean_pages.py --pages output/runs/<run_id>/pages_raw.jsonl \
  --out output/runs/<run_id>/pages_clean.jsonl \
  --model gpt-4.1-mini --boost_model gpt-5 --min_conf 0.6

# 3) Portionize (append hypotheses)
python portionize.py --pages output/runs/<run_id>/pages_clean.jsonl \
  --out output/runs/<run_id>/window_hypotheses.jsonl \
  --window 8 --stride 1 --range_start 1 --range_end <last_page> \
  --model gpt-4.1-mini --boost_model gpt-5

# 4) Consensus + resolve
python consensus.py --hypotheses output/runs/<run_id>/window_hypotheses.jsonl \
  --out output/runs/<run_id>/portions_locked.jsonl --min_conf 0.55 --range_start 1 --range_end <last_page>
python dedupe_portions.py --input output/runs/<run_id>/portions_locked.jsonl \
  --out output/runs/<run_id>/portions_locked_dedup.jsonl
python normalize_portions.py --input output/runs/<run_id>/portions_locked_dedup.jsonl \
  --out output/runs/<run_id>/portions_locked_normalized.jsonl
python resolve_overlaps.py --input output/runs/<run_id>/portions_locked_normalized.jsonl \
  --out output/runs/<run_id>/portions_resolved.jsonl --range_start 1 --range_end <last_page>

# 5) Assemble final portions
python build_portion_text.py --pages output/runs/<run_id>/pages_clean.jsonl \
  --portions output/runs/<run_id>/portions_resolved.jsonl \
  --out output/runs/<run_id>/portions_final_raw.json
```

## Modular driver (WIP)
- Modules are declared in `modules/registry.yaml`; recipes live in `configs/recipes/`.
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

Artifacts appear under `output/runs/<run_id>/` as listed in the recipe; use `--skip-done` to resume and `--force` to rerun stages.

## Output conventions
- `output/runs/<run_id>/` contains all artifacts: images/, ocr/, pages_raw/clean, hypotheses, locked/normalized/resolved portions, final JSON, `pipeline_state.json`.
- `output/run_manifest.jsonl` lists runs (id, path, date, notes).

## Roadmap (high level)
- Enrichment (choices, cross-refs, combat/items/endings)
- Turn-to validator (CYOA), layout-preserving extractor, image cropper/mapper
- Coarse+fine portionizer; continuation merge
- AI planner to pick modules/configs based on user goals

## Dev notes
- Requires Tesseract installed/on PATH.
- Models configurable; defaults use `gpt-4.1-mini` with `--boost_model gpt-5`.
- Artifacts are JSON/JSONL; runs are append-only and reproducible via configs.
