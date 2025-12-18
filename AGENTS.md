# AGENTS GUIDE — codex-forge

This repo processes scanned (or text) books into structured JSON, using modular stages driven by LLMs.

## Prime Directives
- **Do NOT run `git commit`, `git push`, or modify remotes unless the user explicitly requests it.**
- System is in active development (not production); do not preserve backward compatibility or keep legacy shims unless explicitly requested.
- AI-first: the AI owns implementation and self-verification; humans provide requirements and oversight. Do not report work "done" without testing/validation against requirements and story acceptance criteria.
- **100% Accuracy Requirement:** The final artifacts (gamebook.json) are used directly in a game engine. **If even ONE section number or choice is wrong, the game is broken.** Partial success on section coverage or choice extraction is a complete failure. Pipeline must either achieve 100% accuracy or fail explicitly with clear diagnostics. There is no "good enough" - it's perfect or broken.
- Keep artifacts append-only; never rewrite user data or outputs in `output/` or `input/`.
- Artifacts are write-only: never silently patch; any manual or auto patch must be emitted as a new artifact with traceable intent.
- Default to `workspace-write` safe commands; avoid destructive ops (`rm -rf`, `git reset --hard`).
- Preserve non-ASCII only if the file already contains it.
- Do not patch artifacts by hand to hide upstream issues; fix the root cause and regenerate. Any temporary manual edit must be explicit, traceable, and leave original inputs untouched.
- Never "fix" run artifacts by hand: all data corrections must be structural/code changes and reproducible; regenerate outputs instead of manual edits.
- Every stage must resolve before the next runs: either reach its coverage/quality target or finish a defined escalate→validate loop and clearly mark unresolved items. Do not pass partially-resolved outputs downstream without explicit failure markers.
- **Always inspect outputs, not just logs:** After every meaningful run, manually open the produced artifacts (JSON/JSONL) and check they match expectations (counts, sample content). A green or non-crashing run is not evidence of correctness; if outputs are empty/suspicious, stop and fix before proceeding.

## Generality & Non-Overfitting (Read First)
- Optimize for an input *category* (e.g., Fighting Fantasy scans), not a single PDF/run.
- Do not hard-code page IDs, book-specific strings, or one-off replacements (e.g., `staMTNA→STAMINA`) in pipeline code.
- Specialization must be explicit and scoped:
  - Prefer recipe/module params (knobs) over branching logic.
  - If something truly is recipe-specific, keep it in a clearly scoped module and document the scope + knobs.
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

### After Building: Verify Actual Results
**DO NOT declare success just because code runs without errors.**

This is a **data pipeline** project. Every stage produces **artifacts** (JSONL files, JSON files). After implementing any change:

1. **MANDATORY: Inspect actual output artifacts**
   - Open the files: `output/runs/<run_id>/{ordinal:02d}_{module_id}/<artifact>.jsonl` for intermediate artifacts (e.g., `01_extract_ocr_ensemble_v1/pages_raw.jsonl`)
   - Final outputs (e.g., `gamebook.json`) are in root: `output/runs/<run_id>/gamebook.json`
   - Read sample entries (5-10 minimum)
   - Verify the **data content**, not just that the file exists

2. **Verify against expectations**
   - Does the text look correct?
   - Are the extracted values accurate?
   - Do counts/statistics match what you expect?
   - Compare before/after if fixing a bug

3. **Complete the loop: Implement → Verify → Iterate**
   - If artifacts reveal issues, **fix and verify again**
   - Don't stop at "code runs" - stop at "output is correct"
   - Document what you observed in artifacts (include samples in work log)

**Examples of what NOT to do:**
- ❌ "I've implemented the text extraction. The module runs successfully." (Did you read the extracted text?)
- ❌ "Fixed the duplicate detection. No errors." (Are there still duplicates in the output?)
- ❌ "Added section classification. Tests pass." (What does the actual classification data look like?)

**Examples of what TO do:**
- ✅ "Implemented text extraction. Inspected `03_portionize_llm_v1/window_hypotheses.jsonl` - all 293 portions now have populated `raw_text` (e.g., portion 9 has 1295 chars: 'There is also a LUCK box...'). Text quality looks good."
- ✅ "Fixed duplicate detection. Checked `06_enrich_v1/portions_enriched.jsonl` - previously had 3 portions claiming section_id='1', now only 1 (page 16, correct text). Issue resolved."
- ✅ "Added classification. Sampled 10 sections from `gamebook.json` - 8 correctly classified as 'gameplay', 2 as 'rules'. Spot-checked section 42: classified as 'gameplay', text contains combat ('SKILL 7 STAMINA 9'), correct."

**The pattern:**
1. Build/fix code
2. Run pipeline
3. **Open and read the actual artifact files**
4. Verify data quality with specific examples
5. If issues found → return to step 1
6. Only declare success when **data is correct**, not when **code runs**

**Validation must be diagnostic:** For every missing/no-text/no-choice warning or error, emit a per-item provenance trace that walks upstream artifacts (OCR → elements/elements_core → boundaries → portions) and shows where content disappeared or was absent. The trace should make it obvious which stage caused loss (e.g., text present in elements but missing after portions ⇒ extraction issue; text absent from OCR ⇒ source/OCR issue; text truly absent ⇒ likely real empty section). Traces must include artifact paths, page/element IDs, and short text snippets where available. No manual artifact edits—fix code/logic and regenerate.

**Stage resolution discipline:** A stage must resolve before the next runs. Resolution means either (a) it meets its coverage/quality goal (e.g., all sections found, ordering valid) or (b) it finishes a defined escalate→validate loop and records the unresolved items prominently in artifacts/metadata. Do not silently push partial “best-effort” outputs downstream. Examples:
- Section splitting must complete its own escalation (retries, stronger models, focused re-reads) until coverage is acceptable or the cap is hit; only then assemble boundaries.
- Boundary verification must pass or emit explicit failure markers before extraction starts.
- Extraction must retry/repair flagged portions; unresolved portions must carry explicit error records (not empty text) so validators/builders surface them.
- Stub-fatal policy: stub backfills are for forensics only. Default is **fatal on stubs**—pipelines must fail unless `allow_stubs` is explicitly set, and the allowance must be recorded in provenance/validation so missing content cannot be hidden.

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

- Write prompts at the document/recipe level (keep them generic; see “Generality & Non-Overfitting”).
- Prefer simple, structural instructions over brittle heuristics:
  - ✅ “This is a Fighting Fantasy gamebook with front matter, rules, then numbered sections 1–400. Find section headers.”
  - ❌ Complex regex/keyword rule stacks and confidence micro-tuning.
- Use code for deterministic transforms; use AI for semantic structure (classification, boundary detection, context).

### Why This Matters
- This project processes books into structured data. **Wrong data is worse than no data.**
- A module that runs without errors but produces garbage output is a **silent failure**.
- Users trust the output. If the AI doesn't verify it, **bad data propagates downstream**.
- The deep dive we did on story 031 revealed issues at every stage - **issues that only became obvious when we manually inspected artifacts**.
- Validation must surface evidence automatically. On any validation failure or warning (missing text/choices/sections), emit traces that show where data was lost (e.g., boundary source, start element text/page, upstream artifact paths) so an AI or human can see the root cause without manual spelunking.

**You own the quality of your output, not just the quality of your code.**

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
- Use `driver.py` with recipes in `configs/recipes/`. Examples: `recipe-ff-canonical.yaml`, `recipe-ocr.yaml`, `recipe-text.yaml`.
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

## Environment Awareness

**Always run on ARM64 + MPS (GPU) by default**

- Create/refresh env (Metal-friendly pins live in requirements.txt + constraints/metal.txt):
  - `conda create -n codex-arm-mps python=3.11`
  - `conda activate codex-arm-mps`
  - `pip install --no-cache-dir -r requirements.txt -c constraints/metal.txt` (pulls torch==2.9.1 / torchvision==0.24.1 / Pillow<13)
- Activate env: `source ~/miniforge3/bin/activate codex-arm-mps`
- Guard: `python scripts/check_arm_mps.py` (fails if not arm64 or MPS unavailable)
- SHM-safe env (EasyOCR): `KMP_USE_SHMEM=0 KMP_CREATE_SHMEM=FALSE OMP_NUM_THREADS=1 KMP_AFFINITY=disabled KMP_INIT_AT_FORK=FALSE`
- GPU sanity (5pp EasyOCR-only): `python driver.py --recipe configs/recipes/recipe-ff-canonical.yaml --settings configs/settings.easyocr-gpu-test.yaml --end-at intake --run-id cf-easyocr-mps-5 --output-dir /tmp/cf-easyocr-mps-5 --force`
- After any GPU smoke, verify EasyOCR actually ran on GPU:  
  `python scripts/regression/check_easyocr_gpu.py --debug-file /tmp/cf-easyocr-mps-5/ocr_ensemble/easyocr_debug.jsonl`
- Shortcut: `./scripts/smoke_easyocr_gpu.sh /tmp/cf-easyocr-mps-5` (run + check in one step)
- Smoke pipeline (5pp quick run): `python driver.py --recipe configs/recipes/recipe-ff-canonical.yaml --settings configs/settings.ff-canonical-smoke-5.yaml --run-id ff-canonical-smoke-5 --output-dir /tmp/cf-ff-canonical-smoke-5 --force`
- If EasyOCR debug shows `gpu: false`, you are on the wrong env or missing Metal torch—switch to `codex-arm-mps`.
- Expected warning: `pin_memory not supported on MPS` from torch DataLoader is benign.

## Safe Command Examples
- Inspect status: `git status --short`
- List files: `ls`, `rg --files`
- View docs: `sed -n '1,120p' docs/stories/story-015-modular-pipeline.md`
- Run validator: `python validate_artifact.py --schema portion_hyp_v1 --file output/...jsonl`
- Dry-run the canonical 20-page recipe: `python driver.py --recipe configs/recipes/recipe-ff-canonical.yaml --dry-run`
- **Monitored full run (preferred, streams progress)**:
  - `scripts/run_driver_monitored.sh --recipe configs/recipes/recipe-ff-canonical.yaml --settings configs/settings.ff-canonical-smoke-5.yaml --run-id ff-canonical-smoke-5 --output-dir output/runs -- --instrument`
- **Attach monitoring to an existing run** (requires a pidfile containing the driver PID):
  - `scripts/monitor_run.sh output/runs/<run_id> output/runs/<run_id>/driver.pid 5`
- Section coverage check (map + backfill + fail on missing): `python modules/adapter/section_target_guard_v1/main.py --inputs output/runs/ocr-enrich-sections-noconsensus/portions_enriched.jsonl --out /tmp/portions_enriched_guard.jsonl --report /tmp/section_target_report.json`
- Legacy map/backfill adapters are obsolete; use `section_target_guard_v1` (no backward compatibility maintained).
- **Dashboard Testing**: Serve from repo root (`python -m http.server 8000`) and access via `http://localhost:8000/docs/pipeline-visibility.html`. Do not use `file://` URIs as they block CORS/fetch.
- **Sandbox caveat (Apple Vision OCR):** On some setups, Apple Vision OCR may fail under restricted/sandboxed execution with `sysctlbyname for kern.hv_vmm_present failed`. If that happens, rerun outside the sandbox / with full host permissions, or disable the `apple` engine for that run.

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
