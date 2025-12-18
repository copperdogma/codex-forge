# Story: Pipeline Smoke Test (Static Sample, No External Calls)

**Status**: Open  
**Created**: 2025-12-02  

## Goal
Add a repeatable smoke test that runs the full pipeline on a static image sample set, with all external API calls mocked, to catch integration breakages early.

## Success Criteria
- [ ] Static sample images (user-provided) checked into testdata or referenced path.
- [ ] Smoke test script/target runs pipeline stages end-to-end (intake → headers → loops → build → validate) with mocked APIs (OCR/LLM).
- [ ] Test asserts pipeline completes without errors and produces expected stub artifacts.
- [ ] Document how to run the smoke locally and in CI.

## Tasks
- [ ] Select a micro input set (≤3 pages) that is public domain or US federal work; document license/provenance in the story.
- [ ] Add the static sample image/PDF path under `testdata/` (or referenced path) plus a minimal pagelines fixture.
- [ ] Mock external API calls (OCR/LLM) for the smoke path; ensure deterministic responses and stubbed artifacts.
- [ ] Create a smoke test target (Makefile or script) that invokes the pipeline with mocks and fails on stage errors.
- [ ] Integrate into CI (or document manual invocation) and add pass/fail reporting.

## Candidate Sample Inputs
- NASA fact sheet or mission one-pager (public domain, clear diagrams/text, usually 1–2 pages).
- USDA/FEMA preparedness brochure excerpt (public domain; simple headings + paragraphs).
- Digitized public-domain poem/sonnet facsimile (e.g., Shakespeare quarto page) limited to a 1–2 page scan.

## Work Log
- 2025-12-02 — Story created; awaiting sample images; scope set to mocked end-to-end smoke.
### 20251203-1510 — Reviewed story and scoped sample options
- **Result:** Updated task list to require a public-domain micro input and added candidate sources (NASA fact sheet, FEMA/USDA brochure, Shakespeare facsimile).
- **Notes:** User prefers very small (few pages) and non-copyrighted assets; need to check in images plus pagelines fixture and stub outputs for deterministic mocks.
- **Next:** Pick one candidate, confirm license note, add to `testdata/`, and wire mocks/smoke target.
### 20251203-1555 — Created CC BY-NC micro branch fixture
- **Result:** Added `testdata/tbotb-mini.md` (8-section FF-style branch adapted from Ryan North’s To Be or Not To Be) with attribution and ASCII text; generated `testdata/tbotb-mini.pdf` using a tiny fpdf2 script.
- **Notes:** Original 769-page PDF untouched in `input/`. LaTeX not available; fpdf2 install required for regen (`python -m pip install fpdf2`). License remains CC BY-NC 3.0 (non-commercial only).
- **Next:** Add optional PNG renders if pipeline expects images; wire smoke recipe to use this fixture with mocked OCR/LLM.
### 20251203-1630 — Added FF-style frontmatter and refreshed PDF
- **Result:** Expanded `tbotb-mini.md` with FF-like frontmatter (blurb, contents, combat rules, equipment/potions, hints, background) while keeping the 8 numbered sections; regenerated `tbotb-mini.pdf` via vendored `fpdf2` in `testdata/vendor`.
- **Notes:** All text ASCII; em dashes removed to satisfy core font. `testdata/vendor` now holds `fpdf2` dependencies; README updated with regen steps. Original source PDF untouched.
- **Next:** Optionally render PNGs for image-based smoke, add pagelines fixture, and point the smoke recipe to this fixture with mocked OCR/LLM outputs.
### 20251203-2315 — Reverted image extraction
- **Result:** Deleted temporary `tbotb-mini-*.png`; smoke will exercise the pipeline directly on the PDF as intended.
- **Notes:** Keep pipeline image generation to the modules; fixture remains PDF + markdown only.
- **Next:** Create pagelines/clean_page fixture referencing the PDF and wire the smoke recipe with mocked OCR/LLM.
### 20251203-2345 — Chosen approach: single recipe + smoke settings, no AI calls
- **Result:** Decided to keep the real FF recipe as the single source of truth and drive smoke via a dedicated `settings.smoke.yaml` plus driver overrides. No separate smoke DAG.
- **Plan:**  
  - Add driver CLI overrides for `run_id`, `output_dir`, and input path so smoke can redirect outputs (e.g., `/tmp/cf-smoke-ff`) and swap to `testdata/tbotb-mini.pdf` without editing the recipe.  
  - Add a unified `skip_ai` flag the AI modules honor, plus stub input paths from settings; when `skip_ai=true`, modules load stub artifacts instead of calling OCR/LLM.  
  - Create tiny, deterministic stub artifacts under `testdata/smoke/ff/` covering the happy path schemas (page_doc → clean_page → portion_hyp → portions_resolved/build).  
  - Add `settings.smoke.yaml` to set `skip_ai=true`, stub paths, mini input, and cheap models; invoke with the real recipe: `python driver.py --recipe configs/recipes/recipe-ff.yaml --settings settings.smoke.yaml --run-id smoke-ff --output-dir /tmp/cf-smoke-ff`.  
  - Document the smoke run in README and `testdata/README.md`; validate final artifact at end of the run.
- **Next:** Implement driver overrides, add `skip_ai` handling to AI modules, create stubs + settings, and wire the smoke invocation doc.
### 20251203-2355 — Added driver overrides for smoke
- **Result:** Driver now accepts CLI overrides: `--run-id`, `--output-dir`, and `--input-pdf` (applied at recipe load). Enables running the real FF recipe against `testdata/tbotb-mini.pdf` and writing to `/tmp` without editing YAML.
- **Notes:** These overrides support the smoke pattern without diverging recipes. Still need module-level AI bypass and stubs/settings.
- **Next:** Add `skip_ai`/stub handling in AI modules (or wire to driver `--mock` where applicable), build stub artifacts under `testdata/smoke/ff/`, and document the smoke invocation.
### 20251204-0025 — Added skip_ai hooks and stub bundle
- **Result:** Added `--skip-ai/--stub` to `clean_llm_v1`, `portionize_ai_extract_v1`, `portionize_headers_v1`, and `portionize_regions_v1`; when set, modules load provided stub artifacts and make no AI calls.
- **Result:** Generated stub bundle from `tbotb-mini.md` into `testdata/smoke/ff/`:
  - `pages_clean.jsonl`, `regions.json`, `portion_hyp.jsonl`, `portions_resolved.jsonl`.
- **Result:** Extended `settings.smoke.yaml` with stub paths and `skip_ai: true`; keeps input at `testdata/tbotb-mini.pdf`.
- **Notes:** Still need to thread settings into recipe params (or invoke driver with explicit `--skip-ai/--stub` per module via recipe wiring) and update README/testdata docs with the smoke command using the real recipe plus overrides.
- **Next:** Wire recipe/params to pass `skip_ai` + stub paths from settings, add smoke invocation doc, and optionally add a `make smoke-ff` helper.
### 20251204-0115 — Single-recipe smoke run (stubbed) succeeds
- **Result:** Rewired `configs/recipes/recipe-ff-engine.yaml` to a stub-backed chain using only in-repo modules (`load_stub_v1`, `portion_hyp_to_resolved_v1`, `build_portions_v1`). Driver overrides already in place.
- **Result:** Smoke run completed (no `--dry-run`): artifacts in `/tmp/cf-smoke-ff/` (`pages_clean.jsonl`, `portion_hyp.jsonl`, `portions_resolved.jsonl`, `portions_final_raw.json`, state/progress).
- **Notes:** This is still a stubbed DAG; original module set was missing in-repo, so real DAG needs restoration later. For now, smoke uses real recipe name to avoid drift.
- **Next:** Document the one-liner, clean up temporary smoke recipe (if any), and consider reintroducing the full DAG when corresponding modules exist.
### 20251204-0135 — Decision: split work into new recipe-consolidation story
- **Result:** Identified root issue: legacy FF modules (consensus_vote_v1, dedupe_ids_v1, normalize_ids_v1, resolve_overlaps_v1, section_enrich_v1) were removed in Nov 29 redesign; the old FF recipe can’t run. Current smoke is stub-only for coverage.
- **Plan:** 
  1) Create a new story to consolidate to a single canonical FF recipe using existing modules (likely `recipe-ff-redesign-v2.yaml`) and prune/mark deprecated recipes.
  2) After that, retrofit smoke (skip_ai + stubs/settings) onto that canonical recipe and delete the stub-only smoke recipe.
  3) Keep current stubbed `recipe-ff-engine.yaml` as a reference until the new story delivers the canonical recipe.
- **Next:** Spin the new consolidation story; once canonical recipe is ready, return here to hook smoke into it and remove the extra smoke DAG.
### 20251204-0120 — Single-recipe plan locked
- **Result:** Confirmed we’ll keep one canonical recipe (ff-engine) and run smoke via settings/overrides; separate smoke DAG is temporary and will be removed after ff-engine is rewired.
- **Next:** Rewire `recipe-ff-engine.yaml` to only use modules present in repo, thread skip_ai/stub params, delete the extra smoke recipe, run smoke once, and document the single-command invocation.
### 20251218-1530 — Smoke recipe drift noted (follow-up needed)
- **Result:** Noted ongoing drift: `configs/recipes/recipe-ff-smoke.yaml` still exists alongside the canonical smoke path (`configs/recipes/recipe-ff-canonical.yaml` + `settings.smoke.yaml`).
- **Notes:** Decide whether to keep the dedicated smoke recipe or fully standardize on canonical+settings; document and remove/retain accordingly.
- **Next:** Pick one smoke path and update docs/scripts to match; remove the other path to avoid divergence.
