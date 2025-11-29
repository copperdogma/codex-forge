# Story: Fighting Fantasy Engine format export

**Status**: Done  
**Created**: 2025-11-27  

---

## Goal
Replace the current Fighting Fantasy export path with a builder that emits the Fighting Fantasy Engine format (`input/ff-format/gamebook-schema.json`) while retaining every useful enrichment we already produce (page spans, images, provenance, raw/clean text, continuation links, confidence scores). The existing FF-specific output modules are single-use, so we will rewrite them directly to target the new schema without keeping the legacy JSON structure.

## Success Criteria / Acceptance
- New FF recipe outputs a single `gamebook.json` that validates against `input/ff-format/gamebook-schema.json` (title, startSection, formatVersion, sections keyed by id with `text`, `type`, `isGameplaySection`, etc.).
- Gameplay sections preserve/translate navigation, conditional navigation, combat, item, stat, luck, and death mechanics from our enriched data; non-gameplay content is typed (intro/rules/covers/etc.).
- Extra signals we already have (page_start/page_end, source_images/page images, raw_text/clean_text, portion_id, confidence, continuation links) are preserved either as top-level fields or in an `extras`/`provenance` block without violating the required schema.
- Recipe/driver wiring updated so the run writes the new artifact under `output/runs/<run_id>/gamebook.json` plus the usual intermediate JSONLs.
- Validation is automated in the recipe (jsonschema or validator module) and exercised on the Deathtrap Dungeon sample.

## Approach
1) **Schema mapping & gaps** — Read `gamebook-schema.json` + `gamebook-example.json` to map required fields to our current portion/enriched outputs; identify missing fields (e.g., isGameplaySection, conditionalNavigation structure, formatVersion, startSection) and where to source them (LLM prompts vs. config defaults).
2) **Builder rewrite** — Rework the FF export/builder module to assemble `sections` keyed by section/portion id, emit required fields, and carry forward optional metadata (images, page spans, raw_text, clean_text, confidence, continuation_of, source module/run ids). Allow safe extension via an `extras` or `provenance` object.
3) **Recipe update** — Clone the current FF recipe to `recipe-ff-engine.yaml` (or rename the existing one) so its final stage runs the new builder and writes `gamebook.json`; thread title/author/startSection/formatVersion via recipe params.
4) **Validation** — Add a jsonschema check (using the provided schema) as a final stage or post-step; fail the run on validation errors and surface counts of extra fields kept.
5) **Smoke on sample** — Run against `input/06 deathtrap dungeon.pdf` (mock if needed) to verify end-to-end artifact and ensure images/provenance are preserved.

## Tasks
- [x] Map existing enriched/portion fields to FF Engine schema; document any new derivations needed (isGameplaySection, conditionalNavigation, formatVersion defaults).
- [x] Design extra-data carriage (e.g., `extras`/`provenance` blocks) so we keep images, page ranges, raw/clean text, ids, and confidence without breaking validation.
- [x] Rewrite FF export/builder module to emit `gamebook.json` in target format and include optional extras.
- [x] Update FF recipe + driver wiring to pass metadata params (title/author/startSection/formatVersion) and to keep page/image provenance.
- [x] Add schema validation step using `input/ff-format/gamebook-schema.json`; integrate into recipe and document CLI usage.
- [x] Smoke test on Deathtrap Dungeon run; record artifact paths and validation output in the work log.

## Notes / Mapping Draft
- **Source artifacts:** `clean_page` (page text/images), `resolved_portion`, `enriched_portion` (section_id, choices/targets, combat/test_luck/item_effects, continuation, confidence).
- **Section id:** prefer `enriched.section_id` when present; fallback to `resolved.portion_id`; stringified.
- **text:** use concatenated clean text across `page_start..page_end`; keep as-is (no normalization) to satisfy “preserve original text exactly”.
- **type:** map our `type` if present; fallback rules: numeric sections → `section` with `isGameplaySection=true`; non-numeric/cover/rules inferred via recipe metadata or portion type hints.
- **isGameplaySection:** true for numeric sections or when choices/combat/test_luck/item_effects present; false for intro/rules/covers/template.
- **navigationLinks:** from `choices`/`targets` when unconditional; `choiceText` = `text` if supplied; `isConditional=false`.
- **conditionalNavigation:** derive from structured item/check/test_luck patterns if available; otherwise empty (not blocking schema).
- **combat:** map `combat` skill/stamina/name to `creature`; win/lose/escape currently absent—need LLM/enricher to infer or default null.
- **items/statModifications/testYourLuck/deathConditions:** map from `item_effects`, stat deltas, `test_luck`/death signals when present; will need prompting or rules to populate missing data.
- **pageStart/pageEnd:** carry from portion.
- **Provenance/extras (schema allows additionalProperties):** plan `provenance` block with `portion_id`, `orig_portion_id`, `confidence`, `source_images`, `source_pages`, `continuation_of`, `continuation_confidence`, `module_id`, `run_id`, `raw_text`, `clean_text`, `source_paths`.
- **Metadata:** provide via recipe params: `title`, optional `author`, `startSection` default `"1"`, `formatVersion` from schema (use `"1.0.0"` unless overridden).
- **Schema allowance for extras:** `gamebook-schema.json` does not set `additionalProperties=false`; safe to embed `provenance` and `extras` blocks under sections and metadata as long as required fields are present.
- **Builder shape plan:** output `gamebook.json` with `{metadata, sections}`; `sections` keyed by section_id/portion_id; include `provenance` block; keep `raw_text` in provenance to avoid violating “preserve original text exactly” in `text` field; emit `source_images` and `page_span` in provenance; hold a derived `source_pages` array for quick trace.
- **Defaults for missing gameplay fields:** if `choices` exist but no explicit conditional structure, emit `navigationLinks` with `isConditional=false`; if `test_luck` is true but no destinations, leave `testYourLuck` empty and add note in `provenance`; combat without win/lose targets stays as creature only; when neither `items` nor `statModifications` present, emit empty arrays to satisfy schema permissively.
- **Conditional mapping plan:** when `item_effects.action == "check"` and both success/failure targets exist, emit a single `conditionalNavigation` with `condition="has_item"` and map target sections; for `test_luck` boolean, if `choices` contain two targets, map them to `luckySection`/`unluckySection`; otherwise keep `testYourLuck` absent and record gap in provenance.
- **Validation plan:** add final recipe step `validate_ff_engine` running `python -m jsonschema -i gamebook.json input/ff-format/gamebook-schema.json` (or small helper module) and fail on errors; log counts of sections, gameplay vs non-gameplay, missing conditional mappings.

## Work Log
- 2025-11-27 — Story stubbed and requirements captured. Reviewed `input/ff-format/gamebook-schema.json` and `gamebook-example.json`; goal is to retarget FF export to this schema while retaining images, page provenance, and other enriched signals from current outputs. Existing FF-specific modules are safe to rewrite (no backward-compat dependency).
- 2025-11-27-1450 — Drafted schema mapping plan and provenance strategy (see Notes section). Proposed using `provenance` block to retain portion ids, confidence, continuation links, images, page ranges, raw/clean text. Next: confirm schema permits additionalProperties, firm up combat/conditional mapping and defaults, then start builder module rewrite + recipe update.
- 2025-11-27-1512 — Confirmed schema leaves `additionalProperties` open; safe to include `provenance` and `extras`. Added builder shape plan (metadata + sections keyed, provenance carrying raw_text/images/pages). Next: finalize combat/conditional defaults and start refactoring builder module and FF recipe to write `gamebook.json`.
- 2025-11-27-1530 — Added concrete defaults for navigation/combat/test-luck gaps and a validation plan (jsonschema step). Next: move to code—create/export builder module that ingests clean/enriched artifacts and outputs `gamebook.json`, then wire a new `recipe-ff-engine.yaml` with validation stage.
- 2025-11-27-1550 — Implemented `build_ff_engine_v1` export module (outputs gamebook.json with provenance) and `validate_ff_engine_v1` schema check; added recipe `configs/recipes/recipe-ff-engine.yaml` wiring OCR→clean→portion→resolve→build→validate. Tasks updated (mapping, builder, recipe, validation done). Next: run smoke on Deathtrap Dungeon (mock ok if heavy) and capture validation results/artifact paths.
- 2025-11-27-1625 — Ran mock smoke `python driver.py --recipe configs/recipes/recipe-ff-engine.yaml --mock --instrument` (timeout 300s). Output artifacts: `output/runs/deathtrap-ff-engine/gamebook.json` (113 sections) and validation report `output/runs/deathtrap-ff-engine/gamebook_validation.json` (valid). Updated builder defaults to map unknown types to `section` and treat `section` as gameplay by default.
- 2025-11-27-1650 — Added Node/Ajv validator wrapper `validate_ff_engine_node_v1` that runs the upstream engine validator (`input/ff-format/validator/cli-validator.js --json`). Not wired into the recipe yet (requires `npm install ajv`); keeps existing jsonschema validation as default. Next: decide whether to swap recipe validation to the Node validator after ensuring ajv is installed in the runtime.
- 2025-11-27-1715 — Swapped recipe validate stage to `validate_ff_engine_node_v1` (outputs `gamebook_validation_node.json`). Added Ajv preflight in module; requires `npm install ajv` in `input/ff-format/validator` (Node >=18). Did not rerun recipe to avoid failure until dependency installed.
- 2025-11-27-1730 — Removed legacy jsonschema validator (`validate_ff_engine_v1`); canonical validation now via the upstream Node/Ajv validator. Pending: ensure `npm install ajv` is run before pipeline execution.
- 2025-11-27-1755 — Bundled upstream validator + Ajv into module (`modules/validate/validate_ff_engine_node_v1/validator`, with package-lock/node_modules). Recipe updated to use bundled path; module default points to bundled validator. Re-ran mock recipe; Node validator now passes (startSection auto-falls back to first section id when missing). Artifacts: `output/runs/deathtrap-ff-engine/gamebook.json`, `gamebook_validation_node.json` (valid).
- 2025-11-27-1820 — Improved section typing/gameplay: builder now classifies non-numeric portions (toc/intro/rules/adventure_sheet/publishing_info) from text heuristics; startSection falls back to section "1" or first id; isGameplay false for non-section types. Added enrich stage (section_enrich_v1) to recipe so section ids/targets come from heuristic enrichment instead of window ids. Added Node version precheck and bundled ajv (no external install). Added helper script `scripts/smoke-ff-engine.sh` to run mock pipeline/validator. No CI planned per guidance.
- 2025-11-27-1905 — Smoke rerun with section_enrich + stub backfill: `bash scripts/smoke-ff-engine.sh` now passes Node validator. Gamebook: 388 sections (113 real + stubbed targets). Validation report shows only reachability warnings (expected with stubs). Artifacts: `output/runs/deathtrap-ff-engine/gamebook.json`, `gamebook_validation_node.json` (valid, warnings about unreachable sections).
- 2025-11-28-0115 — Full (non-mock) run resumed from portionize; completed and validated. Artifacts: `output/runs/deathtrap-ff-engine/gamebook.json` (422 sections incl. stub targets), `gamebook_validation_node.json` (valid, only reachability warnings). Updated pipeline-visibility Final JSON selection to prefer build_ff_engine artifact over validate outputs so UI links the correct file.
- 2025-11-28-0210 — Dashboard ordering fix: stages now sorted by first event/updated_at so build/validate render after enrich; Final JSON still prefers build_ff_engine. Builder now backfills only numeric targets, records stub_count/provenance, and reports stub count in logger; startSection warning avoided. Stage meta UI cleaned (no “— / ?” placeholders).
- 2025-11-27-1435 — Checklist audited per Story Builder instructions; tasks already present and actionable (mapping, extras plan, builder rewrite, recipe wiring, validation, smoke test). No doc changes needed beyond this log. Next: start schema-to-enriched field mapping and decide where to store extras/provenance in the target JSON without breaking validation.
