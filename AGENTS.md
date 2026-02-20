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
- **Precompute context for readers:** Prefer computing metrics (e.g., costs/usage/quality signals) at the stage that produces them and write them into artifacts/logs (e.g., `instrumentation.json`) instead of relying on downstream recomputation.

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

**Default stance (important):** When requirements are ambiguous or correctness hinges on interpretation, **pause, investigate, and reason first**. Surface 1–2 plausible interpretations/options and only ask if uncertainty remains after reasoning.

### AI-Assist Guideline (Fundamental)
- Prefer code-first extraction for speed/cost, but **use targeted AI calls** when rules would balloon or edge cases are too varied.
- Keep AI calls bounded and **focused on flagged sections**; avoid overfitting regexes to brittle cases.
- Any AI-assisted outputs must still be validated (tests + pipeline run) and logged in the work log.

## Module Development & Testing Workflow

This is a **data pipeline** project. Success means correct data in `output/runs/`, not just code that runs without errors.

**Cost discipline (OCR):**
- Treat the initial OCR stage as **expensive and single-run** whenever possible.
- Iterate downstream by reusing OCR artifacts (`load_artifact_v1`, `--start-from`, or run-local `config.yaml`), not by re-running OCR.
- Only re-run OCR when the OCR itself is the suspected failure source and a controlled re-OCR is required.

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

**Partial reruns (default behavior):** When using `--start-from`, driver.py **invalidates downstream outputs** by default (removes later stage artifacts and state entries) and re-runs everything after the start stage. Use `--keep-downstream` only when you explicitly intend to reuse downstream artifacts.

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

## Patching System (Last Resort)
When a book strongly defies conventions and generic/escalation passes still fail, use the patching system to override specific outputs. This is a **last-resort** mechanism after attempts to generalize.

**When to use patches:**
- After generic modules + escalation loops still produce wrong structure/data.
- When fixes would be overly specific and would harm reusability.
- When the book has unique layout rules that can’t be reliably inferred.

**Patch rules:**
- Patches must be minimal and scoped to the smallest necessary correction.
- Preserve original provenance; do not hand-edit artifacts outside the pipeline.
- Prefer patching structured outputs (portion boundaries, chapter map, table rows) rather than raw OCR text.
- Document the rationale, the patch file, and verification evidence in the story work log.

**Workflow (recommended):**
1. Run the pipeline to the best generic result.
2. Inspect artifacts and identify specific incorrect items.
3. Create/update a `*.patch.json` file (see `input/FF22 Robot Commando.patch.json` for structure).
4. Apply the patch via the patching module/recipe step.
5. Rebuild downstream artifacts and re-validate.
6. Manually verify patched outputs and record the artifact paths + samples.

**How patches are applied (meta-layer in driver):**
- `driver.py` discovers a patch file next to the input (`{book_name}.patch.json`) and copies it into the run as `output/runs/<run_id>/patch.json`.
- Patches are applied **outside** modules by the driver, keyed by `apply_before` / `apply_after` with a **module_id**.
- `apply_before`: driver finds the input artifact that matches `target_file` and applies the patch before the module runs.
- `apply_after`: driver applies the patch directly to the module’s output artifact (so downstream stages read patched data).
- Patch failures do **not** fail the pipeline; they emit warnings in `pipeline_events.jsonl`.
- Validation modules (currently `validate_ff_engine_v2`) can receive `--patch-file` so warnings may be suppressed.

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
- FF smoke (20pp run-only check): `configs/settings.ff-ai-ocr-gpt51-smoke-20.yaml` with canonical recipe; use `--settings` instead of a separate recipe.
- Docs: `README.md`, `snapshot.md`, `docs/stories/` (story tracker in `docs/stories.md`)
- Inputs: `input/` (PDF, images, text); Outputs: `output/` (git-ignored)

## Current Pipeline (modules + driver)
- Use `driver.py` with recipes in `configs/recipes/`.
- **Primary recipe for Fighting Fantasy**: `recipe-ff-ai-ocr-gpt51.yaml` (GPT-5.1 AI-first OCR, HTML output)
- Legacy OCR ensemble recipe (`configs/recipes/legacy/recipe-ff-canonical.yaml`) is deprecated; do not use.
- **Canonical validator**: `validate_ff_engine_node_v1` (Node/Ajv) is the authoritative schema validator and should ship alongside `gamebook.json` to the game engine. It is generic across Fighting Fantasy books (not tuned to a specific title). Python `validate_ff_engine_v2` remains for forensics only.
- Other recipes: `configs/recipes/legacy/recipe-ocr.yaml`, `configs/recipes/recipe-text.yaml` (for reference/testing only)
- Legacy linear scripts were removed; use modules only.

## Modular Plan (story 015)
- Modules scanned from `modules/`; recipes select module ids per stage.
- Validator: `validate_artifact.py --schema <name> --file <artifact.jsonl>` (page_doc, clean_page, portion_hyp, locked_portion, resolved_portion, enriched_portion).

## Key Files/Paths
- Artifacts live under `output/runs/<run_id>/`.
- **Artifact organization**: Each module's artifacts are in `{ordinal:02d}_{module_id}/` folders directly in run_dir (e.g., `01_extract_ocr_ensemble_v1/pages_raw.jsonl`)
- **Final outputs**: `gamebook.json` stays in root for easy access
- **Game-ready package**: `output/runs/<run_id>/output/` (contains `gamebook.json` + `validator/` bundle + README)
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

**ARM64 + MPS is required only for legacy EasyOCR/ensemble runs.** The canonical GPT-5.1 OCR pipeline runs on any arch; use MPS only when running legacy OCR recipes or EasyOCR GPU smoke tests.

**Current canonical recipe**: `configs/recipes/recipe-ff-ai-ocr-gpt51.yaml` (GPT-5.1 AI-first OCR)
- HTML-native output, faster than legacy OCR ensemble
- Legacy `configs/recipes/legacy/recipe-ff-canonical.yaml` is deprecated and disabled

### Environment (required)
- **Canonical GPT-5.1 OCR**:
  - `pip install --no-cache-dir -r requirements.txt`
- **Legacy EasyOCR / OCR ensemble (optional)**:
  - `conda config --add envs_dirs /Users/cam/.conda_envs`
  - `conda create -n codex-arm-mps python=3.11 -y`
  - `conda activate codex-arm-mps`
  - `pip install --no-cache-dir -r requirements-legacy-easyocr.txt -c constraints/metal.txt`
  - Guard (legacy only): `python scripts/check_arm_mps.py` (must pass)
  - SHM-safe env (EasyOCR/libomp stability):
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
- 20pp smoke: `python driver.py --recipe configs/recipes/recipe-ff-ai-ocr-gpt51.yaml --settings configs/settings.ff-ai-ocr-gpt51-smoke-20.yaml --run-id ff-ai-ocr-gpt51-smoke-20 --output-dir /tmp/cf-ff-ai-ocr-gpt51-smoke-20 --force`
- Note: If smoke settings don't exist, create them based on the main recipe with reduced page ranges

### Smoke tests (quick reference)
- Canonical smoke (current pipeline): `configs/recipes/recipe-ff-ai-ocr-gpt51.yaml` + `configs/settings.ff-ai-ocr-gpt51-smoke-20.yaml`
- Offline fixture smoke (no external calls): `configs/recipes/recipe-ff-smoke.yaml` (uses `testdata/smoke/ff/`)
- Legacy/archived smoke: `configs/recipes/legacy/recipe-ocr-coarse-fine-smoke.yaml` and `configs/settings.ff-canonical-smoke*.yaml`

### Troubleshooting (must-read)
- **OMP SHM crash** (`Can't open SHM2`) — legacy EasyOCR only:
  - Ensure `codex-arm-mps` env + SHM-safe vars are set.
  - If it still fails, run outside any restricted/sandboxed shell or disable EasyOCR/torch paths.
- **MPS unavailable** (legacy EasyOCR): rerun env setup; `python scripts/check_arm_mps.py` must pass.
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
## Model Benchmarking (promptfoo)

We use [promptfoo](https://www.promptfoo.dev/) for evaluating AI model/prompt quality on pipeline tasks. Benchmark workspace lives in `benchmarks/`.

### Prerequisites
- **Node.js 22+** (24 LTS recommended). Promptfoo requires Node 22+. Installed via nvm.
- **promptfoo** installed globally: `npm install -g promptfoo` (v0.120.24+).
- Shell sessions need nvm loaded: `source ~/.nvm/nvm.sh && nvm use 24`.
- API keys: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, and `GEMINI_API_KEY` must be set.

### Workspace Structure
```
benchmarks/
├── tasks/           # promptfoo YAML configs (one per eval task)
├── prompts/         # Prompt templates with {{variable}} placeholders
├── golden/          # Hand-crafted reference data for scoring
├── input/           # Test input files (page images, etc.)
├── scorers/         # Python scoring scripts
├── results/         # JSON output from eval runs
└── scripts/         # Analysis helpers
```

### Running Benchmarks
```bash
# From the benchmarks/ directory:
source ~/.nvm/nvm.sh && nvm use 24 > /dev/null 2>&1

# Run a benchmark (no cache for reproducibility)
promptfoo eval -c tasks/image-crop-extraction.yaml --no-cache -j 3

# Save results to file
promptfoo eval -c tasks/image-crop-extraction.yaml --no-cache --output results/run-name.json

# View results in web UI
promptfoo view

# Override the judge/grader model
promptfoo eval -c tasks/image-crop-extraction.yaml --grader anthropic:messages:claude-opus-4-6
```

### Judge / Grader Model

**Default**: promptfoo uses `gpt-5` (OpenAI) for `llm-rubric` assertions when `OPENAI_API_KEY` is set.

**Our standard**: Use **`claude-opus-4-6`** as the judge for all evals. Rationale:
- The judge must be at least as capable as the models being tested.
- Cross-provider judging reduces same-provider bias.

Override per-eval in the YAML config:
```yaml
defaultTest:
  options:
    provider: anthropic:messages:claude-opus-4-6
```

**Provider prefixes**: `openai:`, `anthropic:messages:`, `google:` (uses `GEMINI_API_KEY`).

### Python Scorer Interface

Promptfoo calls `get_assert(output, context)` from Python scorer files:

```python
def get_assert(output: str, context: dict) -> dict:
    """
    Args:
        output: Raw model response text
        context: Dict with 'vars' (test variables), 'prompt', etc.
    Returns:
        {"pass": bool, "score": float 0-1, "reason": str}
    """
```

- Access test variables via `context["vars"]["variable_name"]`.
- `file://` in vars loads file *content*, not paths — use plain strings for paths the scorer will resolve itself.

### Dual Evaluation Pattern

Every eval should use both:
1. **Python scorer** — Deterministic, structural quality. Fast, reproducible, catches structural failures.
2. **LLM rubric** — Semantic quality (coherence, insight depth). Catches qualitative issues the structural scorer misses.

A test case passes only if *both* assertions pass.

### Pitfalls and Gotchas

- **`max_tokens` is NOT set by default for OpenAI models.** Always set `max_tokens` in provider config or outputs will truncate silently (producing invalid JSON).
- **`---` in prompt files is a prompt separator.** Use `==========` or another delimiter instead.
- **`file://` paths resolve relative to the config file**, not CWD.
- **`file://` in test vars loads content, not path.** If a scorer needs a file *path*, use a plain string without `file://` prefix.
- **Anthropic models wrap output in ```json blocks.** Scorers must strip markdown fences before JSON.parse.
- **Exit code 100 = test failures**, not system errors. This is normal.
- **`--dry-run` doesn't exist.** Use `--filter-first-n 1` to validate config with a single test case.
- **Concurrency**: Use `-j 3` as default (avoids rate limits while keeping runs reasonable).
- **Gemini extended thinking eats output tokens.** Set `maxOutputTokens: 16384` for all Gemini providers (4096 is insufficient — thinking tokens consume 3000+).
- **Gemini model IDs have no dated preview suffixes.** Use `gemini-2.5-flash`, `gemini-2.5-pro`, `gemini-3-pro-preview` (no `-preview-06-17` etc.).

### Adding a New Eval

When a new AI-powered module needs tuning:
1. Copy test input to `benchmarks/input/`
2. Create golden reference in `benchmarks/golden/` (hand-crafted, expert-validated)
3. Write prompt template in `benchmarks/prompts/` (use `{{var}}` placeholders)
4. Write Python scorer in `benchmarks/scorers/` (implement `get_assert(output, context)`)
5. Create promptfoo config in `benchmarks/tasks/` (providers x test cases x assertions)
6. Run eval, analyze results, iterate on prompts, pick winning model

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
- **Preferred workflow (diagnostic loop):** diagnose → write tests → fix → run tests → update `config.yaml` inside an existing run to re-run **only** the necessary modules, reusing prior successful artifacts for faster validation.
  - Example (edit run-local `config.yaml` to start from a later stage):
    ```yaml
    # output/runs/<run_id>/config.yaml
    start_from: extract_inventory   # only re-run from this stage forward
    allow_run_id_reuse: true
    ```
- **Schema stamping gotcha (critical):** `driver.py` *stamps* artifacts using `schemas.py`. Any output fields not declared in the schema **will be dropped** when stamping rewrites the JSONL. If you add new fields in a module output, **you must add them to the corresponding schema** (e.g., `PageHtml`) or they will disappear. Always verify the stamped artifact (`output/runs/<run_id>/.../*.jsonl`) contains the new fields after the stage completes.
- **Validation report HTML generation:** `validation_report.html` is produced by `tools/generate_forensic_html.py` when `validate_ff_engine_v2` runs with `forensics: true`. The JSON report (`validation_report.json`) lives in the run root and is the source of the HTML.

## Agent Memory: AI Self-Improvement Log

Treat this section as a living memory. When you discover a mistake, pitfall, or effective pattern during work, record it here so future sessions avoid repeating errors. Entry format: `YYYY-MM-DD — short title`: summary plus explanation including file paths.

### Effective Patterns
- 2026-01-17 — Story-first implementation with focused smoke checks: Implement in dependency order and validate each milestone with a targeted subset run before expanding.
- 2026-01-17 — Reuse existing modules first: Before building new logic, check if an existing module (even from a different recipe) can be reused or adapted. Mimicking battle-tested patterns avoids new bugs.
- 2026-01-24 — Dual evaluation catches what code can't: Python scorers measure structural quality (IoU, field coverage) but miss semantic issues. LLM rubric judges catch qualitative problems. Always use both in promptfoo evals.
- 2026-01-24 — Cross-provider judging reduces bias: Use Claude Opus 4.6 as default judge when evaluating models from OpenAI/Google.

### Known Pitfalls
- 2026-01-17 — Schema stamping drops undeclared fields: `driver.py` stamps artifacts using `schemas.py`. New fields not in the schema are silently dropped. Always add new output fields to the corresponding schema.
- 2026-01-17 — Stale .pyc files cause silent failures: Always `find modules/<module> -name "*.pyc" -delete` before integration testing a modified module.
- 2026-01-24 — VLM image box detection includes nearby text: VLM bounding boxes for photos often absorb captions, headers, and body text. Heuristic trimming is unreliable; systematic eval with golden data is needed.
- 2026-02-16 — promptfoo `max_tokens` trap: OpenAI providers silently truncate long outputs without `max_tokens` set, producing invalid JSON.
- 2026-02-16 — promptfoo `---` in prompts is a separator: Three dashes split one prompt into two fragments. Use `==========` instead.
- 2026-02-16 — Gemini extended thinking eats output tokens: Set `maxOutputTokens: 16384` for Gemini providers (4096 is insufficient).
- 2026-02-16 — Gemini model IDs: No dated preview suffixes. Use `gemini-2.5-flash`, `gemini-2.5-pro`, `gemini-3-pro-preview`.
- 2026-02-16 — promptfoo `raw` prompts bypass format translation: When using `raw:` prompt key, content is sent verbatim to every provider. Anthropic expects `type: "image"` (not `image_url`), Google expects `inlineData` (not `image_url`). Use JS prompt functions with `id: "file://..."` that detect `provider.id` and adapt the image content block format per provider.
- 2026-02-16 — GEMINI_API_KEY in wrong shell: If key is in `.zshrc` but promptfoo runs in bash, it won't be found. Export the key before running or add to `.bashrc`.
- 2026-02-16 — `file://` corrupts binary image data: promptfoo's `file://` loader corrupts binary JPEG when interpolated into prompt templates. Pre-encode images as base64 data URI text files (`data:image/jpeg;base64,...`) stored as `.b64.txt`.

### Lessons Learned
- 2026-01-17 — Cost discipline on OCR: Treat OCR as expensive and single-run. Iterate downstream by reusing OCR artifacts, not re-running OCR.
- 2026-01-24 — Systematic eval beats ad-hoc iteration: After ~10 rounds of heuristic tuning on image cropping without converging, switching to a promptfoo-based eval with golden data was the right move.
- 2026-01-17 — Escalate-to-success loops need caps: Every escalation loop must have a max retry/budget cap to prevent infinite loops.
- 2026-02-16 — Provider-specific image format handling: OpenAI uses `{type: "image_url", image_url: {url: "data:..."}}`, Anthropic uses `{type: "image", source: {type: "base64", media_type: "...", data: "..."}}`, Google uses `{inlineData: {mimeType: "...", data: "..."}}`. For multi-provider evals, use a shared JS helper that adapts format based on `provider.id`.
- 2026-02-16 — Simpler prompts win for stronger models: Gemini 3 Pro scored best with the simplest (baseline) prompt. Overly prescriptive prompts (strict-exclude) can hurt strong models while helping weaker ones. Always test prompt complexity as a variable.
