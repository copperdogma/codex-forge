# Codex-Forge Requirements
_AI-first, modular book-to-structured-data pipeline_

## Purpose & Goals
- Provide a reusable pipeline to convert scanned or born-digital books into structured JSON artifacts with full traceability.
- Support multiple book types (CYOA/gamebooks and non-CYOA) by swapping modules (OCR, cleaning, portionization, validation, enrichment, layout preservation).
- Enable AI-guided setup: the system should help users choose modules and configure runs based on their goals (e.g., preserve layout, validate cross-references).

## Scope (MVP)
- Input: PDF or page images.
- Output: Structured portions with cleaned text, page spans, source image refs, confidence, and trace IDs; intermediate artifacts kept for audit.
- Baseline modules: OCR → page cleaning → portionization → consensus/dedupe/normalize → overlap resolution → final text assembly.
- Batch-friendly and restartable: allow partial runs, overlapping reruns, and global recompute of consensus.

## Functional Requirements
1) **Ingestion**: accept PDF or image dirs; render to images (configurable DPI) if PDF.
2) **OCR**: per-page raw text + image path, page numbers.
3) **Cleaning**: multimodal LLM fixes OCR; outputs clean_text + confidence; keep raw_text; auto boost if low confidence.
4) **Portionization**: sliding-window LLM with priors; multimodal; emits spans with type/title/confidence/continuation hints; configurable window/stride/range; append-only hypotheses.
5) **Consensus & Resolution**: global consensus; min confidence; force range coverage; dedupe/normalize IDs; resolve overlaps; fill gaps.
6) **Assembly**: per-portion JSON with page spans, source images, confidence, orig IDs, concatenated text (prefers clean_text).
7) **Outputs & State**: run dir `output/runs/<run_id>/` (images/, ocr/, pages_raw/clean, hypotheses, locked/normalized/resolved, final JSON, pipeline_state); run manifest `output/run_manifest.jsonl`.
8) **Configuration**: CLI/YAML for models, windows, strides, thresholds, ranges, run_id, priors, DPI/psm/oem/lang; sensible defaults.
9) **Validation**: structural checks; pluggable validators (e.g., turn-to cross-refs for CYOA) optional.
10) **Traceability**: keep spans, source images, confidences; retain JSONL artifacts for audit/rerun.

## Non-Functional Requirements
- Modularity: swappable modules, easy addition of new ones.
- Resilience: partial runs recoverable; append-only hypotheses; rerunnable consensus.
- Portability: JSON/JSONL only; no DB; offline except LLM calls.
- Performance: batching with overlaps; coarse+fine option; cost-conscious.
- Transparency: confidences/notes preserved; no silent merges.
- Versioning: record model/config per run (config snapshot recommended).

## Future Modules / Extensions
- Enrichment (`portions_enriched.jsonl`): extract choices, targets, combat, items, endings; produce app-ready `data.json` for interactive use.
- Turn-to validator for CYOA; skip for non-CYOA.
- Layout-preserving extractor (bounding boxes, typography).
- Image cropper/mapper for illustrations.
- Coarse+fine portionizer; continuation-merge pass.
- AI planner: gather user goals, emit pipeline config, suggest new modules when needed.

## Repository & Structure
- Root: scripts/modules; `docs/`; `snapshot.md`; `output/` (git-ignored); configs.
- Outputs: `output/runs/<run_id>/`; manifest at `output/run_manifest.jsonl`.
- Ignore `.venv/`, `__pycache__/`, `output/`.

## Acceptance Criteria (MVP)
- Given a PDF/input images, produce a run folder with: `pages_raw.jsonl`, `pages_clean.jsonl`, `window_hypotheses.jsonl`, `portions_resolved.jsonl`, `portions_final_raw.json`, `pipeline_state.json`, manifest entry.
- Can rerun portionize on a sub-range and recompute consensus without data loss.
- Models/windows/thresholds configurable via CLI/config without code changes.
