# Story: Onward to the Unknown — Arthur L'Heureux pilot

**Status**: To Do

---
**Depends On**: story-009 (layout‑preserving extractor / table capture capability)

## Acceptance Criteria
- Images under `input/onward-to-the-unknown-images/Image027.jpg`–`Image036.jpg` are treated as the authoritative source for Arthur L'Heureux and processed end-to-end through the modular pipeline.
- Parser emits two distinct section types for this branch: (1) narrative story text, (2) genealogy table content preserved with row/column/headers intact.
- Genealogy table output format is defined and documented (JSON schema or HTML fragment) and can represent the odd layout faithfully; validator or schema added if JSON.
- A recipe (or recipe fragment) exists to run just this branch as a testbed, and produces artifacts under `output/runs/<run_id>/` without touching other inputs.
- Sample artifacts for both subsections are produced and validated (at least spot-checked) against the scans; known parsing pitfalls and open issues are logged.

## Tasks
- [ ] Define desired outputs for genealogy tables (HTML fragment vs structured JSON) and add schema/validator if JSON.
- [ ] Design sectioning rules for the Arthur L'Heureux pages: narrative vs table boundaries, page ranges, and any OCR hints.
- [ ] Implement or configure modules to parse the genealogy table accurately (layout-aware OCR/table capture) and narrative text separately.
- [ ] Add a focused recipe (DAG) to run only the Arthur L'Heureux pages using the scanned images as inputs.
- [ ] Run the recipe, produce artifacts, and validate outputs against scans; record issues/edge cases.
- [ ] Document usage (commands, expected outputs) and update AGENTS safe commands if needed.

## Notes
- Book: *Onward to the Unknown* (family history). Scanned images are authoritative over the PDF.
- Focus branch: Arthur L'Heureux, pages `Image027.jpg`–`Image036.jpg` in `input/onward-to-the-unknown-images/`.
- Two subsections must be handled differently: (1) narrative story; (2) genealogy table with unusual layout—needs faithful capture (may favor HTML to preserve headers/rows/columns).
- Treat this branch as both a functional deliverable and a testbed for broader ingestion.

## Work Log
### 20251126-1200 — Story intake
- **Result:** Captured user requirements for Arthur L'Heureux pilot. No code changes yet.
- **Notes:** Scans preferred over PDF; two subsection types (narrative vs genealogy table) need separate handling. Genealogy table format undecided; must preserve layout accurately, possibly as HTML.
- **Next:** Lock the target output format for genealogy tables and define sectioning/recipe plan before implementing modules.
### 20251212-1335 — Added explicit dependency
- **Result:** Success.
- **Notes:** This pilot requires layout/table preservation work tracked in Story 009; added dependency for sequencing clarity.
- **Next:** Implement Story 009, then return here.
