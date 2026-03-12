# Story 133 — Gemini 3 Flash as Cost-Optimized Crop Detector

**Priority**: High
**Status**: Done
**Ideal Refs**: Req 4 — Illustrate (detect, crop, catalog every illustration with precision)
**Spec Refs**: None — closes cost gap without introducing new compromises
**Depends On**: 125 (promptfoo eval framework), 126 (text validation loop)

## Goal

Replace Gemini 3 Pro ($1.25/book) with Gemini 3 Flash ($0.22/book) as the default illustration detector while maintaining crop quality. Fix Gemini's axis-swap coordinate bug that caused validator rejections and CV fallback. Add stylized text/logo detection to the prompt.

## Acceptance Criteria

- [x] Gemini 3 Flash produces 20/20 golden crops across all 13 golden pages
- [x] Zero validator rejections — all VLM boxes pass validation (no CV fallback needed)
- [x] Stylized text logos (e.g., book title pages) detected and extracted
- [x] Gemini array axis-swap fixed in production pipeline (`[y,x,y,x]` → `[x,y,x,y]`)
- [x] Thinking token truncation prevented (rescue_max_tokens increased to 8192)
- [x] Recipe config updated to use gemini-3-flash-preview
- [x] promptfoo eval confirms conservative-count prompt scores 0.900 avg / 92% pass rate

## Out of Scope

- Full 127-page production run (validated on golden subset only)
- Gate/pre-filter architecture (determined unnecessary — Flash is cheap enough for all pages)
- Improving Image001 score in eval (truncation issue, fixed by token budget increase)

## Approach Evaluation

Evaluated via promptfoo evals and cost modeling across multiple strategies:

- **Gate + expensive detector**: Cheap VLM pre-scan → SOTA extraction. Adds complexity, marginal savings when detector is already cheap. Rejected.
- **No gate + cheap detector (winner)**: Run Gemini 3 Flash on every page. $0.22/book, essentially zero false positive cost. Simplest architecture.
- **Prompt engineering**: Tested 4 prompts (baseline, strict-exclude, two-step, conservative-count). Conservative-count won: 0.900 avg vs 0.829 baseline.
- **Eval**: `benchmarks/tasks/image-crop-g3flash-prompts.yaml` — 4 prompts × 13 golden pages scored by `image_crop_scorer.py`.

## Tasks

- [x] Run promptfoo evals across new models (GPT-5.4, Sonnet 4.6, Gemini 3.1 variants)
- [x] Deep-dive Gemini coordinate format bug (native `[y,x,y,x]` at 0-1000 scale)
- [x] Fix eval scorer auto-normalization (try both axis orderings, pick best IoU)
- [x] Fix production pipeline `_call_vlm_boxes` array parsing for Gemini axis swap
- [x] Add `_auto_fix_axis_swap` safety net for page-level correction
- [x] Test gate vs no-gate cost models (gate adds complexity without meaningful savings)
- [x] Create conservative-count prompt to reduce over-detection on cover/multi-element pages
- [x] Run full 13-page golden eval with conservative-count prompt
- [x] Update `_BBOX_PROMPT` to include stylized text logos
- [x] Increase `rescue_max_tokens` to 8192 to prevent thinking token truncation
- [x] Update recipe config to use gemini-3-flash-preview
- [x] Visual verification: 20/20 golden crops match expected output
- [x] Run required checks:
  - [x] `python -m pytest tests/` (1 pre-existing unrelated failure)
  - [x] `python -m ruff check modules/ tests/` (1 pre-existing warning, not our code)
- [x] Verify Central Tenets:
  - [x] T0 — Traceability: crops trace to source page, VLM model, request ID
  - [x] T1 — AI-First: VLM detects and localizes illustrations, code only crops pixels
  - [x] T2 — Eval Before Build: ran promptfoo evals before changing production config
  - [x] T3 — Fidelity: 20/20 golden crops verified visually
  - [x] T4 — Modular: model swap via recipe config, no hardcoded assumptions
  - [x] T5 — Inspect Artifacts: side-by-side golden vs test comparison verified by user

## Files Modified

- `modules/extract/crop_illustrations_guided_v1/main.py` — Gemini array axis swap fix, `_auto_fix_axis_swap()`, stylized text in `_BBOX_PROMPT`
- `configs/recipes/recipe-onward-images-html-mvp.yaml` — rescue_model → gemini-3-flash-preview, rescue_max_tokens → 8192
- `benchmarks/prompts/crop-conservative-count.js` — New prompt + stylized text logo rule
- `benchmarks/tasks/image-crop-g3flash-prompts.yaml` — New eval config
- `benchmarks/scorers/image_crop_scorer.py` — Auto-normalization for Gemini native formats (earlier in session)

## Notes

### Key findings

- **Gemini native bbox format**: All Gemini models have a trained `[y_min, x_min, y_max, x_max]` format at 0-1000 scale that leaks through even when prompted for `[x0, y0, x1, y1]` at 0-1 scale. Three failure modes: (1) `box_2d` key with native format, (2) `image_box` array with swapped axes, (3) mixed scales.
- **Thinking token budget**: Flash models use 275-4000+ thinking tokens counted against `max_output_tokens`. At 4096 budget, ambiguous pages (like text logos) get truncated. 8192 prevents this.
- **Gate cost analysis**: For detectors under $0.50/book, gate savings don't justify added complexity. The break-even is ~$1/book detector cost.
- **False positives**: Gemini 3 Flash returns empty on 9/10 text-only pages. 1 "false positive" found a real faint logo. Essentially zero wasted cost.

### Model comparison (promptfoo eval, 13 golden pages)

| Model | Best Prompt | Avg Score | Pass Rate | Cost/book |
|-------|-------------|-----------|-----------|-----------|
| Gemini 2.5 Pro | baseline | 0.868 | 84.6% | ~$1.25 |
| Gemini 3 Pro | baseline | 0.856 | 76.9% | ~$1.25 |
| **Gemini 3 Flash** | **conservative-count** | **0.900** | **92.3%** | **~$0.22** |
| Gemini 2.5 Flash | baseline | 0.788 | 69.2% | ~$0.15 |

## Work Log

20260311-2100 — Started eval session. Ran new-models eval, discovered Gemini coordinate format bug. Deep-dived into Gemini native bbox format `[y,x,y,x]` at 0-1000 scale vs our expected `[x,y,x,y]` at 0-1.

20260311-2115 — Fixed eval scorer with auto-normalization (try both axis orderings). Gemini 2.5 Pro: 0.491→0.868, Gemini 3 Flash: emerged as viable at 0.829.

20260311-2130 — Gate vs no-gate cost analysis. Tested permissive gate prompts. Hit thinking token truncation bug (max_output_tokens: 50 eaten by 275 thinking tokens). User caught the contradiction. Fixed, Flash gates went 0%→92% recall. Concluded: no gate needed, Flash is cheap enough for all pages.

20260311-2145 — Prompt engineering. Tested 4 prompts. Conservative-count won: 0.900 avg (up from 0.829 baseline). Fixes Image000 (cover over-counting) and Image011 (4→2 boxes).

20260311-2200 — Production pipeline run on 13 golden pages. Found Gemini array axis swap not handled in production code. Flash returned `image_box: [y,x,y,x]` arrays — boxes landed on wrong regions, validator rejected. Added axis swap fix for Gemini array responses.

20260311-2130 — Re-ran pipeline. All 12/13 pages produce correct crops with zero validator rejections. Page 2 (text logo) truncated at 4096 tokens.

20260311-2135 — Increased rescue_max_tokens to 8192. Page 2 now extracted. 20/20 golden crops produced. Visual verification by user confirmed perfect results.

20260311-2140 — Updated recipe config: gemini-3-pro-preview → gemini-3-flash-preview, 4096 → 8192. Tests pass (1 pre-existing unrelated failure).

20260311-2150 — Added 20 unit tests for axis-swap logic (tests/test_gemini_axis_swap.py). All pass. Cleaned up 3 one-off eval configs.

20260311-2200 — Story marked Done. All 7 ACs met. Evals registry updated with Gemini 3 Flash scores (attempt 003). CHANGELOG entry added. User visually confirmed 20/20 golden crops via side-by-side comparison.
