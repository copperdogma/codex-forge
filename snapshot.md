# Pipeline Snapshot (2025-11-21) — Deathtrap Dungeon → Generic Book Processor

## 2026-01-11 update (Fighting Fantasy bring-up)
- Added pipeline support for new FF mechanics needed for **Robot Commando** and **Freeway Fighter** (Story 117):
  - Early duplicate-page detection (`detect_duplicate_pages_v1`)
  - Automatic section range detection (`detect_section_range_v1`)
  - Combat style frontmatter extraction + assignment (`extract_combat_styles_frontmatter_v1`, `assign_combat_styles_v1`)
  - Stateful navigation extraction (`extract_state_refs_v1`) and reachability support for templated/computed targets
  - Node/Ajv validator schema extended for `conditional` + `combat_metric` and a small runtime helper `evaluateCondition`

## What we built
- **Stages** (reusable for any CYOA / gamebook):
  1) PDF → images (`pages_dump.py` uses pdf2image)
  2) Per-page OCR → `pages_raw.jsonl` (pytesseract)
  3) Per-page multimodal cleaning → `pages_clean.jsonl` (LLM fixes OCR errors; keeps raw + confidence)
  4) Sliding-window, LLM-led portionization with priors → `window_hypotheses.jsonl`
  5) Global consensus → `portions_locked*.jsonl`
  6) Dedupe / normalize IDs (S### for sections, P### for others)
  7) Overlap resolution → `portions_resolved.jsonl` (non-overlapping, full coverage)
  8) Final assembly of raw text per portion → `portions_final_raw.json`

- **Models**: Default `gpt-4.1-mini` with `--boost_model gpt-5` for low/empty outputs. Cleaning uses the same pair. Multimodal (page images get base64-embedded automatically).

- **Portion priors**: Portionizer can accept a prior portions file (`--prior`) so it can mark continuations/merges and make better boundary decisions.

- **State & traceability**: `pipeline_state.json` (per output dir) tracks which pages are done per stage; all artifacts are JSON/JSONL for audit. Each final portion includes page spans, source images, orig IDs, and raw text with page markers.

## Current status of Deathtrap Dungeon
- **Full book processed (all 113 pages)** into `pipeline/output_full/`:
  - `pages_clean.jsonl` (cleaned text + confidence)
  - `window_hypotheses.jsonl` (combined batches 1–50, 41–90, 81–113)
  - `portions_resolved.jsonl` (103 non-overlapping portions, full coverage)
  - `portions_final_raw.json` (103 portions with assembled raw_text)
  - `pipeline_state.json` marks images/ocr/clean/portionize done; enrichment not started
- **Pages 1–20 sample run** remains in `pipeline/output_portion_1_20/` with final assembled portions for that range.

## Key design choices & rationale
- **Multimodal cleaning early**: Higher-quality text improves portion detection; keeps raw OCR for audit.
- **Sliding windows + priors**: Windows give cross-page context; priors let small batches still extend/merge spans without long-lived chat state.
- **Batch resilience**: Portionization is append-only; consensus can be rerun anytime on accumulated hypotheses. Small overlaps are recommended; cross-boundary spans need some shared context.
- **Non-overlap resolution**: After consensus, pick highest-confidence, non-overlapping spans and fill gaps to guarantee coverage.
- **ID normalization**: Sequential S### for sections; P### (or original IDs) for others; dedupe suffixes to avoid collisions.
- **Final assembly**: Keeps page markers and source image paths for traceability and later image cropping.

## Known gaps / next steps
1) **Enrichment pass** (not yet built): For each resolved portion, extract structured fields (choices/targets, combat blocks, test-luck flags, item adds/uses, endings). Should consume `portions_resolved.jsonl` + `pages_clean.jsonl` and emit `portions_enriched.jsonl`.
2) **Coarse+fine dual pass** (optional): Add a coarse large-window sweep (e.g., 25–30 pages, stride ~10) merged with existing fine windows to better catch long portions. Merge hypotheses before consensus.
3) **Continuation merge**: Post-consensus step that merges spans with `continuation_of` hints into single long portions when safe.
4) **Image cropping/mapping**: Use `source_images` and spans to detect/crop illustrations and map them to portions/sections.
5) **App merge**: Build `data.json` for the web app from enriched sections (S###), leaving other portions as ancillary content.
6) **Automation**: A top-level driver to run stages with overlap batching, coarse+fine passes, and final merge by default.

## Future plan (toward “codex-forge”)
- **Modular system**: Swappable modules (OCR, clean, portionize, layout-preserve, turn-validator, enrichment, image cropper, typography-preserve, etc.).
- **AI-first planner**: Guided assistant (via AGENTS.md + module manifest) that asks about the use case (keep layout? validate “turn to N”? keep typography?) and emits a pipeline config; proposes new modules when gaps exist.
- **Layout-aware variants**: Alternate extractors that preserve bounding boxes/formatting for layout-sensitive books; choose the module per run.
- **Validation modules**: For CYOA, a turn-to cross-ref checker; skip for non-CYOA.
- **Batch/overlap strategy**: Append-only hypotheses; overlapping/boundary-context runs; one global consensus ensures long spans can form even with small batches.
- **Repo structure**: Rename `pipeline/` to `codex-forge/`; add `/modules` for components, `/configs` for recipes, `/runs/<name>/` for artifacts/state.
- **Portability**: Keep JSON/JSONL artifacts; no DB; easy to lift into other repos/projects.

## Integration guidance (new repo / relocation)
- Keep `pipeline/` as a standalone module; expose a CLI entrypoint per stage.
- Preserve JSONL artifacts between stages to allow partial reruns.
- For batching: run overlapping ranges, append to the same `window_hypotheses.jsonl`, then one global consensus/resolve/build.
- Defaults: window=8, stride=1, `gpt-4.1-mini` + boost `gpt-5`, min_conf=0.55, force coverage via `--range_start/--range_end`.
- Dependencies already pinned in `requirements.txt`; Tesseract must be installed on the host.

## Quick recipes
- **Full run (already done for DD)**: clean → portionize (overlap batches) → consensus → dedupe → normalize → resolve → build.
- **Touch-up a boundary**: re-run `portionize.py` on an overlapping slice (e.g., p60–80) appending to `window_hypotheses.jsonl`, then rerun consensus→resolve→build.
- **Partial export**: run build against a subset of `portions_resolved.jsonl` to get `portions_final_raw.json` for that slice.

## File map (output_full/)
- `pages_clean.jsonl` — cleaned per-page text/images
- `window_hypotheses.jsonl` — all portion hypotheses (batches combined)
- `portions_locked*.jsonl`, `portions_resolved.jsonl` — progressively filtered spans
- `portions_final_raw.json` — final assembled per-portion text (traceable)
- `pipeline_state.json` — stage completion flags for all 113 pages
