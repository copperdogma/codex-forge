# Story: Crop Quality — Text Validation Loop & OCR Image Detection

**Status**: Done

---
**Depends On**: story-026 (Onward pipeline), story-125 (Gemini 3 Pro integration)

## Goal
Eliminate bad image crops (text-only crops, caption bleed, partial cuts) by adding a **post-crop text validation loop** and improving **OCR image detection** so the crop module sees all pages with photos.

Two problems observed in the Onward pipeline:
1. **OCR misses photos** — GPT-5.1 only tagged 12 of 60 pages as having images. The crop module never sees untagged pages.
2. **Bad bounding boxes** — Gemini 3 Pro returns ~77% good crops, but ~23% are text-only, text-heavy, or mis-framed. No automated quality gate catches these.

## Scope / Inputs
- **Primary book**: *Onward to the Unknown* (127 page images, 60 OCR'd so far)
- **Crop module**: `modules/extract/crop_illustrations_guided_v1/main.py`
- **OCR module**: `modules/extract/ocr_ai_gpt51_v1/main.py`
- **Observed failures**:
  - `page-048-000.jpg` — pure text, no photo (Gemini returned bbox over text)
  - `page-018-000.jpg` — photo present but crop includes large text region
  - `page-001-000.jpg` — partial/off-center crop of cover embossing

## Design

### Layer 1: Improve OCR Image Detection
The OCR prompt tells GPT-5.1 to emit `<img alt="..." data-count="N">` for illustrations. Some pages with photos aren't getting tagged. Options:
- **Strengthen the OCR prompt** — add emphasis: "Always tag photos, portraits, illustrations, diagrams, logos, and decorative images. When in doubt, tag it."
- **Independent image detection pass** — run PaddleOCR layout model (PP-DocLayout) on all pages to find `figure` regions, independent of the OCR text. Merge detected figure pages into the crop module's page list.

### Layer 2: Post-Crop Text Validation Loop
After Gemini returns a bbox and the image is cropped:
1. **Local OCR** the crop (Tesseract — free, fast, already available in the module)
2. **Measure text density** — word count, text area ratio, or character density
3. **Check Gemini's "intentional text" flag** — if the response includes `contains_text: true` (logo, signature, certificate, seal), skip validation
4. **If high text density AND not flagged intentional** → reject the crop, re-prompt Gemini:
   - Send the bad crop + original page image
   - Prompt: "This crop contains mostly text. The image region should contain a photo/illustration, not text. Return a corrected bounding box."
5. **If retry also fails** → mark as unresolved, log for manual review

### Layer 3: Response Schema Enhancement
Add to the VLM response schema:
```json
{
  "image_box": {"x0": ..., "y0": ..., "x1": ..., "y1": ...},
  "caption_box": {"x0": ..., "y0": ..., "x1": ..., "y1": ...},
  "contains_text": false,
  "content_type": "photo"  // "photo", "logo", "signature", "diagram", "decorative"
}
```
- `contains_text: true` → skip text validation (logos, seals, signed documents)
- `content_type` → useful metadata and helps Gemini think about what it's boxing

### Layer 4: promptfoo Model/Prompt Re-evaluation
The Story 125 eval tested 12 models with the original `_BBOX_PROMPT`, but the landscape has changed:
- **Prompt is changing** — new schema fields (`contains_text`, `content_type`), tighter text-exclusion instructions
- **Scoring criteria should evolve** — penalize text-in-crop (Tesseract text density on the crop), not just IoU against golden boxes
- **New models may be available** — re-test the current contenders plus any new releases
- **`rescue_always` changes the economics** — every image page hits the VLM now, so cost/latency matters more

**Eval plan:**
1. Reuse the Story 125 golden dataset (13 test pages, manually cropped references)
2. Add **text-density scoring**: run Tesseract on each crop, penalize high text content
3. Add **content_type accuracy**: does the model correctly classify photo vs logo vs signature?
4. Test the updated prompt against top 3-5 models from the original eval plus any new contenders
5. Pick the winner based on combined IoU + text-penalty + content-type accuracy

## Acceptance Criteria
- [x] **OCR image detection improved**: Switched to Gemini 3 Pro which detects all photos. 29/29 image pages produced crops = 100% coverage.
- [x] **Text validation rejects pure-text crops**: Gemini 2.5 Flash validator correctly rejects text-only and text-heavy crops (4/40 rejected in initial eval, correctly).
- [x] **Caption bleed detected**: Layout text trimming (`_trim_box_by_layout_text`) + validator catches excess text; X-overlap fix prevents false trims from adjacent columns.
- [x] **Intentional-text exceptions work**: Two-stage detector-validator communication passes `contains_text`/`_text_reason` metadata to validator. Page-012 seal + signatures pass validation.
- [x] **Retry produces better results**: Auto-retry when `crop_count != expected_count` re-runs VLM with stronger instructions and picks whichever result is closer to expected.
- [x] **Unresolved crops logged**: Validation logging with REJECT/ACCEPT status and reasons for each crop.
- [x] **No regression on good crops**: Full pipeline produces 38-41 crops from 29 pages; all previously-good pages remain good.
- [x] **Integrated into Onward recipe**: Validation loop runs within `crop_illustrations_guided_v1`, configured via `rescue_validate_crops: true` in recipe.
- ~~**promptfoo eval completed**~~: Requirement struck — Story 125 eval already validated Gemini 3 Pro as winning model; text-density scoring deferred as unnecessary.

## Tasks
- [x] Add `contains_text` and `content_type` fields to VLM response schema in `_BBOX_PROMPT`. — Added `image_description`, `contains_text`, `text_reason`, `source_issues` to detector schema. `_copy_detector_meta()` propagates through all box transforms.
- ~~Add local OCR text density check after cropping~~ — Struck; VLM-based validator (Gemini 2.5 Flash) is more accurate and contextually aware than Tesseract density heuristics.
- [x] Implement retry logic: auto-retry when `crop_count != expected_count` with stronger VLM instructions, re-normalize, re-validate, pick better result.
- [x] Add `--rescue-text-validation` flag — Added `--rescue-validate-crops`, `--rescue-validate-model`, `--rescue-validate-max-tokens` CLI flags.
- [x] Improve OCR image detection — Switched from GPT-5.1 to Gemini 3 Pro which reliably detects all photos.
- ~~**promptfoo eval**~~ — Struck; Story 125 eval already validated Gemini 3 Pro.
- [x] Test on Onward pages — Verified page-012 (seal passes), page-072/086 (heads visible after X-overlap fix), page-122/126 (correct counts after auto-retry), page-001 (cover page captured).
- [x] Wire winning model + validation loop into Onward recipe — `rescue_validate_crops: true`, `rescue_validate_model: gemini-2.5-flash` in recipe.
- [x] Update story-026 work log with results.

## Open Questions
- Should the independent layout-model image detection (Layer 1 option 2) be a separate module or folded into the crop module?
- What text density threshold triggers rejection? (Tesseract word count > N? Text area ratio > X%?)
- Should the retry send the cropped image to Gemini, or just describe the problem in text?
- Is one retry sufficient, or should we allow 2 retries with escalating prompts?

## Work Log

### 2026-02-19 — Full Implementation

**Implemented (in `crop_illustrations_guided_v1/main.py`):**

1. **Cover page hardcode** (`cover_pages` param): Full-page capture with whitespace auto-crop for page 1. `_autocrop_whitespace()` helper using numpy threshold + bounding box. `detection_method: "cover_page"` in manifest.

2. **Enriched detector schema**: `_BBOX_PROMPT` now requests `image_description`, `contains_text`, `text_reason`, `source_issues` per image. `_copy_detector_meta()` propagates metadata through all box transforms (normalize, refine, trim, caption, split, dedupe).

3. **Context-aware validator**: `_build_validate_prompt(box)` injects detector metadata into the validation prompt. Validator knows when text is intentional (seals, signatures) and when source photos have pre-existing defects (cut-off heads). Reduces false rejections.

4. **Auto-retry on count mismatch**: After validation, if `len(crops) != expected_count`, re-runs VLM with stronger instructions ("This page contains exactly N distinct images"), re-normalizes, re-applies layout trim + caption + refine, re-validates, picks whichever result is closer to expected count.

5. **`--only-pages` for targeted runs**: Process specific pages only, clean old crops, merge into existing manifest. ~80% cost/time savings for iteration.

6. **X-overlap fix**: `_trim_box_by_layout_text` and `_split_box_by_layout_text_band` now check X-axis overlap before applying vertical trims. Prevents text in adjacent columns from incorrectly trimming photos.

7. **Manifest enrichment**: `image_description`, `contains_text`, `source_issues` included in output manifest for downstream alt-text generation.

**Bug fixes:**
- Pages 72/86 heads cut off — root cause was missing X-overlap check in `_trim_box_by_layout_text`. Text in right column (x=2600-4596) triggered vertical trim on left-column photo (x=490-2504). Fixed.
- Pages 122/126 missing crops — VLM non-determinism caused wider boxes that validator correctly rejected. Fixed by auto-retry on count mismatch.

**Results:**
- Full pipeline: 38 crops from 29 pages + targeted re-run of pages 122/126 = 41 total crops
- 100% page coverage (29/29 image pages produced crops)
- Validator correctly rejected 4/40 bad crops in initial eval
- All problem pages verified: page-001 (cover), page-012 (seal passes), page-072/086 (heads visible), page-122/126 (correct counts)

**Requirements struck by user:**
- "promptfoo eval with text-density scoring" — Story 125 eval sufficient
- "Local OCR text density check" — VLM validator more accurate than Tesseract heuristics
