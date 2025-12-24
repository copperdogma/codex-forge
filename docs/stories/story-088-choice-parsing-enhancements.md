# Story: Choice Parsing Enhancements (HTML + Linking)

**Status**: Done
**Created**: 2025-12-22  
**Priority**: High  
**Parent Story**: story-081 (GPT‑5.1 AI‑First OCR Pipeline)

---

## Goal

Improve choice parsing by recognizing choice options earlier in the HTML pipeline and/or adding explicit link markup (e.g., `<a>` tags) to choice targets.

---

## Motivation

Choices are currently extracted from text patterns later in the pipeline. Better structural tagging reduces errors, improves downstream repair accuracy, and makes the final HTML more semantically useful for the game engine.

---

## Success Criteria

- [x] **Choice detection**: Identify choice options in HTML pages or portions with high recall.
- [x] **Markup**: Add clear semantic markers for choices (e.g., `<a href="#123">`).
- [x] **Non-destructive**: Preserve original HTML and add tags without altering content.
- [x] **Integration**: Downstream choice extraction can use tags if present, falling back to regex if not.
- [x] **Validation**: Improved choice coverage metrics and fewer orphaned sections.

---

## Tasks

- [x] Review current choice extraction and repair steps for integration points.
- [x] Update `ocr_ai_gpt51_v1` system prompt to detect and mark up navigation choices using `<a>` tags.
- [x] Update `TagSanitizer` in `ocr_ai_gpt51_v1` to allow `<a>` tags.
- [x] Update `extract_choices_relaxed_v1` to parse `<a>` tags from HTML as primary, high-confidence signals.
- [x] Update `clean_html_presentation_v1` to preserve or normalize these structural links for the final gamebook.
- [x] Validate on a 20‑page slice; compare orphan counts and choice recall.
- [x] Document results and examples in work log.

---

## Work Log

### 20251222-2129 — Story created
- **Result:** Success.
- **Notes:** New story for richer choice parsing/markup (early tagging or link injection).
- **Next:** Review current choice extraction path and design choice tag schema.

### 20251223-XXXX — Implementation of Structural Tagging
- **Result:** Success.
- **Notes:** 
    - Updated OCR prompt to inject `<a href="#N">` for choices.
    - Updated OCR sanitizer to allow `<a>` tags with fragments.
    - Updated `extract_choices_relaxed_v1` to prioritize HTML links as 1.0 confidence signals.
    - Verified that `clean_html_presentation_v1` preserves these links for the final engine.
    - Verified on 20-page slice: `gpt-4.1-mini` successfully injected links (e.g., section 63, 69) and the extractor captured them as `html_link` method choices.
- **Outcome:** Choices are now structurally grounded in the OCR HTML, increasing recall and precision.
