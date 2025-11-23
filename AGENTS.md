# AGENTS GUIDE — codex-forge

This repo processes scanned (or text) books into structured JSON, using modular stages driven by LLMs.

## Prime Directives
- **Do NOT run `git commit`, `git push`, or modify remotes unless the user explicitly requests it.**
- AI-first: the AI owns implementation and self-verification; humans provide requirements and oversight. Do not report work “done” without testing/validation against requirements and story acceptance criteria.
- Keep artifacts append-only; never rewrite user data or outputs in `output/` or `input/`.
- Default to `workspace-write` safe commands; avoid destructive ops (`rm -rf`, `git reset --hard`).
- Preserve non-ASCII only if the file already contains it.

## Repo Map (high level)
- Modules live under `modules/<stage>/<module_id>/` with `module.yaml` + `main.py` (no registry file).
- Driver: `driver.py` (executes recipes, stamps/validates artifacts).
- Schemas: `schemas.py`; validator: `validate_artifact.py`.
- Settings samples: `settings.example.yaml`, `settings.smoke.yaml`
- Docs: `README.md`, `snapshot.md`, `docs/stories/` (story tracker in `docs/stories.md`)
- Inputs: `input/` (PDF, images, text); Outputs: `output/` (git-ignored)

## Current Pipeline (modules + driver)
- Use `driver.py` with recipes in `configs/recipes/` (DAG-style ids/needs). Examples: `recipe-ocr.yaml`, `recipe-text.yaml`, `recipe-ocr-1-20.yaml`.
- Legacy linear scripts were removed; use modules only.

## Modular Plan (story 015)
- Modules scanned from `modules/`; recipes select module ids per stage.
- Validator: `validate_artifact.py --schema <name> --file <artifact.jsonl>` (page_doc, clean_page, portion_hyp, locked_portion, resolved_portion, enriched_portion).

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
- Dry-run a DAG recipe: `python driver.py --recipe configs/recipes/recipe-ocr-dag.yaml --dry-run`
- Section coverage check (fails on missing targets): `python modules/validate/assert_section_targets_v1.py --inputs output/runs/ocr-enrich-sections-merged/portions_enriched_backfill.jsonl --out /tmp/section_report.json`

## Open Questions / WIP
- Enrichment stage not implemented (Story 018).
- Shared helpers now live under `modules/common` (utils, ocr); module mains should import from `modules.common.*` without mutating `sys.path`.
- DAG/schema/adapter improvements tracked in Story 016/017.

## Etiquette
- Update the relevant story work log for any change or investigation.
- Keep responses concise; cite file paths when referencing changes.
- **Debugging discipline:** when diagnosing issues, inspect the actual data/artifacts at each stage before changing code. Prefer evidence-driven plans (e.g., grep/rg on outputs, view JSONL samples) over guess-and-edit loops. Document what was observed and the decision that follows.
