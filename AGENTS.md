# AGENTS GUIDE — codex-forge

This repo processes scanned (or text) books into structured JSON, using modular stages driven by LLMs.

## Prime Directives
- **Do NOT run `git commit`, `git push`, or modify remotes unless the user explicitly requests it.**
- System is in active development (not production); do not preserve backward compatibility or keep legacy shims unless explicitly requested.
- **AI-first:** the AI owns implementation and self-verification; humans provide requirements and oversight.
- **The Definition of Done:** A story or task is **NOT complete** until:
    1. It runs successfully through `driver.py` in a real (or partial resume) pipeline.
    2. Produced artifacts exist in `output/runs/`.
    3. **Manual Data Inspection**: You have opened the artifacts (JSON/JSONL) and manually verified that the specific data being added/fixed is accurate and high-quality.
    4. You have reported the specific artifact paths and sample data verified to the user.
- **100% Accuracy Requirement:** The final artifacts (gamebook.json) are used directly in a game engine. **If even ONE section number or choice is wrong, the game is broken.** Partial success on section coverage or choice extraction is a complete failure. Pipeline must achieve 100% accuracy or fail explicitly.
- **Inspect outputs, not just logs:** A green or non-crashing run is not evidence of correctness. Always manually open produced artifacts and check for logical errors (e.g., concatenated sections, missing data, incorrect values).
- Keep artifacts append-only; never rewrite user data or outputs in `output/` or `input/`.

## Generality & Non-Overfitting (Read First)
- Optimize for an input *category* (e.g., Fighting Fantasy scans), not a single PDF/run.
- Do not hard-code page IDs, book-specific strings, or one-off replacements (e.g., `staMTNA→STAMINA`) in pipeline code.
- Specialization must be explicit and scoped:
  - Prefer recipe/module params (knobs) over branching logic.
  - If something truly is recipe-specific, keep it in a clearly scoped module and document the scope + knobs.
- **Architecture goal (reusability):** Keep upstream intake/OCR modules as generic as possible. Push booktype-specific heuristics/normalization (e.g., gamebook navigation phrases, FF section conventions) downstream into booktype-aware modules (portionize/extract/enrich/export) or recipe-scoped adapters.
- Prefer *signals and loops* over brittle fixes: detect → validate → targeted escalate → validate.
- If adding deterministic corrections, they must be generic (class-based, conservative), opt-in by default, and preserve original text/provenance.
- Validate across multiple pages/runs; add regression checks on *patterns* (coverage, bad-token occurrence, empty text rate), not exact strings.

## Critical AI Mindset: Think First, Verify Always

### Before Building: Question the Approach
**DO NOT blindly implement what was asked without critical evaluation.**

Before writing any significant code or starting implementation:
1. **Pause and analyze**: Is this the right approach? Is there a better way?
2. **Consider alternatives**: Could this be simpler? More robust? More maintainable?
3. **Spot obvious issues**: Does the request seem problematic, incomplete, or suboptimal?
4. **Speak up**: If you see a better solution or potential issue, **STOP and discuss with the user first**
   - Example: "Before implementing X, I notice Y approach would be significantly better because Z. Should we discuss?"
   - Example: "This request asks for A, but I see it may not address the root cause B. Can we verify the goal?"

**You are not a code monkey**. You are a technical partner. Think critically, challenge assumptions, propose improvements.

**When adding new behaviors**, prefer shipping them as a separate module first, run a baseline, and only merge into an existing module after comparing baselines to prove no regressions.

## Module Development & Testing Workflow

This is a **data pipeline** project. Success means correct data in `output/runs/`, not just code that runs without errors.

### Development Phase: Standalone Testing (Encouraged)
**Use standalone testing for rapid iteration during development:**
- Fast debugging without re-running expensive upstream stages
- Direct control over inputs for testing edge cases
- Cost-effective iteration during implementation

```bash
# Good for development - iterate quickly
PYTHONPATH=. python modules/enrich/ending_guard_v1/main.py \
  --portions /path/to/test_input.jsonl \
  --out /tmp/test_output.jsonl
```

**Standalone testing is a tool for development, NOT a completion criterion.**

### Completion Phase: Integration Testing (Mandatory)
**Work is NOT complete until tested through driver.py in the real pipeline and manually verified for quality.**

**Completion checklist:**
1. **Clear Python cache:** `find modules/<module> -name "*.pyc" -delete` (stale cache causes silent failures)
2. **Run through driver:** Use `--start-from <stage>` or a resume recipe.
3. **Verify artifacts exist:** Check `output/runs/<run_id>/{ordinal:02d}_{module_id}/` has expected files.
4. **Manual Data Verification (Mandatory)**: Open JSONL/JSON, read 5-10 samples, and verify content correctness. **Check for logical failures** (e.g., mismatched page ranges, corrupted HTML, missing features).
5. **Check downstream stages:** Ensure next stages can consume the artifacts.
6. **Document findings:** Include artifact paths + sample data in work log.

**Artifact reuse policy**: You MAY reuse artifacts from a previous run (e.g., expensive OCR results) to save time/cost using a resume recipe or `load_artifact_v1`. However, you MUST ensure that the reused IDs and schemas are consistent with the current run to prevent "megasection" or "mismatch" failures.

```bash
# Completion testing - must succeed for work to be "done"
find modules/enrich/ending_guard_v1 -name "*.pyc" -delete
python driver.py --recipe configs/recipes/recipe-ff-ai-ocr-gpt51.yaml \
  --run-id test-ending-detection --start-from detect_endings --force
ls -lh output/runs/test-ending-detection/13_ending_guard_v1/portions_with_endings.jsonl
python3 -c "import json; [print(json.loads(line).get('ending')) for line in open('...')[:5]]"
```

**Completion criteria:**
- ❌ "Module works standalone to /tmp" → NOT DONE
- ❌ "Code runs without errors" → NOT DONE
- ❌ "Artifacts copied from /tmp to output/" → NOT DONE (breaks provenance)
- ✅ "Driver.py executed stage successfully, artifacts in output/runs/, data verified" → DONE

### Why Both Matter
- **Standalone testing** saves time and money during development
- **Driver integration** proves it works in the real system with real dependencies
- **Neither replaces the other** - use standalone for iteration, driver for verification

**Common failure pattern to avoid:**
1. ❌ Develop module with standalone testing → works great
2. ❌ Inspect `/tmp/output.jsonl` → data looks perfect
3. ❌ Declare story complete → **WRONG**
4. ❌ Later discover it fails when run through driver.py

**Correct pattern:**
1. ✅ Develop module with standalone testing (iterate rapidly)
2. ✅ Once logic works, test through driver.py
3. ✅ Fix any integration issues (missing args, schema mismatches, dependency problems)
4. ✅ Verify artifacts in `output/runs/` have correct data
5. ✅ Only then declare complete

### Artifact Inspection Examples
**What NOT to do:**
- ❌ "Implemented extraction. Module runs successfully."
- ❌ "Fixed duplicates. No errors reported."
- ❌ "Added classification. Tests pass."

**What TO do:**
- ✅ "Implemented extraction. Inspected `output/runs/.../03_portionize/portions.jsonl` - 293 portions with populated text (e.g., portion 9: 1295 chars 'There is also a LUCK box...'). Quality verified."
- ✅ "Fixed duplicates. Checked `output/runs/.../06_enrich/portions_enriched.jsonl` - was 3 sections claiming id='1', now 1 (page 16, correct). Resolved."
- ✅ "Added classification. Sampled 10 from `output/runs/.../gamebook.json` - 8 'gameplay', 2 'rules'. Section 42: 'gameplay', has combat 'SKILL 7 STAMINA 9'. Correct."

## Validation & Stage Resolution

### Stage resolution discipline
A stage must resolve before the next runs. Resolution means either (a) it meets its coverage/quality goal or (b) it finishes a defined escalate→validate loop and records unresolved items prominently. Do not silently push partial outputs downstream.

Examples:
- Section splitting must complete escalation (retries, stronger models) until coverage is acceptable or retry cap is hit
- Boundary verification must pass or emit explicit failure markers before extraction starts
- Extraction must retry/repair flagged portions; unresolved portions carry explicit error records (not empty text)
- **Stub-fatal policy:** Default is fatal on stubs—pipelines must fail unless `allow_stubs` is explicitly set

### Diagnostic validation
For every missing/no-text/no-choice warning, emit a per-item provenance trace walking upstream artifacts (OCR → elements → boundaries → portions) showing where content disappeared. Traces must include artifact paths, page/element IDs, and text snippets. No manual artifact edits—fix code/logic and regenerate.

### Escalate-to-success loop (applies to every stage)
- Default pattern: **detect/code → validate → targeted escalate → validate**, repeat until 100% success or a retry/budget cap is hit.
- Each pass must use the latest artifacts (hash/mtime guard to prevent stale inputs).
- Escalation outputs become the new gold standard for that scope (do not fall back to earlier OCR/LLM results).
- Surface evidence automatically: emit per-item presence/reason flags and small debug bundles for failures.
- **Escalation caps are mandatory:** Every escalation loop must have a maximum iteration/retry/budget cap to prevent infinite loops. Examples: `max_retries`, `budget_pages`, `max_repairs`, `max_candidates`. If a stage hits its cap without reaching 100% accuracy, it must fail explicitly (not silently pass partial results).

### Choice Extraction & Validation (Critical for Game Engine)

**Code-first extraction approach:**
- **Primary signal:** Pattern matching for "turn to X", "go to Y" references in text
- **AI role:** Validation only, not primary extraction (saves costs, more reliable)
- **Module:** `extract_choices_v1` - dedicated, single-purpose choice extractor

### Scanning for Section Features

When implementing modules that scan sections for specific features (combat, inventory, stat changes, etc.), strictly follow the **try-validate-escalate** pattern:

1.  **Try (Code-first)**: Use deterministic patterns (regex, keyword matching) to identify and extract features. This is fast and free.
2.  **Validate**: Apply custom validation rules specific to the feature (e.g., "SKILL must be between 1-15", "Item gain must include an item name").
3.  **Escalate (AI)**: If validation fails or the code-first pass detects ambiguity (e.g., "SKILL mentioned but no block found"), escalate to a targeted AI call with a stronger model.

Always think about **HOW** to validate the data for the specific feature you are extracting. Each feature likely needs its own set of integrity checks.

**Two-layer validation:**

1. **Per-section validation:** Text patterns vs. extracted choices
   - Scan text for all "turn to X" references
   - Compare with extracted choices
   - Flag discrepancies (text mentions choice not extracted)
   - **Limitation:** Can't detect missing choices not mentioned in text patterns

2. **Graph validation (Orphan Detection):**
   - Every section (except section 1) must be referenced by at least one choice
   - Build graph: sections → incoming choice references
   - Find orphans: sections with zero incoming references
   - **Signal:** Orphans prove we're missing pointers somewhere (even if we don't know where)
   - **Limitation:** Tells us THAT we have errors, not WHERE the missing choices are

**Escalation:** If validation fails, flagged sections must be re-extracted with choice-focused prompts and stronger models. Maximum retry cap required (e.g., `max_choice_repairs: 50`).

### Prompt Design: Trust AI Intelligence, Don't Over-Engineer

- Write prompts at the document/recipe level (keep them generic; see "Generality & Non-Overfitting").
- Prefer simple, structural instructions over brittle heuristics:
  - ✅ "This is a Fighting Fantasy gamebook with front matter, rules, then numbered sections 1–400. Find section headers."
  - ❌ Complex regex/keyword rule stacks and confidence micro-tuning.
- Use code for deterministic transforms; use AI for semantic structure (classification, boundary detection, context).

## Escalation Strategy (known-good pattern)
When a first-pass run leaves quality gaps, escalate in a controlled, data-driven loop:
1. **Baseline**: Run the fastest/cheapest model with conservative prompts.
2. **Detect issues**: Programmatically flag suspect items (missing choices, low alpha ratio, empty text, dead ends, etc.).
3. **Targeted re-read**: Re-run only the flagged items with a stronger multimodal model and a focused prompt that embeds the minimal context directly (page image + raw_text in the prompt; no external attachments).
4. **Rebuild & revalidate**: Rebuild downstream artifacts from the patched portions and re-run validation.
5. **Verify artifacts**: Spot-check the repaired items and confirm warnings/errors are cleared or correctly justified (e.g., true deaths).
Avoid manual text edits; use this loop to stay generic, reproducible, and book-agnostic (see “Generality & Non-Overfitting”).

### OCR structural guard (add before baseline split)
Before portionization, automatically flag pages for high-fidelity re-OCR if either engine output shows fused/structurally bad text:
- Headers present in the image but missing as standalone lines (e.g., multiple section numbers fused into one long line).
- Extreme per-page text divergence between engines (token Jaccard low or one engine has a mega-line while the other does not), based on flattened page text, not headers.
- On flagged pages, re-OCR with a stronger, layout-aware vision model (page ±1 if needed), then continue the pipeline with the improved page text.

## Repo Map (high level)
- Modules live under `modules/<stage>/<module_id>/` with `module.yaml` + `main.py` (no registry file).
- Driver: `driver.py` (executes recipes, stamps/validates artifacts).
- Schemas: `schemas.py`; validator: `validate_artifact.py`.
- Settings samples: `settings.example.yaml`, `settings.smoke.yaml`
- FF smoke (20pp run-only check): `configs/settings.ff-canonical-smoke.yaml` with canonical recipe; use `--settings` instead of a separate recipe.
- Docs: `README.md`, `snapshot.md`, `docs/stories/` (story tracker in `docs/stories.md`)
- Inputs: `input/` (PDF, images, text); Outputs: `output/` (git-ignored)

## Current Pipeline (modules + driver)
- Use `driver.py` with recipes in `configs/recipes/`.
- **Primary recipe for Fighting Fantasy**: `recipe-ff-ai-ocr-gpt51.yaml` (GPT-5.1 AI-first OCR, HTML output)
- Legacy OCR ensemble recipe (`recipe-ff-canonical.yaml`) is deprecated; do not use.
- Other recipes: `recipe-ocr.yaml`, `recipe-text.yaml` (for reference/testing only)
- Legacy linear scripts were removed; use modules only.

## Modular Plan (story 015)
- Modules scanned from `modules/`; recipes select module ids per stage.
- Validator: `validate_artifact.py --schema <name> --file <artifact.jsonl>` (page_doc, clean_page, portion_hyp, locked_portion, resolved_portion, enriched_portion).

## Key Files/Paths
- Artifacts live under `output/runs/<run_id>/`.
- **Artifact organization**: Each module's artifacts are in `{ordinal:02d}_{module_id}/` folders directly in run_dir (e.g., `01_extract_ocr_ensemble_v1/pages_raw.jsonl`)
- **Final outputs**: `gamebook.json` stays in root for easy access
- **Pipeline metadata**: `pipeline_state.json`, `pipeline_events.jsonl`, `snapshots/` remain in root
- Driver now auto-generates a fresh `run_id`/output directory per run; reuse is opt-in via `--allow-run-id-reuse` (or explicit `--run-id`).
- Input PDF: `input/06 deathtrap dungeon.pdf`; images: `input/images/`.
- Story work logs: bottom of each `docs/stories/story-XXX-*.md`.
- Change log: `CHANGELOG.md`.

## Models / Dependencies
- OpenAI API (set `OPENAI_API_KEY`).
- Tesseract on PATH (or set `paths.tesseract_cmd`).
- **Model Selection Guidelines**:
  - **For maximum intelligence/complex reasoning**: Use `gpt-5` (or latest flagship model)
  - **For speed/value**: Use `gpt-4.1-nano` or `gpt-4.1-mini` (fastest and cheapest)
  - **Avoid defaulting to `gpt-4o`**: It's been supplanted by `gpt-5` for smarts, and mini/nano models for speed/value
  - **Reference**: [OpenAI Models Documentation](https://platform.openai.com/docs/models) - Check this for latest models, capabilities, and pricing
- Defaults: `gpt-4.1-mini` with optional boost `gpt-5`; see scripts/recipes.

## Running & Monitoring (canonical recipe: recipe-ff-ai-ocr-gpt51.yaml)

**Always run on ARM64 + MPS by default. If that is not available, stop and fix the env before running the pipeline.**

**Current canonical recipe**: `configs/recipes/recipe-ff-ai-ocr-gpt51.yaml` (GPT-5.1 AI-first OCR)
- HTML-native output, faster than legacy OCR ensemble
- Legacy `recipe-ff-canonical.yaml` is deprecated and disabled

### Environment (required)
- Create/refresh env (Metal pins in `requirements.txt` + `constraints/metal.txt`):
  - `conda config --add envs_dirs /Users/cam/.conda_envs`
  - `conda create -n codex-arm-mps python=3.11 -y`
  - `conda activate codex-arm-mps`
  - `pip install --no-cache-dir -r requirements.txt -c constraints/metal.txt`
- Activate env: `source ~/miniforge3/bin/activate codex-arm-mps`
- Guard: `python scripts/check_arm_mps.py` (must pass)
- SHM-safe env (required for EasyOCR/libomp stability):
  - `KMP_USE_SHMEM=0 KMP_CREATE_SHMEM=FALSE OMP_NUM_THREADS=1 KMP_AFFINITY=disabled KMP_INIT_AT_FORK=FALSE`

### Full pipeline run (preferred)
- Use the monitored wrapper (creates pidfile + crash markers):
  - `scripts/run_driver_monitored.sh --recipe configs/recipes/recipe-ff-ai-ocr-gpt51.yaml --run-id <run_id> --output-dir output/runs -- --instrument --force`
- **Important**:
  - `--output-dir` must be the **parent** (`output/runs`), not a run-specific path.
  - `run_driver_monitored.sh` pre-deletes the run dir on `--force`, strips `--force`, and adds `--allow-run-id-reuse`.
  - `driver.py` refuses `--force` on `output/runs` root; always pass a run-specific dir.

### Monitoring (choose one)
- Active monitor (recommended; shows crash immediately):
  - `scripts/monitor_run.sh output/runs/<run_id> output/runs/<run_id>/driver.pid 5`
- Foreground 60s polling loop (only if background terminals are disabled):
  - `while true; do date; tail -n 1 output/runs/<run_id>/pipeline_events.jsonl; sleep 60; done`
- Crash visibility:
  - `monitor_run.sh` tails `driver.log` when PID disappears and appends a `run_monitor` failure event.
  - `run_driver_monitored.sh` calls `scripts/postmortem_run.sh` on exit to append a `run_postmortem` failure event.

### Smoke runs
- 5pp smoke: `python driver.py --recipe configs/recipes/recipe-ff-ai-ocr-gpt51.yaml --settings configs/settings.ff-ai-ocr-smoke-5.yaml --run-id ff-ai-ocr-smoke-5 --output-dir /tmp/cf-ff-ai-ocr-smoke-5 --force`
- Note: If smoke settings don't exist, create them based on the main recipe with reduced page ranges

### Troubleshooting (must-read)
- **OMP SHM crash** (`Can't open SHM2`):
  - Ensure `codex-arm-mps` env + SHM-safe vars are set.
  - If it still fails, run outside any restricted/sandboxed shell or disable EasyOCR/torch paths.
- **MPS unavailable**: rerun env setup; `python scripts/check_arm_mps.py` must pass.
- **Apple Vision OCR sandbox failure** (`sysctlbyname for kern.hv_vmm_present failed`): run outside sandbox/full host permissions or disable `apple` engine.
- **Monitoring looks idle but process died**: check `driver.log` in the run dir and confirm `run_monitor` / `run_postmortem` events exist in `pipeline_events.jsonl`.

## Safe Command Examples
- Inspect status: `git status --short`
- List files: `ls`, `rg --files`
- View docs: `sed -n '1,120p' docs/stories/story-015-modular-pipeline.md`
- Run validator: `python validate_artifact.py --schema portion_hyp_v1 --file output/...jsonl`
- Dry-run the canonical recipe: `python driver.py --recipe configs/recipes/recipe-ff-ai-ocr-gpt51.yaml --dry-run`
- Section coverage check: `python modules/adapter/section_target_guard_v1/main.py --inputs output/runs/ocr-enrich-sections-noconsensus/portions_enriched.jsonl --out /tmp/portions_enriched_guard.jsonl --report /tmp/section_target_report.json`
- Dashboard: `python -m http.server 8000` then open `http://localhost:8000/docs/pipeline-visibility.html`
## Open Questions / WIP
- Enrichment stage not implemented (Story 018).
- Shared helpers now live under `modules/common` (utils, ocr); module mains should import from `modules.common.*` without mutating `sys.path`.
- DAG/schema/adapter improvements tracked in Story 016/017.

## Etiquette
- Update the relevant story work log for any change or investigation.
- Keep responses concise; cite file paths when referencing changes.
- **Impact-first updates (required):** When reporting progress, don’t just summarize what changed—also state how it improved (or failed to improve) outcomes.
  - Include a short “Impact” block with:
    - **Story-scope impact:** What acceptance criteria/tasks this unblocked or de-risked.
    - **Pipeline-scope impact:** What got measurably better downstream (coverage, fewer escalations, fewer bad tokens, cleaner boundaries, etc.).
    - **Evidence:** 1–3 concrete artifact paths checked (e.g., `output/runs/<run_id>/07_reconstruct_text_v1/pagelines_reconstructed.jsonl`, `.../09_elements_content_type_v1/elements_core_typed.jsonl`) and what you saw there.
    - **Next:** The next highest-leverage step and what would falsify success.
  - If results are mixed, say so explicitly and name the remaining failure mode(s).
- **Debugging discipline:** when diagnosing issues, inspect the actual data/artifacts at each stage before changing code. Prefer evidence-driven plans (e.g., grep/rg on outputs, view JSONL samples) over guess-and-edit loops. Document what was observed and the decision that follows.
- **Reuse working patterns first:** before inventing a new solution, look for an existing working pattern in this repo (code, UX, helper). Read it, understand it, and adapt with minimal changes.
