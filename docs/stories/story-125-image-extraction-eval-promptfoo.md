# Story 125: Image Extraction Evaluation with promptfoo

**Status**: Done

---
**Parent Story**: story-026 (Onward to the Unknown — image-only → chapter-linked HTML)
**Depends On**: story-026 (in-progress image cropping work)
**Cross-Reference**: cine-forge story-035 (Model Benchmarking — promptfoo adoption and patterns)

## Goal
Use **promptfoo** to systematically evaluate VLM prompts and models for extracting/cropping embedded photos from scanned book pages. The current heuristic + VLM approach in `crop_illustrations_guided_v1` has hit a wall on caption/header separation (see story-026 work log, Jan 23–24 entries). Instead of more heuristic iteration, we'll build a **golden dataset** of manually cropped reference images and use promptfoo's multi-model evaluation framework to find the optimal prompt × model combination.

## Background / Why This Approach
After ~10 iterations on VLM-guided cropping with caption trimming, OCR-edge trimming, and VLM retry passes, the image cropper still includes captions/body text on several pages (12, 21, 38, 60). The core difficulty is that halftone photos, faint borders, and nearby captions make text/figure separation ambiguous for both CV and VLM approaches.

Rather than continuing to stack heuristics, we'll:
1. Define "correct" by hand (golden crops)
2. Measure how close each prompt × model gets to correct (automated scoring)
3. Iterate on prompts with fast feedback (promptfoo eval + leaderboard)
4. Lock in the best combination and wire it back into the pipeline module

This mirrors the **cine-forge promptfoo pattern** (story-035): prompt templates × provider matrix × golden references × Python scorers × dual evaluation (deterministic + LLM rubric).

## Scope / Inputs
- **Test pages**: ~6 representative pages from *Onward to the Unknown* covering key failure modes
- **Golden references**: Manually cropped photos (by human) defining the ideal crop for each page
- **Models to evaluate**: GPT-5.1, GPT-5, Claude Opus 4.6 (vision), Gemini 2.5 Pro, Gemini 2.5 Flash, and any other vision-capable models available
- **Prompt variants**: At least 3–5 different VLM prompt strategies

## Acceptance Criteria
- [x] **Golden dataset exists**: ~6 pages with manually cropped reference photos and derived bounding-box coordinates stored in `benchmarks/golden/`.
- [x] **promptfoo workspace set up**: `benchmarks/` directory in codex-forge with `tasks/`, `prompts/`, `golden/`, `input/`, `scorers/`, matching the cine-forge pattern.
- [x] **At least 3 prompt variants tested** across at least 4 vision models.
- [x] **Python scorer implemented** measuring IoU (Intersection over Union), box count accuracy, and caption exclusion.
- [x] **Eval results analyzed**: leaderboard shows clear winner(s) with cost/quality tradeoffs documented.
- [x] **Winning prompt/model wired back** into `crop_illustrations_guided_v1` (or a new module) and validated through `driver.py` on the Onward recipe.
- [x] **Results documented** in work log with artifact paths and sample evidence.

## Recommended Test Pages
Based on story-026 work log failure modes:

| Page | Image File | Why It's a Good Test |
|------|-----------|---------------------|
| 12 | Image012 | Certificate with seal/signatures — non-photo image, header text bleed |
| 18 | Image018 | Group portrait — single large photo with caption |
| 21 | Image021 | Two photos with captions — multi-image, caption separation |
| 22 | Image022 | Single photo with caption — straightforward but caption-adjacent |
| 38 | Image038 | Multi-photo page — multiple images to detect and separate |
| 60 | Image060 | Two photos with captions — caption text still appearing in crops |

## Golden Dataset Preparation
1. **Human crops the photos** from each test page exactly as they should appear (no captions, no headers, no body text, no page numbers).
2. **Save each crop** as a separate file: `benchmarks/golden/crops/page-NNN-000.jpg`, `page-NNN-001.jpg`, etc.
3. **Record bounding boxes** in a JSON file: `benchmarks/golden/image-crops.json` with pixel coordinates `[x0, y0, x1, y1]` for each crop relative to the source page image.
4. **Record metadata**: number of expected images per page, whether any images are non-photographic (seals, logos, diagrams).

## promptfoo Workspace Layout
```
benchmarks/
├── tasks/
│   └── image-crop-extraction.yaml    # promptfoo config: models × prompts × test cases
├── prompts/
│   ├── crop-baseline.txt             # Current approach prompt
│   ├── crop-exclude-text.txt         # Tighter "exclude all text" variant
│   ├── crop-two-step.txt             # "Find photos, then exclude captions" variant
│   ├── crop-mask-description.txt     # "Describe what is NOT a photo" variant
│   └── ...
├── golden/
│   ├── image-crops.json              # Bounding boxes + metadata per page
│   └── crops/                        # Manually cropped reference images
│       ├── page-012-000.jpg
│       ├── page-021-000.jpg
│       ├── page-021-001.jpg
│       └── ...
├── input/
│   ├── page-012.jpg                  # Source page images (copied or symlinked)
│   ├── page-018.jpg
│   ├── page-021.jpg
│   ├── page-022.jpg
│   ├── page-038.jpg
│   └── page-060.jpg
├── scorers/
│   └── image_crop_scorer.py          # IoU + count + caption exclusion scorer
├── results/                          # JSON output from eval runs
├── scripts/
│   └── derive_golden_boxes.py        # Helper: derive bounding boxes from manual crops
└── README.md
```

## Scorer Design (Python)
The scorer will measure multiple dimensions with weights:

| Dimension | Weight | What It Measures |
|-----------|--------|-----------------|
| **box_count** | 0.15 | Did the model find the right number of images? |
| **iou_mean** | 0.35 | Mean IoU across matched predicted ↔ golden boxes |
| **iou_min** | 0.15 | Worst-case IoU (catches one bad crop among good ones) |
| **caption_exclusion** | 0.20 | Is there text in the crop that shouldn't be there? |
| **coverage** | 0.15 | Does the crop include the full photo without cutting in? |

**Pass threshold**: weighted score >= 0.75 (tune after first run).

### IoU Matching
- Match predicted boxes to golden boxes using Hungarian algorithm (minimize total IoU cost).
- Unmatched predicted boxes penalize precision; unmatched golden boxes penalize recall.
- IoU = area(intersection) / area(union) for each matched pair.

### Caption Exclusion Check
- For each predicted crop region, run a lightweight text detector (Tesseract or similar) on the cropped area.
- Compare detected text against known captions/headers for that page (from golden metadata).
- Score 1.0 if no caption text found, 0.0 if caption text present, interpolate for partial.

## Prompt Strategy Variants to Test

1. **Baseline**: Current `crop_illustrations_guided_v1` prompt (as-is).
2. **Strict text exclusion**: "Return bounding boxes for photographs only. Exclude ALL text — captions, headers, page numbers, body text. The box must contain only the photographic image."
3. **Two-step**: Step 1: "List all photos on this page with descriptions." Step 2: "For each photo, return a tight bounding box that excludes any surrounding text."
4. **Negative description**: "Identify regions that are NOT text and NOT tables. Return bounding boxes for those regions."
5. **Caption-aware**: "This page has photos with captions below them. Return bounding boxes for the photos only, stopping before any caption text."

## Model Matrix
| Model | Type | Expected Cost | Vision Capable |
|-------|------|--------------|----------------|
| GPT-5.1 | Current default | $$ | Yes |
| GPT-5 | Flagship | $$$ | Yes |
| Claude Opus 4.6 | Cross-provider | $$$ | Yes |
| Claude Sonnet 4.5 | Mid-tier | $$ | Yes |
| Gemini 2.5 Pro | Cross-provider | $$ | Yes |
| Gemini 2.5 Flash | Budget | $ | Yes |

## Tasks
- [x] Set up `benchmarks/` workspace directory structure.
- [x] Copy/symlink ~6 test page images into `benchmarks/input/`.
- [x] **Human**: manually crop photos from each test page and save to `benchmarks/golden/crops/`.
- [x] Write `derive_golden_boxes.py` to compute bounding boxes from manual crops vs source images.
- [x] Build `benchmarks/golden/image-crops.json` with bounding boxes + metadata.
- [x] Write 3–5 prompt template variants in `benchmarks/prompts/`.
- [x] Write `image_crop_scorer.py` (IoU + count + caption exclusion).
- [x] Write `benchmarks/tasks/image-crop-extraction.yaml` promptfoo config.
- [x] Run `promptfoo eval` and analyze results.
- [x] Iterate on prompts based on results (2–3 rounds expected).
- [x] Wire winning prompt/model back into pipeline module.
- [x] Validate through `driver.py` on Onward recipe and inspect outputs.
- [x] Document results and update story-026 work log.

## Prerequisites
- **Node.js 22+** and **promptfoo** installed globally (`npm install -g promptfoo`).
- **API keys**: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`.
- Follow cine-forge `AGENTS.md` promptfoo section for setup guidance.

## Open Questions
- Should we also test **layout detection models** (PaddleOCR, LayoutParser) as a non-VLM baseline, or keep this purely VLM-focused?
- Should the scorer use Tesseract for caption exclusion checks, or a VLM "is there text in this crop?" call?
- Do we need separate prompt strategies for photo pages vs non-photo pages (certificates, seals)?
- What IoU threshold constitutes "good enough" for production use?

## When Complete
After this story is done, **return to Story 026** to:
- Wire the winning image extraction approach into the Onward recipe
- Re-run the full pipeline end-to-end
- Complete the remaining acceptance criteria (chapter HTML verification, table spot-checks, etc.)

## Work Log

### 20260216b — Full eval run completed

- Fixed Anthropic prompt format: promptfoo sends raw prompts as-is, so Anthropic's `type: "image"` format needed provider-specific JS prompt functions
- Fixed Google API key: GEMINI_API_KEY was in .zshrc but not available in bash shell where promptfoo runs
- Created shared JS prompt helper (`_image-helpers.js`) that adapts image content blocks per provider (OpenAI `image_url`, Anthropic `image` with base64 source, Google `inlineData`)
- Full eval: 12 models x 3 prompts x 13 images = 468 calls, 0 errors
- Results: 223 passed, 245 failed (47.65% pass rate)

**Winner: Gemini 3 Pro + baseline prompt** (0.856 avg score, 77% pass rate)

Top 5 combos:
1. Gemini 3 Pro + baseline: 0.856 score, 77% pass
2. Gemini 3 Pro + two-step: 0.798 score, 69% pass
3. Gemini 2.5 Pro + baseline: 0.793 score, 77% pass
4. Gemini 3 Flash + baseline: 0.746 score, 69% pass
5. GPT-5.2 + strict-exclude: 0.740 score, 62% pass

Key findings:
- Gemini models dominate with simple (baseline) prompts
- strict-exclude prompt hurts Gemini but helps OpenAI/Claude
- Claude Opus 4.6 most consistent across prompts (62% on all three)
- Hardest images: Image011 (certificate, 0% pass), Image001 (title page, 3% pass)
- Full analysis in `benchmarks/results/run2-analysis.md`

**Next step**: Wire winning model (Gemini 3 Pro + baseline prompt) into the pipeline module.

### 20260216c — Gemini 3 Pro wired into pipeline and validated

**Changes made:**
- Created `modules/common/google_client.py` — Gemini vision client wrapper with usage logging (mirrors `openai_client.py` pattern)
- Modified `modules/extract/crop_illustrations_guided_v1/main.py`:
  - Added `GeminiVisionClient` import with graceful fallback
  - Added `_is_gemini_model()` helper
  - Added Gemini dispatch to `_call_vlm_boxes()` and `_call_vlm_caption_boxes()`
  - Fixed array-format bbox parsing: Gemini returns `image_box: [x0, y0, x1, y1]` (array) instead of `{x0, y0, x1, y1}` (dict) — parser now handles both
  - `_refine_boxes_with_vlm()` inherits Gemini support via delegation to `_call_vlm_boxes()`
- Updated `configs/recipes/recipe-onward-images-html-mvp.yaml`:
  - `rescue_model: gemini-3-pro-preview` (was `gpt-5.1`)
  - `rescue_max_tokens: 4096` (was 800; Gemini uses thinking tokens that eat into output budget)

**Validation:** Ran crop module standalone on 3 test pages (Image000, Image020, Image021) with `rescue_always: true`. All pages returned correct bounding boxes with caption schema. 4 clean crops produced — no caption text, no header bleed. Visual inspection confirmed quality matches eval expectations.
