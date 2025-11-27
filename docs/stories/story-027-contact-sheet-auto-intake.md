# Story: Contact-sheet intake for automatic book type planning

**Status**: Done

---

## Acceptance Criteria
- Contact-sheet generation pipeline downsamples all input pages/images (e.g., to ~200px wide), numbers them, and packs them into grids/strips with a manifest mapping sheet coordinates to original filenames.
- LLM “overview” prompt consumes the contact sheets only (no web lookup), classifies book type(s) (novel/CYOA/genealogy/mixed/etc.), and lists candidate pages that need zooms for finer inspection.
- Optional second-pass “zoom” step fetches higher-res crops for requested pages and refines the plan (sectioning approach + recommended recipe or module set).
- System produces a human-readable proposed plan (book type, sectioning strategy, artifacts to extract) and requires user confirmation before running any recipe.
- Output artifacts (contact sheets, manifests, plan JSON) are written under `output/runs/<run_id>/` without touching existing inputs/outputs.
- The flow is piloted on `input/onward-to-the-unknown-images/` and handles late-appearing content (e.g., appendices/tables) without relying on first-N pages.

## Tasks
- [x] Implement contact-sheet builder: downscale pages/images, overlay page numbers, pack into grids, emit manifest linking sheet positions to originals (now supports PDF rendering).
- [x] Define manifest/plan JSON schemas (contact sheet manifest, plan, zoom requests) and add validator/tests.
- [x] Design LLM overview prompt and response schema to classify book type(s) and request zoom pages; support mixed-type outputs.
- [x] Add optional zoom fetcher to pull mid/high-res versions (or crops) for LLM-requested pages and run a refinement prompt.
- [x] Produce plan JSON + human-readable summary; require explicit user confirmation before executing a recipe.
- [x] Integrate with driver/recipes: map plan outcomes to existing recipes or minimal stubs; ensure no web lookup is used for this flow (intake recipe now ends at confirm).
- [x] Pilot on `input/onward-to-the-unknown-images/` (Arthur L'Heureux and beyond) and log findings/edge cases.
- [x] Document usage and safe commands; add validator/tests for manifest/plan formats.
- [x] Add module-gap analysis stage that compares detected content types (e.g., formulas, tables, images) against available modules; surface missing capabilities and propose build tasks in the plan.
- [x] Add interactive intake recipe with confirmation gate (no auto-dispatch) aligned with Story 011 planner UX.
- [x] Pilot on `input/onward-to-the-unknown-images/` (full book) for intake-only classification.

## Usage (intake recipe)
- Default generic run: `python driver.py --recipe configs/recipes/recipe-intake-contact-sheet.yaml --run-id intake-mybook --output-dir output/runs/intake-mybook --force`
- Override inputs: set `input.images_dir` in the recipe or pass `--input.images_dir <dir>` if supported by runner (else edit recipe before running).
- Artifacts land under `output/runs/<run_id>/` (contact sheets, manifest, overview/zoom/gap/final plan JSONL). No downstream dispatch is performed.
- Planner (Story 011) should read `overview_plan_final.jsonl`, chat with the user, then decide whether to run an existing recipe or propose new modules/recipes based on capability gaps.

## Safe commands & validation
- Validate manifest: `python validate_artifact.py --schema contact_sheet_manifest_v1 --file output/runs/<run_id>/build_contact_sheets.jsonl`
- Validate plan: `python validate_artifact.py --schema intake_plan_v1 --file output/runs/<run_id>/overview_plan_final.jsonl`
- Re-run intake with force: `python driver.py --recipe configs/recipes/recipe-intake-contact-sheet.yaml --run-id intake-<book> --output-dir output/runs/intake-<book> --force`

## Notes
- No web lookup; rely solely on local contact sheets and optional zooms.
- Goal: avoid missing late content (tables/appendices) and reduce cost by sampling the whole book at low resolution.
- Contact sheets must preserve ordering and page identifiers to enable targeted zoom requests.
- User confirmation is required before running the chosen recipe.

## Draft Design
- **Contact sheets**
  - Downscale each page/image to max width 200px (preserve aspect ratio); optional 2x retina toggle.
  - Overlay page/image id (e.g., source filename) in a corner; include sequence number.
  - Pack into grids (default 5x4). Emit multiple sheets if needed; deterministic naming: `sheet-001.jpg`, `sheet-002.jpg`, ...
  - Manifest (JSONL): one row per tile with fields `sheet_id`, `tile_index`, `source_image`, `display_number`, `sheet_path`, `tile_bbox` (optional pixel coords within sheet), `orig_size`.
- **Overview prompt/response**
  - Input: list of sheet images + manifest summary (counts, order). No OCR text by default.
  - Output schema (plan draft): `book_type` (enum: novel, cyoa, genealogy, textbook, mixed), `type_confidence`, `sections` (list of {label, page_spans, type}), `zoom_requests` (list of source_image IDs to inspect), `notes`, `risk_flags` (e.g., "tables present", "images heavy").
- **Zoom pass**
  - For each requested `source_image`, provide mid/high-res page (or crop) to LLM; refine `sections`, `risk_flags`, and `recommended_recipe`.
  - Allow limiting zoom count (budget cap) and stopping if confidence already high.
- **Plan artifact**
  - `plan.json` containing: `book_type`, `confidence`, `recommended_recipe` (path/name), `sectioning_strategy` (narrative/table/choice/table-of-contents etc.), `zoom_pages`, `assumptions`, `warnings`, and linkage to manifest (`sheets` array with filenames).
  - Human-readable summary emitted to stdout + saved as `plan.txt`.
- **Module-gap analysis**
  - Input: overview signals (e.g., presence of formulas, sheet music, tables, heavy images) + catalog of available modules.
  - Behavior: list required capabilities vs existing modules; mark gaps (e.g., no formula extractor). Plan should include `capability_gaps` with suggested new modules/tasks or fallback handling (skip, passthrough, HTML snapshot).
  - Output: enrich `intake_plan_v1` with `capability_gaps` and user-facing warnings; gate user confirmation on acknowledging gaps or selecting a fallback.
- **Interactive intake recipe (Story 011 alignment)**
  - Recipe `recipe-intake-contact-sheet.yaml`: build sheets → overview → gap analysis → (optional) zoom refine → emit plan → pause.
  - CLI asks: “Do you want me to lead you through converting a book?” and shows plan summary; user can edit choices (ignore gaps, change outputs) before dispatch.
  - On approval, driver branches to the recommended downstream recipe (novel/CYOA/genealogy, etc.) or user-selected override; on decline, it exits cleanly with artifacts preserved.
- **Validator targets**
  - `contact_sheet_manifest_v1` and `intake_plan_v1` schemas to be added to `schemas.py` + `validate_artifact.py`.

## Work Log
### 20251126-1415 — Story created
- **Result:** Drafted story for contact-sheet-based automatic intake and planning; no code changes yet.
- **Notes:** Focus on local assets only; pilot target is `input/onward-to-the-unknown-images/`.
- **Next:** Design contact-sheet builder spec (dimensions, grid layout, manifest format) and the overview prompt/response schema.
### 20251126-1430 — Checklist refinement
- **Result:** Added explicit task to define manifest/plan schemas and validators for contact sheets and plans.
- **Notes:** Tasks otherwise complete and actionable.
- **Next:** Draft spec for contact-sheet builder (dimensions, numbering, grid layout, file naming) and outline manifest/plan JSON fields.
### 20251126-1448 — Drafted design for sheets, manifest, plan
- **Result:** Added draft design covering sheet sizing/overlay, grid packing, manifest fields, overview/zoom prompts, and plan artifact shape (including validator targets).
- **Notes:** Still need to formalize schemas in code and prototype the contact-sheet builder; zoom budget/rules can be tuned later.
- **Next:** Implement manifest/plan schemas in `schemas.py` + `validate_artifact.py`, and spike a contact-sheet builder on `input/onward-to-the-unknown-images/` to test the spec.
### 20251126-1505 — Added schemas and validator hooks
- **Result:** Implemented `contact_sheet_manifest_v1` and `intake_plan_v1` models in `schemas.py`; added them to `validate_artifact.py` SCHEMA_MAP so CLI validation works.
- **Notes:** No fixtures/tests yet. Models include bbox validation, unique/tile fields, and plan fields (book_type enum, sections, zoom_requests, sheets, manifest_path, assumptions/warnings, confidence range).
- **Next:** Create sample manifests/plans from a contact-sheet spike and add tests; then wire the builder/prompt flow to produce these artifacts.
### 20251126-1525 — Schema smoke test
- **Result:** Instantiated sample `ContactSheetTile` and `IntakePlan` objects via a small Python smoke test (no files written); validation passed.
- **Notes:** Confirms enum/field constraints behave as expected; still need real artifacts and CLI validation.
- **Next:** Build a minimal contact-sheet generator to produce actual manifest/plan files from `input/onward-to-the-unknown-images/` and add tests for the new schemas.
### 20251126-1545 — Contact-sheet generator spike
- **Result:** Added `scripts/contact_sheet_builder.py`; generated 7 sheets (5x4 grid, 200px width) and a manifest for 127 pages from `input/onward-to-the-unknown-images/`. Validated manifest with `validate_artifact.py --schema contact_sheet_manifest_v1` (passes).
- **Notes:** Overlay uses simple black box with white numbering; manifest records tile bboxes and original sizes. Output placed in `/tmp/contact-sheets`. No ingestion of plan yet.
- **Next:** Integrate builder into a recipe/stage, add tests/fixtures, and implement the LLM overview/zoom flow to emit `intake_plan_v1` + `plan.txt` using the generated sheets.
### 20251126-1610 — Added module-gap requirement
- **Result:** Updated tasks/design to require a gap-analysis stage: compare detected content types (formulas, sheet music, heavy tables/images) against available modules, surface missing capabilities, and include `capability_gaps` + warnings in the plan.
- **Notes:** Plan confirmation should pause if gaps exist, offering options (skip, passthrough HTML, or build new module). Need a module registry view for the planner.
- **Next:** Extend `intake_plan_v1` schema with `capability_gaps` field and outline gap-check logic tied to module catalog; then implement in overview/zoom stage.
### 20251126-1630 — Captured interactive run/branching plan
- **Result:** Added task/design notes for an interactive intake recipe with a confirmation gate that branches to downstream recipes; tied UX to Story 011 planner flow.
- **Notes:** Plan artifacts (`plan.json`/`plan.txt`) will be shown to the user for edits/approval; gaps must be acknowledged or given a fallback before run continues.
- **Next:** Implement recipe scaffold with pause/confirm, stub gap-analysis module, and align prompts with Story 011 guidance.
### 20251126-1705 — Intake module + recipe scaffold and gap analyzer stub
- **Result:**
  - Added module `modules/intake/contact_sheet_builder_v1` (wraps contact sheet builder logic) with module.yaml.
  - Added module `modules/intake/gap_analyzer_v1` to enrich `intake_plan_v1` with `capability_gaps` from signals vs `modules/module_catalog.yaml`.
  - Added `modules/module_catalog.yaml` (initial capabilities map) and recipe `configs/recipes/recipe-intake-contact-sheet.yaml` (builder → gap analyzer, writes plan.json).
- **Notes:** Gap analyzer currently expects optional signals JSON; recommended recipe selection/confirmation gate not yet wired. No tests/fixtures yet.
- **Next:** Add overview/zoom LLM stage to produce signals/plan, wire confirmation gate, and create tests for builder/gap analyzer + recipe run.
### 20251126-1730 — Overview stub + recipe update + signals/gaps propagation
- **Result:**
  - Added `contact_sheet_overview_v1` module (stub) that summarizes manifest, tags `signals` (images), and writes a draft `intake_plan_v1`.
  - Updated intake recipe to run builder → overview → gap_analyzer (plan passthrough).
  - Extended schema `intake_plan_v1` with `signals` and `recommended_recipe`; gap analyzer now merges plan signals with optional signals file.
- **Notes:** Overview is placeholder (no LLM yet); gap analyzer still simple capability check against catalog. Confirmation gate and downstream branching still pending.
- **Next:** Implement real LLM prompt for overview/zoom, add confirmation stage/branching, and add tests/fixtures for the new modules and recipe.
### 20251126-1750 — Confirmation gate scaffold
- **Result:** Added `confirm_plan_v1` module (interactive gate) and appended it to the intake recipe after gap analysis. Plan must be approved (or auto_approve set) before downstream run.
- **Notes:** Still no LLM overview/zoom; confirmation gate currently copies plan through on approval or exits with code 2. Needs downstream branching hook.
- **Next:** Implement LLM overview/zoom, add branching to recommended recipe, and create tests/fixtures for builder/overview/gap/confirm chain.
### 20251126-1820 — Zoom refine + dispatch hint stubs and recipe run-path wired
- **Result:**
  - Added `zoom_refine_v1` (stub) to cap zoom_requests and set a heuristic `recommended_recipe`.
  - Added `dispatch_hint_v1` to write a downstream handoff JSON.
  - Updated intake recipe to builder → overview (stub) → zoom_refine (stub) → gap_analyzer → confirm_plan → dispatch_hint.
  - Schema: `intake_plan_v1` now includes `signals`; overview stub tags `images`; gap analyzer merges signals.
  - Smoke-tested modules on contact sheets in `/tmp`: plan flows through, gaps empty, dispatch hint emitted.
- **Notes:** Overview/zoom remain non-LLM stubs; recommended_recipe heuristic is placeholder. Still need true LLM prompts, branching execution, and tests/fixtures.
- **Next:** Replace overview/zoom with LLM implementation (signals/sections/zoom requests), add recipe branching hook to execute recommended recipe, and add automated tests for the intake chain.
### 20251126-1840 — Heuristic overview stub (no LLM yet)
- **Result:** Updated `contact_sheet_overview_v1` to a minimal heuristic (still non-LLM) instead of the earlier pure stub; sets book_type=mixed, signals=[images], low confidence.
- **Notes:** Does not analyze content; just ensures pipeline runs without failing. LLM vision prompt still needed.
- **Next:** Implement real LLM overview/zoom and downstream branching/tests.
### 20251126-1915 — LLM-ready overview wiring (prompt stub, params)
- **Result:** Upgraded `contact_sheet_overview_v1` to call a vision model (defaults: gpt-4.1-mini-vision), added params max_sheets/vision_detail, and structured a JSON-focused prompt for book_type/signals/zoom_requests. Recipe already routes through this stage.
- **Notes:** Still needs live run with model + zoom refinement prompt; zoom_refine remains heuristic. Tests and dispatcher branching still pending.
- **Next:** Add a real zoom prompt, wire dispatcher to execute recommended recipe, and add fixtures/tests for the intake chain.
### 20251126-1945 — Zoom prompt params + dispatcher stage added
- **Result:**
  - Extended `zoom_refine_v1` with model/vision_detail params and a basic vision prompt to refine book_type/signals/recommended_recipe (still lightweight; uses filenames, not fetched images yet).
  - Added `run_dispatch_v1` module and wired recipe to dispatch downstream via `dispatch_hint` (fallback recipe configurable).
  - Recipe now: builder → overview (LLM-ready) → zoom_refine (LLM-ready) → gap_analyzer → confirm_plan → dispatch_hint → run_dispatch.
- **Notes:** Zoom prompt still not using actual page crops; recommended_recipe mapping is simple; tests/fixtures still missing.
- **Next:** Add page-fetch/zoom images, improve recipe selection logic, and add automated tests for the chain.
### 20251126-2015 — Zoom image fetch + initial tests
- **Result:**
  - `zoom_refine_v1` now optionally loads source images for zoom_requests (vision prompt uses images when available) and exposes `source_images_dir` param; still falls back to text if missing.
  - Added minimal schema tests `modules/intake/tests/test_intake_chain.py` to assert schemas wired and validate sample manifest/plan rows.
- **Notes:** Recipe selection remains simple; dispatcher fallback is generic OCR. No end-to-end test yet.
- **Next:** Improve recipe mapping, add e2e harness, and enrich prompts with manifest display numbers/page order.
### 20251126-2100 — Mockable prompts, recipe_map, dry-run dispatch
- **Result:**
  - Added mock_output hooks to overview/zoom refine for offline tests; zoom refine accepts recipe_map param.
  - Added dry_run default to run_dispatch_v1 and recipe uses dry_run=true to avoid executing downstream pipelines in intake runs.
  - Tests now use fixtures and import harness; still minimal but passing (`pytest modules/intake/tests/test_intake_chain.py`).
- **Notes:** Real recipe mapping for genealogy/CYOA still TODO; e2e harness with mocked LLM remains; prompts could include display numbers/order for better zoom suggestions.
- **Next:** Add e2e test with mocked LLM outputs, refine prompts with manifest context, and define recipe maps for genealogy/CYOA once recipes exist.
### 20251126-2130 — E2E mocked intake chain
- **Result:** Added fixtures for overview/zoom mocks and an end-to-end test (`modules/intake/tests/test_intake_chain_e2e.py`) that runs builder → overview (mock) → zoom_refine (mock) → gap → confirm → dispatch_hint → dispatch (dry-run). Tests pass (one integration skipped for live LLM).
- **Notes:** Uses real contact_sheet_builder on the input images; dispatch kept dry-run. Recipe mapping still placeholder (genealogy→recipe-genealogy.yaml which doesn’t exist yet).
- **Next:** Provide actual genealogy/CYOA recipes or map to existing ones, enrich prompts with manifest display numbers, and consider lowering builder size for test speed.
### 20251126-2145 — Removed hard mapping; kept AI-driven selection
- **Result:** Dropped `recipe_map` parameter from zoom_refine; tests updated. Keeps recipe choice AI/heuristic-driven to avoid over-specifying.
- **Notes:** Dispatch still dry-run; recommended recipe still placeholder OCR when AI doesn’t set one.
- **Next:** Let LLM choose recipes based on catalog; add live run once satisfied with prompts.
### 20251126-2225 — Evidence-rich plan + PDF builder + no dispatch
- **Result:**
  - Builder now supports PDFs (renders pages once, builds sheets); intake recipe ends at confirm (no dispatch/execution).
  - Plan/gaps now carry `signal_evidence` with pages and reasons; gaps include page references.
  - Ran intake on `input/06 deathtrap dungeon.pdf` to validate: classified CYOA, signals images/cyoa/forms; gap: forms (page 11). No downstream run executed.
- **Notes:** LLM models switched to `gpt-4.1`; vision prompts use data URLs. Dispatch removed per AI-human flow.
- **Next:** Pilot on `input/onward-to-the-unknown-images/` (Arthur L'Heureux), add docs/usage, and keep AI-driven recipe selection.
### 20251127-?? — Intake pilot on full Onward to the Unknown (images)
- **Result:**
  - Ran intake on all images (`input/onward-to-the-unknown-images/`); plan saved to `output/runs/intake-onward/plan.json` with sheets/manifest alongside.
  - Signals: tables, images; evidence includes page lists; heuristic book_type set to `genealogy` (confidence 0.7) for planner convenience; no downstream execution.
- **Notes:** Page-level table tagging may include extra pages but correctly captures first table at page 23. Intake purpose is coarse content identification for the planner AI; not for exact page annotation.
- **Next:** Add brief usage/safe-command notes and finalize docs/tests coverage.
### 20251126-2040 — Recipe mapping hook in zoom refine
- **Result:** `zoom_refine_v1` now accepts a `recipe_map` JSON param and uses it before fallback heuristics; still defaults to OCR placeholder recipes.
- **Notes:** Needs real recipe targets (genealogy/CYOA) and an e2e branching test. Dispatcher unchanged.
- **Next:** Add end-to-end harness with mocked LLM, better recipe map, and prompt enrichment (display numbers/order).
### 20251127-1540 — Fixed intake run and stamped Onward pilot
- **Result:** Normalized signal evidence pages to strings, aligned recipe outputs per stage to avoid force-clean clobbering inputs, and relaxed intake modules to ignore driver state/progress flags. Confirmed full intake run on `input/onward-to-the-unknown-images/` via `recipe-intake-contact-sheet.yaml`; artifacts stamped under `output/runs/intake-onward/` (manifest, sheets, overview, zoom, gaps, final plan). Signals: images + tables; gap flagged missing tables module. No downstream dispatch executed.
- **Notes:** Page cues now referenced by display numbers from contact sheets; plan stored at `output/runs/intake-onward/overview_plan_final.jsonl`.
- **Next:** Add usage/docs + validator tests; consider minor prompt tuning for table/page localization fidelity (non-blocking).
### 20251127-1605 — Added usage/safe commands and validator CLI tests
- **Result:** Documented intake run/validation commands in this story; added CLI validation tests for manifest and plan in `modules/intake/tests/test_intake_chain.py`.
- **Notes:** Tasks for docs/tests now complete; intake remains generic and non-dispatching.
- **Next:** Minor prompt tuning for page localization is optional; otherwise hand off to Story 011 planner for interactive execution.
