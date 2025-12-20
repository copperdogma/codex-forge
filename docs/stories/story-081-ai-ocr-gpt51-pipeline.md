# Story: GPT‑5.1 AI‑First OCR Pipeline (HTML‑First)

**Status**: To Do  
**Created**: 2025-12-20  
**Priority**: High

---

## Goal

Build a new **AI‑first OCR pipeline** that uses **GPT‑5.1** to produce structured **HTML per page**, then runs HTML‑aware portionization to reach the same downstream outputs (sections/choices/gamebook) while **leaving all existing modules untouched**.

---

## Non‑Negotiables

- **Do not modify any existing modules.**  
  Create **new modules/recipes** only, by copying and adapting old pipeline components.
- **Reuse the existing PDF→images→split module as‑is** if no code changes are required.
- **HTML is the canonical OCR output** (per‑page HTML).

---

## Agreed Plan (Detailed)

### Stage 0 — Page Split (reuse existing module)
Use the current split logic to generate `page-###L/R` images. No changes.

### Stage 1 — AI OCR (new module)
**`ocr_ai_gpt51_v1`**
- Input: split page images
- Output: **per‑page HTML** in the **gold HTML schema** (same as OCR bench)
- Model: `gpt-5.1`
- Must emit **verbatim text** + structural tags (`<h2>`, `<p>`, `<dl>`, `<table>`, etc.)

### Stage 2 — HTML → Blocks (new module)
**`html_to_blocks_v1`**
- Parse per‑page HTML into a block stream (tag‑aware, no guessing)
- Block fields: `page_id`, `block_type` (`h1/h2/p/dl/table/img`), `text`, `order`
- Purpose: provide deterministic, typed inputs for segmentation/boundary detection

### Stage 3 — Coarse Segment (new module)
**`coarse_segment_html_v1`**
- Input: HTML blocks
- Output: frontmatter/gameplay/endmatter segments
- Rules: use headings + patterns, not OCR heuristics

### Stage 4 — Boundary Detection (new module)
**`detect_boundaries_html_v1`**
- Input: HTML blocks + coarse segments
- Output: section boundaries (IDs, start/end positions)
- Primary signal: `<h2>` section headers

### Stage 5 — Portionize / Extract (new module)
**`portionize_html_extract_v1`**
- Input: HTML blocks + section boundaries
- Output: portion JSONL with clean text
- Should preserve HTML semantics for later choice extraction

### Stage 6 — Choices / Build / Validate (reuse existing modules)
Reuse existing downstream modules (choices/build/validate), with adapters if needed for HTML text.

---

## Key Architecture Decisions

- **Per‑page HTML is primary.**  
  If needed, create **derived merged documents** (frontmatter/gameplay/endmatter) without discarding page‑level provenance.
- **No content‑type guessers.**  
  HTML tags already encode structure; avoid redundant “header detection” heuristics.
- **New modules only.**  
  If a current module is needed, copy it to a new module ID and adapt.

---

## Success Criteria

- [ ] New AI‑first recipe runs end‑to‑end without touching existing OCR modules.
- [ ] HTML OCR output follows the gold HTML schema.
- [ ] Coarse segmentation yields correct frontmatter/gameplay/endmatter boundaries.
- [ ] Section boundaries produced from `<h2>` headers achieve full coverage (1–400).
- [ ] Choices and final `gamebook.json` pass validation on a 20‑page test run.

---

## Tasks

- [ ] **Inventory current recipe** and identify exact split module to reuse unchanged.
- [ ] **Create new recipe** `recipe-ff-ai-ocr-gpt51.yaml` using the new modules.
- [ ] **Implement `ocr_ai_gpt51_v1`** (HTML output per page).
- [ ] **Implement `html_to_blocks_v1`** (HTML → block stream).
- [ ] **Implement `coarse_segment_html_v1`** (frontmatter/gameplay/endmatter).
- [ ] **Implement `detect_boundaries_html_v1`** (section IDs from `<h2>`).
- [ ] **Implement `portionize_html_extract_v1`** (sections from HTML blocks).
- [ ] **Adapter (if needed)** for downstream choice extraction/build.
- [ ] **Run 20‑page test** and inspect artifacts manually.
- [ ] **Document results** + update work log with evidence.

---

## Work Log

### 20251220-1545 — Story created
- **Result:** Success; new story created for GPT‑5.1 pipeline redesign.
- **Notes:** Plan finalized for HTML‑first pipeline with new modules only.
- **Next:** Inventory current recipe and draft the new GPT‑5.1 recipe.
