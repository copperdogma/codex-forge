# AGENTS GUIDE — codex-forge

This repo processes scanned (or text) books into structured JSON, using modular stages driven by LLMs.

## Prime Directives
- **Do NOT run `git commit`, `git push`, or modify remotes unless the user explicitly requests it.**
- AI-first: the AI owns implementation and self-verification; humans provide requirements and oversight. Do not report work “done” without testing/validation against requirements and story acceptance criteria.
- Keep artifacts append-only; never rewrite user data or outputs in `output/` or `input/`.
- Default to `workspace-write` safe commands; avoid destructive ops (`rm -rf`, `git reset --hard`).
- Preserve non-ASCII only if the file already contains it.

## Repo Map (high level)
- CLI stages: `pages_dump.py`, `clean_pages.py`, `portionize.py`, `consensus.py`, `dedupe_portions.py`, `normalize_portions.py`, `resolve_overlaps.py`, `build_portion_text.py`, `extract_text.py`, `validate_artifact.py`.
- Schemas: `schemas.py`
- Settings samples: `settings.example.yaml`, `settings.smoke.yaml`
- Docs: `README.md`, `snapshot.md`, `docs/stories/` (story tracker in `docs/stories.md`)
- New modular scaffolding: `modules/registry.yaml`, recipes in `configs/recipes/`
- Inputs: `input/` (PDF, images, text); Outputs: `output/` (git-ignored)

## Current Pipeline (legacy linear)
1) `pages_dump.py` — PDF→images→OCR (`pages_raw.jsonl`)
2) `clean_pages.py` — multimodal LLM cleaning (`pages_clean.jsonl`)
3) `portionize.py` — sliding-window portion hypotheses (`window_hypotheses.jsonl`)
4) `consensus.py` → `dedupe_portions.py` → `normalize_portions.py` → `resolve_overlaps.py`
5) `build_portion_text.py` — assembles `portions_final_raw.json`

## Modular Plan (story 015, WIP)
- Registry: `modules/registry.yaml` enumerates modules (extract/clean/portionize/consensus/resolve/build/enrich placeholder).
- Recipes: `configs/recipes/recipe-ocr.yaml`, `recipe-text.yaml` show module selection per stage.
- New extractor: `extract_text.py` ingests text/MD/HTML via glob into `pages_raw.jsonl`.
- Validator: `validate_artifact.py --schema <name> --file <artifact.jsonl>` (portion_hyp_v1, locked_portion_v1 currently).

## Key Files/Paths
- Artifacts live under `output/runs/<run_id>/`.
- Input PDF: `input/06 deathtrap dungeon.pdf`; images: `input/images/`.
- Story work logs: bottom of each `docs/stories/story-XXX-*.md`.
- Change log: `CHANGELOG.md`.

## Models / Dependencies
- OpenAI API (set `OPENAI_API_KEY`).
- Tesseract on PATH (or set `paths.tesseract_cmd`).
- Defaults: `gpt-4.1-mini` with optional boost `gpt-5`; see scripts/recipes.

## Safe Command Examples
- Inspect status: `git status --short`
- List files: `ls`, `rg --files`
- View docs: `sed -n '1,120p' docs/stories/story-015-modular-pipeline.md`
- Run validator: `python validate_artifact.py --schema portion_hyp_v1 --file output/...jsonl`

## Open Questions / WIP
- Driver to execute recipes and stamp metadata is TBD.
- Enrichment stage not implemented; placeholder in registry.
- Schema metadata only attached to portion hypothesis/locked portions so far.

## Etiquette
- Update the relevant story work log for any change or investigation.
- Keep responses concise; cite file paths when referencing changes.
