# Story: Enrichment & alternate modules

**Status**: To Do

---

## Acceptance Criteria
- Enrichment module implemented and registered; extracts choices/combat/items/endings into `enriched_portion_v1`.
- At least one alternate module each for portionize and consensus (e.g., coarse portionizer or heuristic; different consensus strategy) to demonstrate swapability.
- Recipes include examples selecting the new modules; driver executes them end-to-end.
- Validator updated to cover new module outputs if schemas differ.

## Tasks
- [x] Implement enrichment module (LLM or rule-based) emitting `enriched_portion_v1`; add to registry. *(enrich_struct_v1)*
- [x] Add alternate portionizer module (e.g., coarse-window) and alternate consensus module; register them. *(portionize_page_v1, consensus_spanfill_v1)*
- [x] Add recipes showcasing module swaps and enrichment stage usage. *(recipe-text-enrich-alt.yaml)*
- [ ] Extend validator/ schemas if enrichment output needs updates. *(not needed yet; verify after real run)*
- [x] Add smoke(s) covering enrichment + alternate modules (can be mock-friendly for cost control). *(text ingest recipe as low-cost smoke)*

## Notes
- Build on existing resolved portions; keep compatibility with Story 015 stamping.
- Consider cost controls (mock or small-page samples) for CI-ish runs.

## Design Sketch
- **Enrichment module (`enrich_struct_v1`)**: stage `enrich`; reads resolved portions + pages (clean or raw) to fetch span text and images; LLM prompt extracts choices/combat/test_luck/item_effects into `enriched_portion_v1`; params: `model`, `boost_model`, `text_field` (`clean_text|raw_text`), `max_chars`, `include_images`.
- **Alternate portionizer (`portionize_page_v1`)**: deterministic, groups pages into fixed-size spans (default 1 page) without LLM; emits `portion_hyp_v1` with configurable `group_size`, optional `range_start/range_end`.
- **Alternate consensus (`consensus_spanfill_v1`)**: greedy high-confidence coverage with gap fill and optional forced range; no voting; keeps shortest high-conf spans first to reduce overlaps.
- **Recipes**: add DAG recipe showcasing enrichment stage and swapability (e.g., coarse page-based portionizer + vote-based or spanfill consensus); include text-friendly smoke variant to cap token costs.

## Work Log
### 20251121-2116 — Reviewed story scope and checklist
- **Result:** Success; confirmed acceptance criteria and existing task list are present and actionable.
- **Notes:** No changes to tasks yet; enrichment module and alternate modules still unstarted.
- **Next:** Sketch enrichment module approach and schema implications before implementation.
### 20251121-2119 — Scanned current pipeline code and schemas
- **Result:** Success; located `enriched_portion_v1` schema in `schemas.py`, driver defaults include `enrich` stage output; existing modules: portionize_sliding_v1 and consensus_vote_v1 only.
- **Notes:** Driver scans module folders via `module.yaml`; no enrichment stage exists yet. Consensus module is vote-based; portionizer uses sliding-window LLM.
- **Next:** Draft design for enrichment module and alt portionizer/consensus; decide params and prompts.
### 20251121-2120 — Drafted module/recipe design
- **Result:** Success; documented plan for `enrich_struct_v1`, `portionize_page_v1`, `consensus_spanfill_v1`, plus DAG + smoke recipes with enrichment stage.
- **Notes:** Enrichment to use span text from pages (clean/raw) with JSON-output prompt; alt portionizer deterministic grouped pages; alt consensus greedy gap-fill.
- **Next:** Implement modules following design; wire into recipes and add smoke coverage.
### 20251121-2124 — Implemented enrichment + alternate modules and recipe; ran tests
- **Result:** Success; added `enrich_struct_v1`, deterministic `portionize_page_v1`, and `consensus_spanfill_v1`; wired enrich input handling into `driver.py`; created `configs/recipes/recipe-text-enrich-alt.yaml`. Pytest (`driver_plan` + `driver_integration`) passing (13/13).
- **Notes:** Enrichment uses LLM JSON response with optional image support, truncates span text to `max_chars`; consensus spanfill greedily covers gaps; recipe uses text ingest to keep costs low.
- **Next:** Consider additional smoke (OCR path) and prompt tuning once real run tried; verify schema validation on enriched outputs in practice.
### 20251121-2128 — Dry-run recipe with new modules
- **Result:** Success; `driver.py --dry-run --recipe configs/recipes/recipe-text-enrich-alt.yaml` shows correct command chain including enrich stage.
- **Notes:** Ready for real run when API key set; no mock path for enrich so will incur LLM calls.
- **Next:** Run real or limited-range execution to inspect `portions_enriched.jsonl`; adjust prompt/schema if needed.
### 20251121-2130 — Ran text enrich recipe end-to-end
- **Result:** Success; full run of `recipe-text-enrich-alt.yaml` produced enriched output (1 row) with choice extracted (target "2", text "choose left"). All stages stamped/validated.
- **Notes:** Enriched JSON example at `output/runs/text-enrich-alt/portions_enriched.jsonl`; `created_at` and `run_id` remain null (driver stamps schema but not created_at/run_id for enrich stage yet—consider adding).
- **Next:** Decide if validator needs to enforce non-null metadata for enriched outputs; add OCR-based recipe variant if desired.
### 20251121-2132 — Filled metadata stamping; reran recipe
- **Result:** Success; driver stamping now backfills `module_id`, `run_id`, `created_at` when missing/null. Reran recipe with `--force`; enriched rows now include run_id and timestamps.
- **Notes:** Re-run reused files so duplicates appear in enriched output; clean run dir for fresh artifacts if needed.
- **Next:** Optionally add cleanup/overwrite behavior or guidance; consider OCR-based enrichment recipe.
### 20251121-2134 — Added OCR-based alt recipe and validated dry-run
- **Result:** Added `configs/recipes/recipe-ocr-enrich-alt.yaml` using extract_ocr -> clean_llm -> portionize_page_v1 -> consensus_spanfill_v1 -> dedupe/normalize/resolve -> build -> enrich_struct_v1 (pages 1–2 for cost cap). Dry-run shows correct command chain.
- **Notes:** Provides OCR pathway showcasing new modules + enrichment; not executed yet to avoid extra API cost.
- **Next:** Optionally run OCR recipe for real when budget allows; consider cleaning run dirs before reruns to avoid duplicated JSONL rows.
### 20251121-2135 — Added test for stamp metadata backfill
- **Result:** Success; unit test in `tests/driver_plan_test.py` asserts `stamp_artifact` fills module_id/run_id/created_at when missing. Tests passing (10/10 in file).
- **Notes:** Pydantic deprecation warning persists (existing).
- **Next:** Consider cleaning run dirs before rerun to avoid duplicate rows; optionally add enrich validator checks if more fields needed.
### 20251121-2137 — Ran OCR alt recipe end-to-end
- **Result:** Success; `recipe-ocr-enrich-alt.yaml` executed (pages 1–2) producing enriched outputs with images referenced. No choices/combat detected in intro pages; timestamps/run_id populated.
- **Notes:** Enriched sample at `output/runs/ocr-enrich-alt/portions_enriched.jsonl`; truncation marker present on page 2 due to `max_chars`.
- **Next:** If desired, adjust `max_chars` or include images for deeper pages; consider validator rules only if enrichment fields need stricter checks.
### 20251121-2139 — Prevented duplicate artifacts on force reruns
- **Result:** Added `cleanup_artifact` helper called when `--force` is used; removes existing stage output before rerun to avoid append duplicates. Unit test added in `tests/driver_plan_test.py`; all tests in file now 11/11 passing.
- **Notes:** Pydantic deprecation warning remains (existing).
- **Next:** If more rigorous validation needed for enrichment outputs, add validator tests; otherwise story looks complete.
