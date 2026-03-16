# AGENTS.md — codex-forge

Source of truth for all AI agents working on codex-forge (Claude Code, Cursor, Gemini CLI).
Read this file at the start of every session.

> **Mission:** Codex-forge is the **intake R&D lab for Dossier**. It solves hard
> format conversion problems — scanned PDFs, images, weird document formats — one
> at a time. Each converter is perfected here, then graduated into Dossier when ready.
>
> **The Ideal (`docs/ideal.md`) is the most important document in this project.**
> It defines what codex-forge should be with zero limitations. Every compromise
> in `docs/spec.md` carries a detection mechanism for when it's no longer needed.
> When in doubt: "Does this move us toward the Ideal?"
>
> **Preferences exist at two levels.** Vision-level preferences (Central Tenets)
> persist across all implementations. Compromise-level preferences die when their
> compromise is eliminated. Know which level you're working at.

## Central Tenets (Vision-Level Preferences)

0. **Traceability is the Product** — Every piece of extracted text traces back to source page, OCR engine, confidence score, and processing step. Without provenance, output is noise.
1. **AI-First, Code-Second** — Use AI (VLMs, LLMs) for intelligence (extraction, classification, understanding). Use code for orchestration, storage, validation, and glue.
2. **Eval Before Build** — Before implementing complex logic, measure what SOTA can do. Record all attempts in `docs/evals/registry.yaml`. Never re-try blocked approaches without new evidence.
3. **Fidelity to Source** — The pipeline preserves the source document faithfully. OCR errors, formatting loss, and missing content are bugs, not acceptable losses.
4. **Modular by Default** — Swappable modules, YAML-driven recipes. A new document type needs a new recipe, not new code.
5. **Inspect the Artifacts** — Tests passing is necessary but not sufficient. Always visually inspect outputs before marking Done.

## Core Agent Mandates

- **ACTIVE PROJECT — NO BACKWARDS COMPAT**: Zero external users. Change things directly. No migration paths, no deprecation shims.
- **Critical Pushback Required**: Push back when an idea is worse than what exists. Sycophantic agreement is harmful.
- **No Implicit Commits**: NEVER commit or push unless explicitly requested.
- **Security First**: NEVER stage secrets, API keys, or credentials.
- **Verify, Don't Assume**: Check files and dependencies exist before using them.
- **Eval-First Engineering**: Test the simplest AI approach first. If SOTA succeeds in one call, there's nothing to build. Never conclude "AI can't do this" from a cheap model's failure.
- **The Definition of Done:** A story or task is **NOT complete** until:
    1. It runs successfully through `driver.py` in a real (or partial resume) pipeline.
    2. Produced artifacts exist in `output/runs/`.
    3. **Manual Data Inspection**: You have opened the artifacts (JSON/JSONL) and manually verified that the specific data being added/fixed is accurate and high-quality.
    4. You have reported the specific artifact paths and sample data verified to the user.
- **Default to coherent scope expansion:** If exploration reveals important adjacent work that is necessary to actually satisfy the story's goal, expand the story modestly and update the story file/work log instead of treating it as "out of scope." For larger expansions, present the recommendation to the user for approval before implementing. Only split work into a new story when it is materially distinct, meaningfully larger in blast radius, or would make validation unclear.
- **Estimate in relative effort, not human time:** Unless the user explicitly asks for calendar estimates, express effort as relative size (`XS`, `S`, `M`, `L`, `XL` or equivalent), not hours/days. Optimize scope decisions for what an AI can implement and validate coherently, not for human sprint capacity.
- **Inspect outputs, not just logs:** A green or non-crashing run is not evidence of correctness. Always manually open produced artifacts and check for logical errors (e.g., garbled text, broken tables, missing data, incorrect values).
- **Precompute context for readers:** Prefer computing metrics (e.g., costs/usage/quality signals) at the stage that produces them and write them into artifacts/logs (e.g., `instrumentation.json`) instead of relying on downstream recomputation.
- **Graduate, don't accumulate:** When a converter is stable and proven, plan its migration to Dossier. Codex-forge stays focused on unsolved problems.
- **Consistency policy must be explicit:** When solving document-consistency or normalization problems, emit inspectable policy artifacts (for example `pattern_inventory`, `consistency_plan`, `conformance_report`) instead of hiding conventions in prompts. See `docs/runbooks/document-consistency-planning.md`.

## Subagent Strategy

| Task | Model | Rationale |
|------|-------|-----------|
| File search, glob, grep, simple reads | **Haiku** | Fast, cheap, mechanical |
| Write a single focused module/script | **Sonnet** | Good code quality, fast enough |
| Multi-file refactor, architecture decisions | **Opus** | Needs full context and judgment |
| Research/exploration across codebase | **Sonnet** | Good at synthesis, thorough |
| Writing tests for existing code | **Sonnet** | Needs to understand contracts |
| Reviewing/validating generated code | **Opus** | Quality gate, catches subtle issues |

**Guidelines:** Parallelize independent work. Opus orchestrates, delegates, reviews — never blindly trusts. Use subagents for large-output tasks to protect main context. Fail fast: bad subagent output → adjust approach, don't retry same prompt.

## Skills

Canonical location: `.agents/skills/` — works across Claude Code, Cursor, Gemini CLI.
- `.claude/skills` and `.cursor/skills` are symlinks to `.agents/skills`
- `skills/` at repo root is a symlink for backwards compatibility
- `.gemini/commands/*.toml` are generated wrappers — run `scripts/sync-agent-skills.sh` after changes
- Use `/align` for post-change methodology sweeps across the Ideal, spec, build map, stories, and evals
- Use `/triage` for read-only full sweeps or scoped backlog / inbox / eval triage
- To create a new skill: `/create-cross-cli-skill`

## Story Lifecycle

**Statuses:** Draft → Pending → In Progress → Done | Blocked
- **Draft** — Skeleton with goal/notes. NOT buildable. Needs detailed ACs and tasks before `/build-story`.
- **Pending** — Fully detailed (ACs, tasks, files to modify). Ready for `/build-story`.
- **In Progress** — Active work.
- **Done** — All checks pass, work log current, CHANGELOG updated, eval registry updated if applicable.
- **Blocked** — Waiting on dependency or decision.

**Story IDs are identifiers, not sequence numbers.** New stories get max+1. Order via `Depends On`, not ID. Never use letter suffixes.

**Workflow:** `/triage` (when useful) → `/create-story` → `/build-story` → `/validate` → `/mark-story-done`

**Decision discipline:** Hard-to-reverse architecture, workflow, schema, or cross-cutting project decisions belong in `docs/decisions/`. Stories affecting those areas should cite relevant ADRs in `Decision Refs`, or explicitly note that none were found after search.

**Central Tenet Verification** — Every story includes a tenet checklist (T0-T5). Must be verified before marking Done.

**Scope management default** — Stories are not fixed-size human sprint tickets. If a modest amount of tightly coupled work is discovered during implementation and is required to make the story actually succeed, absorb it into the current story and update the story document. If the expansion is larger, riskier, or changes the goal, recommend the scope change explicitly before proceeding.

## Docs

- `docs/ideal.md` — The Ideal: zero-limitation north star
- `docs/build-map.md` — System structure, compromise progress, input coverage, graduation tracking
- `docs/spec.md` — Active compromises with detection evals
- `docs/decisions/` — ADRs for hard-to-reverse architecture, workflow, schema, and cross-cutting project decisions
- `docs/evals/registry.yaml` — Eval scores, targets, attempt history
- `docs/requirements.md` — Functional requirements
- `docs/stories.md` — Story index (130+ stories)
- `docs/stories/` — Individual story files with ACs, tasks, work logs
- `docs/scout.md` — Scout expedition index
- `docs/ai-learning-log.md` — AI self-improvement log (patterns, pitfalls, lessons)
- `tests/fixtures/formats/_coverage-matrix.json` — Machine-readable format inventory (16 formats)
- `docs/runbooks/` — Operational runbooks for repeatable workflows
- `CHANGELOG.md` — Release history (CalVer `YYYY-MM-DD-NN` format)

## Generality & Non-Overfitting
- Optimize for an input *category* (e.g., scanned genealogy books), not a single PDF/run.
- Do not hard-code page IDs, document-specific strings, or one-off replacements in pipeline code.
- Specialization must be explicit and scoped:
  - Prefer recipe/module params (knobs) over branching logic.
  - If something truly is recipe-specific, keep it in a clearly scoped module and document the scope + knobs.
- **Architecture goal (reusability):** Keep upstream intake/OCR modules as generic as possible. Push format-specific heuristics downstream into format-aware modules or recipe-scoped adapters.
- Prefer *signals and loops* over brittle fixes: detect → validate → targeted escalate → validate.
- If adding deterministic corrections, they must be generic (class-based, conservative), opt-in by default, and preserve original text/provenance.
- Validate across multiple documents/runs; add regression checks on *patterns* (coverage, bad-token occurrence, empty text rate), not exact strings.

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
PYTHONPATH=. python modules/<stage>/<module_id>/main.py \
  --input /path/to/test_input.jsonl \
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

**Artifact reuse policy**: You MAY reuse artifacts from a previous run (e.g., expensive OCR results) to save time/cost using a resume recipe or `load_artifact_v1`. However, you MUST ensure that the reused IDs and schemas are consistent with the current run to prevent "megasection" or "mismatch" failures. Before treating an older run as a trusted upstream or review source, check `output/run_health.jsonl` and `output/run_assessments.jsonl` (or `python tools/run_registry.py check-reuse --run-id <run_id> --scope <scope>`). The CLI auto-detects the shared project `output/` root from the current repo/worktree; only pass `--output-root` when you need to override that default. A run is never globally "known good"; trust must be scope-specific.

```bash
# Completion testing - must succeed for work to be "done"
find modules/<stage>/<module_id> -name "*.pyc" -delete
python driver.py --recipe configs/recipes/<recipe>.yaml \
  --run-id test-run --start-from <stage> --force
ls -lh output/runs/test-run/<ordinal>_<module_id>/
python3 -c "import json; [print(json.loads(line)) for line in open('output/runs/test-run/...')][:5]"
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
- ✅ "Implemented OCR extraction. Inspected `output/runs/.../01_extract_ocr/pages.jsonl` - 293 pages with populated text (e.g., page 9: 1295 chars, table structure preserved). Quality verified."
- ✅ "Fixed duplicates. Checked `output/runs/.../03_structure/structured.jsonl` - was 3 sections claiming id='1', now 1 (page 16, correct). Resolved."
- ✅ "Added crop detection. Sampled 10 from `output/runs/.../02_illustrate/crops.json` - 8 illustrations, 2 diagrams. Page 42: correct bounding box, no text contamination."

## Validation & Stage Resolution

### Stage resolution discipline
A stage must resolve before the next runs. Resolution means either (a) it meets its coverage/quality goal or (b) it finishes a defined escalate→validate loop and records unresolved items prominently. Do not silently push partial outputs downstream.

Examples:
- Section splitting must complete escalation (retries, stronger models) until coverage is acceptable or retry cap is hit
- Boundary verification must pass or emit explicit failure markers before extraction starts
- Extraction must retry/repair flagged portions; unresolved portions carry explicit error records (not empty text)
- **Stub-fatal policy:** Default is fatal on stubs—pipelines must fail unless `allow_stubs` is explicitly set

### Diagnostic validation
For every missing/no-text warning, emit a per-item provenance trace walking upstream artifacts showing where content disappeared. Traces must include artifact paths, page/element IDs, and text snippets. No manual artifact edits—fix code/logic and regenerate.

### Escalate-to-success loop (applies to every stage)
- Default pattern: **detect/code → validate → targeted escalate → validate**, repeat until 100% success or a retry/budget cap is hit.
- Each pass must use the latest artifacts (hash/mtime guard to prevent stale inputs).
- Escalation outputs become the new gold standard for that scope (do not fall back to earlier OCR/LLM results).
- Surface evidence automatically: emit per-item presence/reason flags and small debug bundles for failures.
- **Escalation caps are mandatory:** Every escalation loop must have a maximum iteration/retry/budget cap to prevent infinite loops. Examples: `max_retries`, `budget_pages`, `max_repairs`, `max_candidates`. If a stage hits its cap without reaching 100% accuracy, it must fail explicitly (not silently pass partial results).

## Escalation Strategy (known-good pattern)
When a first-pass run leaves quality gaps, escalate in a controlled, data-driven loop:
1. **Baseline**: Run the fastest/cheapest model with conservative prompts.
2. **Detect issues**: Programmatically flag suspect items (low alpha ratio, empty text, garbled tables, etc.).
3. **Targeted re-read**: Re-run only the flagged items with a stronger multimodal model and a focused prompt that embeds the minimal context directly (page image + raw_text in the prompt; no external attachments).
4. **Rebuild & revalidate**: Rebuild downstream artifacts from the patched portions and re-run validation.
5. **Verify artifacts**: Spot-check the repaired items and confirm warnings/errors are cleared.
Avoid manual text edits; use this loop to stay generic, reproducible, and format-agnostic (see “Generality & Non-Overfitting”).

## Patching System (Last Resort)
When a document strongly defies conventions and generic/escalation passes still fail, use `*.patch.json` files to override specific outputs. Patches are applied by `driver.py` outside modules, keyed by `apply_before`/`apply_after` with a module_id. Rules:
- Patches must be minimal, scoped, and documented in the story work log.
- Preserve provenance; do not hand-edit artifacts outside the pipeline.
- Patch failures emit warnings (not errors) in `pipeline_events.jsonl`.

## Repo Map
- `modules/<stage>/<module_id>/` — `module.yaml` + `main.py` (no registry file)
- `driver.py` — pipeline orchestrator; `schemas.py` — data schemas; `validate_artifact.py` — schema validator
- `configs/recipes/` — YAML recipes; `configs/settings.*.yaml` — run settings
- `benchmarks/` — promptfoo evals (tasks, golden, scorers, prompts)
- `tests/` — pytest suite (79 files)
- `scripts/` — utility scripts
- `input/` — source PDFs/images (git-ignored); `output/` — pipeline artifacts (git-ignored)

## Pipeline
- `driver.py` executes recipes from `configs/recipes/`. Modules scanned from `modules/`; recipes select module IDs per stage.
- Artifacts live under `output/runs/<run_id>/{ordinal:02d}_{module_id}/`.
- Pipeline metadata: `pipeline_state.json`, `pipeline_events.jsonl` in run root.
- Driver auto-generates a fresh `run_id` per run; reuse is opt-in via `--allow-run-id-reuse`.
- Validator: `validate_artifact.py --schema <name> --file <artifact.jsonl>`.
- Legacy recipes in `configs/recipes/legacy/` — preserved for reference, not active use.

## Models / Dependencies
- OpenAI API (set `OPENAI_API_KEY`).
- Tesseract on PATH (or set `paths.tesseract_cmd`).
- **Model Selection Guidelines**:
  - **For maximum intelligence/complex reasoning**: Use `gpt-5` (or latest flagship model)
  - **For speed/value**: Use `gpt-4.1-nano` or `gpt-4.1-mini` (fastest and cheapest)
  - **Avoid defaulting to `gpt-4o`**: It's been supplanted by `gpt-5` for smarts, and mini/nano models for speed/value
  - **Reference**: [OpenAI Models Documentation](https://platform.openai.com/docs/models) - Check this for latest models, capabilities, and pricing
- Defaults: `gpt-4.1-mini` with optional boost `gpt-5`; see scripts/recipes.

## Running & Monitoring

**See [docs/RUNBOOK.md](docs/RUNBOOK.md) for full execution instructions.**

### Key Developer Commands
- **Resume a run:** `scripts/run_driver_monitored.sh ... --start-from <stage>`
- **Smoke Test:** `make smoke`

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

## Etiquette
- Update the relevant story work log for any change or investigation.
- Keep responses concise; cite file paths when referencing changes.
- **Impact-first updates (required):** When reporting progress, don’t just summarize what changed—also state how it improved (or failed to improve) outcomes.
  - Include a short “Impact” block with:
    - **Story-scope impact:** What acceptance criteria/tasks this unblocked or de-risked.
    - **Pipeline-scope impact:** What got measurably better downstream (coverage, fewer escalations, fewer bad tokens, cleaner boundaries, etc.).
    - **Evidence:** 1–3 concrete artifact paths checked and what you saw there.
    - **Next:** The next highest-leverage step and what would falsify success.
  - If results are mixed, say so explicitly and name the remaining failure mode(s).
- **Debugging discipline:** when diagnosing issues, inspect the actual data/artifacts at each stage before changing code. Prefer evidence-driven plans (e.g., grep/rg on outputs, view JSONL samples) over guess-and-edit loops. Document what was observed and the decision that follows.
- **Reuse working patterns first:** before inventing a new solution, look for an existing working pattern in this repo (code, UX, helper). Read it, understand it, and adapt with minimal changes.
- **Preferred workflow (diagnostic loop):** diagnose → write tests → fix → run tests → update `config.yaml` inside an existing run to re-run **only** the necessary modules, reusing prior successful artifacts for faster validation.
  - Example (edit run-local `config.yaml` to start from a later stage):
    ```yaml
    # output/runs/<run_id>/config.yaml
    start_from: <stage>   # only re-run from this stage forward
    allow_run_id_reuse: true
    ```
- **Schema stamping gotcha (critical):** `driver.py` *stamps* artifacts using `schemas.py`. Any output fields not declared in the schema **will be dropped** when stamping rewrites the JSONL. If you add new fields in a module output, **you must add them to the corresponding schema** or they will disappear. Always verify the stamped artifact contains the new fields after the stage completes.

## AI Learning Log

See [`docs/ai-learning-log.md`](docs/ai-learning-log.md) — living memory of effective patterns, known pitfalls, and lessons learned across sessions. Update it when you discover something worth remembering.
