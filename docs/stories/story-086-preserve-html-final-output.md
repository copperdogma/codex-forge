# Story: Preserve HTML Through Final Gamebook

**Status**: Done  
**Created**: 2025-12-22  
**Priority**: High  
**Parent Story**: story-081 (GPT‑5.1 AI‑First OCR Pipeline)

---

## Goal

Ensure HTML structure survives all pipeline stages and is present in the final gameplay output artifact(s). Plain-text-only outputs are insufficient for layout-sensitive content.

---

## Motivation

Current final artifacts appear to lose HTML, leaving only plain text. This destroys layout information (tables, lists, stat blocks, headings) that is crucial for game engine use and downstream conversions.

---

## Success Criteria

- [x] **HTML preserved end-to-end**: raw HTML retained through portionization and extraction stages.
- [x] **Final artifact includes HTML**: `gamebook.json` (or a parallel artifact) contains HTML per section.
- [x] **No data loss**: Plain text can be derived from HTML; HTML remains source of truth.
- [x] **Validation**: Spot-check final output shows preserved tables, headings, lists, and stat blocks.
- [x] **Text optional**: Plain-text fields can be derived from HTML (dropping text earlier is allowed if HTML is preserved).
- [x] **BACKGROUND included**: The unnumbered BACKGROUND section is included in gameplay with an implicit link to section 1.

---

## Tasks

- [x] Trace where HTML is dropped today (module by module).
- [x] Add fields and schema updates needed to keep HTML alongside text.
- [x] Update build/export module to include HTML in final output.
- [x] Verify with a sample run (5–10 sections with tables/lists).
- [x] Document results and impact in the work log.
- [x] Decide whether to drop `text` earlier in the pipeline (HTML as sole source of truth) and update downstream consumers if needed.
- [x] Trace and fix missing BACKGROUND section (unnumbered) and add implicit navigation to section 1.

---

## Work Log

### 20251222-1545 — Story created
- **Result:** Success.
- **Notes:** New requirement to retain HTML all the way to final gamebook outputs.
- **Next:** Trace where HTML is dropped and add preservation paths.

### 20251222-1625 — Traced HTML drop and added final HTML output fields
- **Result:** Partial success.
- **Notes:** HTML is preserved through `portionize_html_extract_v1` as `raw_html` but was dropped in `build_ff_engine_v1` and `build_ff_engine_with_issues_v1`. Added `html` to section outputs (including stub sections) in both build modules.
- **Next:** Run a small sample build to confirm `gamebook.json` includes `html` per section and spot-check tables/headings.

### 20251222-1705 — Verified HTML in final gamebook output (sample)
- **Result:** Success.
- **Notes:** Rebuilt gamebook using updated build module: `output/runs/ff-ai-ocr-gpt51-full-20251221a/gamebook_with_html.json`. Sample sections (7, 15, 16, 20, 61, 80, 100) now include `html` with expected structure (tables/headings present).
- **Next:** Decide whether to drop plain-text fields earlier or keep both for now.

### 20251222-1740 — Dropped raw text reliance; derive text from HTML
- **Result:** Success.
- **Notes:** Updated choice extraction and repair to use HTML-derived text; `portionize_html_extract_v1` now drops `raw_text` by default. Build modules now derive `text` from HTML when raw text is absent.
- **Next:** Verify pipeline runs still pass with `raw_text` omitted; trace BACKGROUND inclusion gap.

### 20251222-1815 — BACKGROUND section now included with implicit link to 1
- **Result:** Success.
- **Notes:** Added BACKGROUND detection in `detect_boundaries_html_v1` and updated portionize/build stages to handle non-numeric section IDs. Verified with `/tmp/gamebook_with_background.json`: startSection=`background`, HTML present, and implicit navigation to section 1.
- **Next:** Re-run the full pipeline when convenient to propagate BACKGROUND into the main gamebook artifact.

### 20251222-1900 — Rebuilt downstream outputs without OCR
- **Result:** Success.
- **Notes:** Rebuilt from existing HTML blocks (no OCR) into `/tmp/cf-ff-ai-ocr-gpt51-rebuild-20251222/gamebook.json`. HTML is present in sections, `startSection` is `background`. Total sections = 401 (includes `background` plus 1–400).
- **Next:** Decide whether to keep 401 sections (background + 400 numeric) or treat background as separate metadata.

### 20251222-2235 — Rebuilt with HTML blocks and wired recipe background flags
- **Result:** Success.
- **Notes:** Rebuilt from `/tmp/cf-ff-ai-ocr-gpt51-rebuild-20251222/page_blocks.jsonl` (HTML blocks) through boundaries, portions, choices, and build. `gamebook.json` now includes `html` per section; `metadata.startSection` is `background`. Updated `configs/recipes/recipe-ff-ai-ocr-gpt51.yaml` to use `html_to_blocks_v1` and enable `include_background` / `drop_raw_text`.
- **Next:** Consider adding `html_to_blocks_v1` output validation to smoke tests and ensure recipe wiring matches the rebuild steps.

### 20251222-2305 — Tightened smoke validation for HTML + BACKGROUND
- **Result:** Success.
- **Notes:** Updated `modules/validate/validate_gamebook_smoke_v1/main.py` to require `metadata.startSection`, enforce `background` start when present, allow `background` as a non-numeric section id, and treat empty gameplay content as missing only if both text and HTML are absent.
- **Next:** Re-run `validate_gamebook_smoke_v1` on latest rebuilt gamebook to confirm it passes.

### 20251222-2350 — Smoke run completed on main recipe
- **Result:** Success (warnings expected for stubs).
- **Notes:** Ran `configs/recipes/recipe-ff-ai-ocr-gpt51.yaml` with `configs/settings.ff-ai-ocr-gpt51-smoke-20.yaml` into `/tmp/cf-ff-ai-ocr-gpt51-smoke-20`. Pipeline completed with `validate_gamebook_smoke_v1` warnings only for stub/unresolved-missing sections. See `/tmp/cf-ff-ai-ocr-gpt51-smoke-20/13_validate_gamebook_smoke_v1/validation_report.json`.
- **Next:** Consider adding a smoke assertion for `metadata.startSection == background` and HTML presence in `gamebook.json`.

### 20251223-0015 — Fixed HTML repair loop include_background param
- **Result:** Success.
- **Notes:** Added `include_background` support to `detect_boundaries_html_loop_v1` (arg + module.yaml). Re-ran smoke; HTML repair loop now proceeds without missing-arg failure.
- **Next:** Keep smoke coverage for this path to avoid regressions.

### 20251223-0105 — Dropped section text + provenance text in final gamebook
- **Result:** Success.
- **Notes:** Added `emit_text` / `emit_provenance_text` flags to `build_ff_engine_v1` and `build_ff_engine_with_issues_v1`. Rebuilt final artifact into `output/runs/ff-ai-ocr-gpt51-full-20251222b/gamebook.json` with `--drop-text --drop-provenance-text`. Verified sections contain HTML but no `text`, and provenance omits `raw_text`/`clean_text`.
- **Next:** Consider adding recipe defaults and smoke assertions to keep text scrubbed in future full runs.

### 20251223-0115 — Set canonical run ID to 20251222b
- **Result:** Success.
- **Notes:** Canonical output is now `ff-ai-ocr-gpt51-full-20251222b` (text/provenance scrubbed). Prior run `ff-ai-ocr-gpt51-full-20251222` remains for reference.
- **Next:** Use `ff-ai-ocr-gpt51-full-20251222b` for downstream QA or game-ready validation.
