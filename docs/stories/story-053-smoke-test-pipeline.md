# Story: Pipeline Smoke Test (Static Sample, No External Calls)

**Status**: Open  
**Created**: 2025-12-02  

## Goal
Add a repeatable smoke test that runs the full pipeline on a static image sample set, with all external API calls mocked, to catch integration breakages early.

## Success Criteria
- [x] Static sample images (user-provided) checked into testdata or referenced path.
- [x] Smoke test script/target runs pipeline stages end-to-end (intake → headers → loops → build → validate) with mocked APIs (OCR/LLM).
- [x] Test asserts pipeline completes without errors and produces expected stub artifacts.
- [x] Document how to run the smoke locally and in CI.

## Tasks
- [x] Select a micro input set (≤3 pages) that is public domain or US federal work; document license/provenance in the story.
- [x] Add the static sample image/PDF path under `testdata/` (or referenced path) plus a minimal pagelines fixture.
- [x] Mock external API calls (OCR/LLM) for the smoke path; ensure deterministic responses and stubbed artifacts.
- [x] Create a smoke test target (Makefile or script) that invokes the pipeline with mocks and fails on stage errors.
- [x] Integrate into CI (or document manual invocation) and add pass/fail reporting.

## Candidate Sample Inputs
- NASA fact sheet or mission one-pager (public domain, clear diagrams/text, usually 1–2 pages).
- USDA/FEMA preparedness brochure excerpt (public domain; simple headings + paragraphs).
- Digitized public-domain poem/sonnet facsimile (e.g., Shakespeare quarto page) limited to a 1–2 page scan.

## Work Log
...
### 20251223-2045 — Finalized end-to-end smoke test
- **Result:** Success. Implemented `Makefile` with `make smoke-ff` target.
- **Notes:** Created `recipe-ff-smoke.yaml` and `text_to_html_blocks_v1` adapter to convert old `clean_page_v1` stubs to the modern `page_html_blocks_v1` format. Updated `portionize_html_extract_v1` and `ending_guard_v1` to support custom IDs and `skip_ai` flags.
- **Next:** Integrate `make smoke` into local/remote CI workflow.
