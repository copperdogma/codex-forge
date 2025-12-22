# Story: Choice Parsing Enhancements (HTML + Linking)

**Status**: To Do  
**Created**: 2025-12-22  
**Priority**: High  
**Parent Story**: story-081 (GPT‑5.1 AI‑First OCR Pipeline)

---

## Goal

Improve choice parsing by recognizing choice options earlier in the HTML pipeline and/or adding explicit link markup (e.g., `<a>` tags) to choice targets.

---

## Motivation

Choices are currently extracted from text patterns later in the pipeline. Better structural tagging could reduce errors, improve downstream repair accuracy, and make the final HTML more semantically useful.

---

## Success Criteria

- [ ] **Choice detection**: Identify choice options in HTML pages or portions with high recall.
- [ ] **Markup**: Add clear semantic markers for choices (e.g., `<a data-target="123">` or `<choice target="123">`).
- [ ] **Non-destructive**: Preserve original HTML and add tags without altering content.
- [ ] **Integration**: Downstream choice extraction can use tags if present, falling back to regex if not.
- [ ] **Validation**: Improved choice coverage metrics and fewer orphaned sections.

---

## Tasks

- [ ] Review current choice extraction and repair steps for integration points.
- [ ] Define a minimal, generic HTML choice tag schema (avoid FF-specific assumptions).
- [ ] Implement a choice-tagging pass (HTML in → HTML out) with provenance.
- [ ] Update choice extraction to prefer tags when present.
- [ ] Validate on a 20‑page slice; compare orphan counts and choice recall.
- [ ] Document results and examples in work log.

---

## Work Log

### 20251222-2129 — Story created
- **Result:** Success.
- **Notes:** New story for richer choice parsing/markup (early tagging or link injection).
- **Next:** Review current choice extraction path and design choice tag schema.
