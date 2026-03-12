# Story 134 — OCR Pipeline Speed & Cost Optimization

**Priority**: High
**Status**: Draft
**Ideal Refs**: Req 3 (Extract — clean, accurate text), Vision "instant" and "cost negligible"
**Spec Refs**: C1 (OCR quality), Story 082 (large-image cost optimization — prior art)
**Depends On**: None (builds on existing `ocr_ai_gpt51_v1` module)

## Goal

Reduce OCR pipeline wall-clock time and API cost for a full book run without sacrificing quality. Currently a 127-page Onward run sends 5100x6600 (34MP) images one at a time sequentially, with no downsampling. This story investigates multiple optimization axes and implements the winners.

### Current Baseline (estimated for 127-page Onward run)

- **Image size**: 5100x6600 (34MP), ~1.2MB JPEG per page
- **Execution**: Sequential, one API call per page
- **Model**: Claude Sonnet 4.6 (current recipe)
- **Cost**: ~$0.18/call × 127 pages ≈ **$23/run** (estimated)
- **Time**: ~110s/call × 127 pages ≈ **3.9 hours** (sequential)

### Target

- **Cost**: < $10/run (>50% reduction)
- **Time**: < 30 minutes (>85% reduction via parallelism)
- **Quality**: No regression — structure_preservation ≥ 0.945 on table fidelity eval

## Acceptance Criteria

- [ ] **Image downsampling**: Configurable `max_long_side` param (default ~2048px). Quality eval shows no regression at chosen resolution.
- [ ] **Parallel execution**: Configurable `concurrency` param (default 5-10). Pages processed in parallel with rate limiting.
- [ ] **Multi-page context eval**: Tested whether sending consecutive pages together improves quality at table/paragraph boundaries. Evidence-based decision on single vs multi-page mode.
- [ ] **Batch API eval**: Tested async batch endpoints (OpenAI Batch API, Anthropic Message Batches) for 50% cost reduction. Evidence-based decision on sync vs batch.
- [ ] **Model tiering eval**: Tested using a cheap model (nano/haiku) for simple prose, expensive model only for complex pages. Requires content-type signal.
- [ ] **Cost/speed metrics**: Every optimization measured with latency_ms, cost_usd, and quality score. Recorded in eval registry.
- [ ] **No quality regression**: Table fidelity eval (onward-table-fidelity) passes at ≥0.945 with optimizations enabled.
- [ ] **Recipe-configurable**: All optimizations controlled via recipe params, not hardcoded.

## Out of Scope

- Changing the OCR model itself (that's the model eval story, not this one)
- Changing the OCR prompt (prompt tuning is separate)
- Non-OCR pipeline stages (crop, table rescue, portionize, etc.)
- Building a custom OCR model or fine-tuning

## Approach Evaluation

Six optimization axes, roughly independent — can be combined:

### A1: Image Downsampling
- **Hypothesis**: Most vision APIs internally resize to ~2048px. Sending 5100x6600 wastes bandwidth and may waste input tokens.
- **Prior art**: Story 082 found 0.971 text fidelity when downsampling to old benchmark sizes (~1700x2200). Never implemented.
- **Test**: Run table fidelity eval at 5100, 3000, 2048, 1500, 1024px long side. Find the quality cliff.
- **Expected impact**: Faster uploads, fewer input tokens → lower cost. Possibly faster API response.
- **Implementation**: Add `max_long_side` param to OCR module. Resize with Pillow before base64 encoding.

### A2: Parallel Execution
- **Hypothesis**: Pages are independent. N concurrent API calls → ~Nx speedup (up to rate limits).
- **Test**: Run 10 pages with concurrency 1, 3, 5, 10. Measure wall-clock time and check for rate limit errors.
- **Expected impact**: 5-10x wall-clock reduction.
- **Implementation**: `asyncio` or `concurrent.futures.ThreadPoolExecutor` in OCR module. Add `concurrency` param.

### A3: Multi-Page Context Windows
- **Hypothesis**: Sending 2-3 consecutive pages together gives the model context for table continuations, hyphenated words, and section boundaries — potentially better quality.
- **Counter-hypothesis**: Single-page is simpler to parallelize and retry. Table rescue pass already handles cross-page issues.
- **Test**: Run table fidelity eval with single-page vs 2-page vs 3-page context windows. Compare quality and cost.
- **Expected impact**: Possibly better quality on table boundaries; possibly worse cost (more input tokens per call).
- **Implementation**: Group manifest pages into sliding windows, combine images in single API call.

### A4: Batch API (Async, 50% Cheaper)
- **Hypothesis**: OpenAI Batch API and Anthropic Message Batches offer 50% cost reduction for async processing (results within 24h).
- **Test**: Submit a 10-page batch, verify results are identical to sync calls.
- **Expected impact**: 50% cost reduction. Slower turnaround (minutes to hours), acceptable for book processing.
- **Implementation**: New batch mode in OCR module. Submit all pages, poll for completion, collect results.

### A5: Model Tiering (Cheap Model for Simple Pages)
- **Hypothesis**: Prose-only pages (no tables, no images) don't need an expensive model. A nano/haiku model could handle them at 10-20x lower cost.
- **Test**: Run prose-only pages through cheap models, compare quality. Need content-type signal (exists from Story 062).
- **Expected impact**: 30-50% cost reduction if 60%+ of pages are simple prose.
- **Implementation**: Two-pass: classify page complexity, route to appropriate model. Recipe params for `default_model` and `complex_model`.

### A6: Page Deduplication / Skip Blank Pages
- **Hypothesis**: Some books have blank pages, repeated headers, or near-duplicate content. Detecting and skipping these saves cost.
- **Test**: Scan Onward images for blank/near-blank pages. Count how many could be skipped.
- **Expected impact**: Small (5-10% for most books), but free.
- **Implementation**: Check image entropy or white pixel ratio before sending to API.

### A7: Re-eval Budget Models in Single-Page Mode
- **Hypothesis**: The 2026-03-11 eval sent multi-page table images in a single API call (4-6 pages per call). Budget models (Gemini Flash, Flash-Lite, GPT-5 Mini/Nano) failed due to output truncation — reasoning tokens consumed the output budget, leaving insufficient tokens for the full table HTML. But the pipeline processes one page at a time, and the table rescue pass handles cross-page stitching downstream. Single-page mode eliminates the truncation problem entirely.
- **Evidence from 2026-03-11 eval**: Gemini 3.1 Flash-Lite scored 0.931 on alma (shortest table, 4 pages) but 0.138 on arthur (6 pages) — clearly truncation, not capability. Gemini 3 Flash scored 0.927 on alma but 0.272 on marie_louise (reasoning used 62K tokens, only 2.6K left for output).
- **Test**: Run single-page OCR eval on the same golden pages with budget models. Compare per-page quality (not unified table quality — that's the table rescue pass's job). Need a single-page scorer variant.
- **Expected impact**: If budget models match quality per-page, cost drops dramatically. Gemini 2.5 Flash-Lite at $0.005/call vs Gemini 3.1 Pro at $0.09/call = 18x cheaper. Even Gemini 2.5 Flash at $0.06 would be significant.
- **Key insight**: The multi-page eval is testing two things at once — model OCR quality AND ability to produce long unified output. Separating these lets us find models that are excellent at OCR but limited in output length, which is fine for a one-page-at-a-time pipeline.

### Eval Strategy

- **Primary eval**: `onward-table-fidelity` (existing, 3 test cases, target 0.945)
- **Secondary eval**: Full pipeline run cost/time comparison (before vs after)
- **Single-page eval**: New eval variant — per-page OCR quality scored independently, for budget model re-evaluation
- **All optimizations must be measured independently** before combining

## Tasks

- [ ] Baseline measurement: time and cost a full 127-page Onward OCR run (sequential, full resolution)
- [ ] A1: Image downsampling — resolution sweep eval (5100/3000/2048/1500/1024)
- [ ] A2: Parallel execution — implement ThreadPoolExecutor with configurable concurrency
- [ ] A3: Multi-page context — eval single vs 2-page vs 3-page windows on table fidelity
- [ ] A4: Batch API — prototype OpenAI Batch API for OCR, compare cost
- [ ] A5: Model tiering — eval cheap models on prose-only pages
- [ ] A6: Blank page detection — scan Onward for skippable pages
- [ ] A7: Re-eval budget models in single-page mode (Flash, Flash-Lite, Mini, Nano) — they failed multi-page eval due to truncation, not capability
- [ ] Combine winning optimizations into the OCR module
- [ ] Full pipeline run with optimizations — verify no quality regression
- [ ] Update recipe with new params (max_long_side, concurrency, etc.)
- [ ] Run required checks:
  - [ ] `python -m pytest tests/`
  - [ ] `python -m ruff check modules/ tests/`
- [ ] Search all docs and update any related to what we touched
- [ ] Verify Central Tenets:
  - [ ] T0 — Traceability: every output traces to source page, OCR engine, confidence, processing step
  - [ ] T1 — AI-First: didn't write code for a problem AI solves better
  - [ ] T2 — Eval Before Build: measured SOTA before building complex logic
  - [ ] T3 — Fidelity: source content preserved faithfully, no silent losses
  - [ ] T4 — Modular: new recipe not new code; no hardcoded book assumptions
  - [ ] T5 — Inspect Artifacts: visually verified outputs, not just checked logs

## Files to Modify

- `modules/extract/ocr_ai_gpt51_v1/main.py` — Add downsampling, parallelism, batch mode, multi-page context
- `modules/extract/ocr_ai_gpt51_v1/module.yaml` — New params: max_long_side, concurrency, batch_mode, context_pages
- `configs/recipes/recipe-onward-images-html-mvp.yaml` — Wire new params
- `configs/recipes/recipe-images-ocr-html-mvp.yaml` — Wire new params
- `docs/evals/registry.yaml` — Record optimization eval results
- `benchmarks/tasks/onward-table-fidelity.yaml` — May need variants for resolution tests

## Notes

- OpenAI documents that images are internally resized: "low" detail = 512x512, "high" detail = max 2048px short side, max 768 tiles. Sending 5100x6600 may be processed identically to 2048x2650.
- Anthropic has similar internal resizing for Claude vision.
- Google Gemini may handle full resolution better given their video/image training.
- Story 082 proved downsampling is viable but never shipped the implementation. This story finishes that work and adds parallelism.
- The multi-page context question is genuinely open — could go either way. The table rescue pass may already handle cross-page issues well enough that single-page OCR + rescue is better than multi-page OCR.

## Plan

{Written by build-story Phase 2 — per-task file changes, impact analysis, approval blockers}

## Work Log

{Entries added during implementation — YYYYMMDD-HHMM — action: result, evidence, next step}
