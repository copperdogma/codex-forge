# codex-forge
AI-first, modular pipeline for turning scanned books into structured JSON with full traceability.

## Pipeline Architecture

The pipeline follows a 5-stage model:

1. **Intake → IR (generic)**: PDF/images → structured elements (Unstructured library provides rich IR with text, types, coordinates, tables)
2. **Verify IR (generic)**: QA checks on completeness, page coverage, element quality
3. **Portionize (domain-specific)**: Identify logical portions (CYOA sections, genealogy chapters, textbook problems) and reference IR elements
4. **Augment (domain-specific)**: Enrich portions with domain data (choices/combat for CYOA, relationships for genealogy)
5. **Export (format-specific)**: Output to target format (FF Engine JSON, HTML, Markdown) using IR + augmentations

Steps 1-2 are universal across all document types. Steps 3-4 vary by domain (gamebooks vs genealogies vs textbooks). Step 5 is tied to output requirements (precise layout for PDF, simplified for Markdown).

**Reusability goal:** Keep upstream intake/OCR modules as generic as possible. Prefer pushing booktype-specific heuristics/normalization (e.g., gamebook navigation phrase canonicalization, FF conventions) downstream into booktype-aware portionize/extract/enrich/export modules or recipe-scoped adapters so the OCR stack can be reused across book types.

The **Intermediate Representation (IR)** stays unchanged throughout; portionization and augmentation annotate/reference it rather than transforming it.

## What it does (today)
- Ingest PDF or page images → structured element IR (Unstructured or OCR-based)
- Multimodal LLM cleaning → per-page clean text + confidence
- Sliding-window portionization (LLM, optional priors, multimodal) → portions reference IR elements
- Consensus/dedupe/normalize, resolve overlaps, guarantee coverage
- Assemble per-portion JSON (page spans, source images, raw_text from IR)
- Run outputs stored under `output/runs/<run_id>/` with manifests and state

## Repository layout
- CLI modules/scripts: `pages_dump.py`, `clean_pages.py`, `portionize.py`, `consensus.py`, `dedupe_portions.py`, `normalize_portions.py`, `resolve_overlaps.py`, `build_portion_text.py`, etc.
- `docs/requirements.md`: system requirements
- `snapshot.md`: current status and pipeline notes
- `output/`: git-ignored; run artifacts live at `output/runs/<run_id>/`
  - **Artifact organization**: Each module has its own folder `{ordinal:02d}_{module_id}/` (e.g., `01_extract_ocr_ensemble_v1/`) containing its artifacts
  - **Final outputs**: `gamebook.json` stays in root for easy access
  - **Pipeline metadata**: `pipeline_state.json`, `pipeline_events.jsonl`, `snapshots/` in root
- `settings.example.yaml`: sample config
- Driver snapshots: each run writes `snapshots/` (recipe.yaml, plan.json, registry.json, optional settings/pricing/instrumentation configs) and records paths in `output/run_manifest.jsonl` for reproducibility.
- Shared helpers for module entrypoints live in `modules/common/` (utils, OCR helpers).

## Modular driver (current)
- Modules live under `modules/<stage>/<module_id>/`; recipes live in `configs/recipes/`.
- Driver orchestrates stages, stamps artifacts with schema/module/run IDs, and tracks state in `pipeline_state.json`.
- Swap modules by changing the recipe, e.g. OCR vs text ingest.

### Fighting Fantasy Book Structure

**Running Headers (Section Ranges):**
- Fighting Fantasy gamebooks use **running headers** in the upper corners of gameplay pages
- **Left page (L)**: Shows section range (e.g., "9-10", "18-21") indicating which sections are on that page
- **Right page (R)**: Shows single section number (e.g., "22") or range indicating sections on that page
- These are **NOT page numbers** - they indicate which gameplay sections (1-400) appear on the page
- Format: Either ranges like "X-Y" (sections X through Y) or single numbers like "Z" (section Z only)
- Position: Upper outside corners (top-left for left pages, top-right for right pages)

**Coordinate System Note:**
- OCR engines may use different coordinate systems (standard: y=0=top, inverted: y=0=bottom)
- Running headers at top corners may have high y values (0.9+) if coordinate system is inverted
- Pattern detection must account for this when identifying top vs bottom positions

### Legacy OCR Ensemble Recipe Reference (Archived)

**Current canonical recipe**: `configs/recipes/recipe-ff-ai-ocr-gpt51.yaml` (GPT-5.1 AI-first OCR, HTML-first output).
The legacy OCR-ensemble recipe is archived at `configs/recipes/legacy/recipe-ff-canonical.yaml`; the module list below is preserved for historical reference.

#### Intake Stage

**01. `extract_ocr_ensemble_v1`** (Code + AI escalation)
- **What it does**: Runs multiple OCR engines (Tesseract, EasyOCR, Apple Vision, PDF text) in parallel and combines results with voting/consensus
- **Why**: Different engines excel at different fonts/layouts; ensemble improves accuracy
- **Try**: Code (multi-engine OCR)
- **Validate**: Code (disagreement scoring)
- **Escalate**: AI (GPT-4V vision transcription for high-disagreement pages)

**02. `easyocr_guard_v1`** (Code)
- **What it does**: Validates that EasyOCR produced text for sufficient pages
- **Why**: EasyOCR is primary engine; missing output indicates critical failure
- **Type**: Code-only validation guard

**03. `pick_best_engine_v1`** (Code)
- **What it does**: Selects the best OCR engine output per page based on quality metrics, preserves standalone numeric headers from all engines
- **Why**: Reduces noise while preserving critical section headers that might only appear in one engine
- **Type**: Code-only selection

**04. `inject_missing_headers_v1`** (Code)
- **What it does**: Scans raw OCR engine outputs for numeric headers (1-400) missing from picked output and injects them
- **Why**: Critical for 100% section coverage; headers can be lost during engine selection
- **Type**: Code-only injection

**05. `ocr_escalate_gpt4v_v1`** (AI)
- **What it does**: Re-transcribes high-disagreement or low-quality pages using GPT-4V vision model
- **Why**: Vision models can read corrupted/scanned text that OCR engines miss
- **Type**: AI escalation (targeted, budget-capped)

**06. `merge_ocr_escalated_v1`** (Code)
- **What it does**: Merges original OCR pages with escalated GPT-4V pages into unified final OCR output
- **Why**: Creates single authoritative OCR artifact for downstream stages
- **Type**: Code-only merge

**07. `reconstruct_text_v1`** (Code)
- **What it does**: Merges fragmented OCR lines into coherent paragraphs while preserving section boundaries
- **Why**: Cleaner text improves downstream AI accuracy and human readability
- **Type**: Code-only reconstruction

**08. `pagelines_to_elements_v1`** (Code)
- **What it does**: Converts pagelines IR (OCR output) into elements_core.jsonl (structured element IR)
- **Why**: Standardizes format for downstream portionization stages
- **Type**: Code-only transformation

**09. `elements_content_type_v1`** (Code + optional AI)
- **What it does**: Classifies elements into DocLayNet types (Section-header, Text, Page-footer, etc.) using text-first heuristics
- **Why**: Content type tags enable code-first boundary detection (filters for Section-header)
- **Try**: Code (heuristic classification)
- **Escalate**: Optional AI (LLM classification for low-confidence items, disabled by default)

#### Portionize Stage

**10. `coarse_segment_v1`** (AI)
- **What it does**: Single LLM call to classify entire book into frontmatter/gameplay/endmatter page ranges
- **Why**: Establishes macro boundaries before fine-grained section detection
- **Type**: AI classification (one call for entire book)

**11. `fine_segment_frontmatter_v1`** (AI)
- **What it does**: Divides frontmatter section into logical portions (title, copyright, TOC, rules, etc.)
- **Why**: Structures non-gameplay content for completeness
- **Type**: AI segmentation

**12. `classify_headers_v1`** (AI)
- **What it does**: Batched AI calls to classify elements as macro headers, game section headers, or neither
- **Why**: Provides header candidates for global structure analysis
- **Type**: AI classification (batched, forward/backward redundancy)

**13. `structure_globally_v1`** (AI, currently stubbed)
- **What it does**: Single AI call to create coherent global document structure from header candidates
- **Why**: Creates ordered section structure with macro sections and game sections
- **Type**: AI structuring (currently skipped via stub)

**14. `detect_boundaries_code_first_v1`** (Code + AI escalation)
- **What it does**: Code-first section boundary detection with targeted AI escalation for missing sections
- **Why**: Replaces expensive batched AI with free code filter + 0-30 targeted AI calls; achieves 95%+ coverage
- **Try**: Code (filters elements_core_typed for Section-header with valid numbers, applies multi-stage validation)
- **Validate**: Code (coverage check vs target)
- **Escalate**: AI (targeted re-scan of pages with missing sections using GPT-5)
- **Type**: Code-first with AI escalation

**15. `portionize_ai_scan_v1`** (AI, fallback)
- **What it does**: Full-document AI scan for section boundaries (fallback if code-first fails)
- **Why**: Backup method if code-first detection misses too many sections
- **Type**: AI fallback

**16. `macro_locate_ff_v1`** (AI)
- **What it does**: Identifies frontmatter/main_content/endmatter pages from minimal OCR text
- **Why**: Provides macro section hints for structure analysis
- **Type**: AI location

**17. `merge_boundaries_pref_v1`** (Code)
- **What it does**: Merges primary boundary set with fallback, preferring primary and filling gaps
- **Why**: Combines code-first results with AI fallback for maximum coverage
- **Type**: Code-only merge

**18. `verify_boundaries_v1`** (Code + optional AI)
- **What it does**: Validates section boundaries with deterministic checks (ordering, duplicates) and optional AI spot-checks
- **Why**: Catches boundary errors before expensive extraction stage
- **Try**: Code (deterministic validation)
- **Escalate**: Optional AI (spot-checks sampled boundaries for mid-sentence starts)
- **Type**: Code validation with optional AI sampling

**19. `validate_boundary_coverage_v1`** (Code)
- **What it does**: Ensures boundary set covers expected section IDs and meets minimum count
- **Why**: Fails fast if coverage is too low
- **Type**: Code-only validation

**20. `validate_boundaries_gate_v1`** (Code)
- **What it does**: Final gate check before extraction (count, ordering, gaps)
- **Why**: Prevents proceeding with invalid boundary set
- **Type**: Code-only gate

**21. `portionize_ai_extract_v1`** (AI)
- **What it does**: Extracts section text from elements and parses gameplay data (choices, combat, luck tests, items) using AI
- **Why**: AI understands context and can extract structured gameplay data from narrative text
- **Type**: AI extraction (per-section calls)

**22. `repair_candidates_v1`** (Code)
- **What it does**: Detects sections needing repair (garbled text, low alpha ratio, high digit ratio) using heuristics
- **Why**: Identifies problematic sections before expensive repair stage
- **Type**: Code-only detection

**23. `repair_portions_v1`** (AI)
- **What it does**: Re-reads flagged sections with multimodal LLM (GPT-5) to repair garbled text
- **Why**: Vision models can transcribe corrupted text that OCR missed
- **Type**: AI repair (targeted, budget-capped)

**24. `strip_section_numbers_v1`** (Code)
- **What it does**: Removes section/page number artifacts from section text while preserving paragraph structure
- **Why**: Clean text for final gamebook output
- **Type**: Code-only cleaning

#### Extract Stage

**25. `extract_choices_v1`** (Code + optional AI)
- **What it does**: Extracts choices from section text using deterministic pattern matching ("turn to X", "go to Y")
- **Why**: Code-first approach is faster, cheaper, and more reliable than pure AI extraction
- **Try**: Code (pattern matching)
- **Escalate**: Optional AI (validation for ambiguous cases, disabled by default)
- **Type**: Code-first with optional AI validation

#### Build Stage

**26. `build_ff_engine_v1`** (Code)
- **What it does**: Assembles final gamebook.json from portions with choices, combat, items, etc.
- **Why**: Creates final output format for game engine consumption
- **Type**: Code-only assembly
- **Output note**: Gameplay flow is encoded in ordered `sequence` events (replaces legacy `navigation`).

#### Validate Stage

**27. `validate_ff_engine_node_v1`** (Node/AJV)
- **What it does**: Canonical schema validator shared with the game engine (Node + Ajv)
- **Why**: Ensures pipeline/game engine use identical validation logic
- **Type**: Node validator (bundled, portable)
- **Ship**: Include `modules/validate/validate_ff_engine_node_v1/validator` alongside `gamebook.json` in the game engine build.
- **How to ship**: Copy `gamebook.json` + `modules/validate/validate_ff_engine_node_v1/validator/gamebook-validator.bundle.js` into the game engine bundle, then run `node gamebook-validator.bundle.js gamebook.json --json` before loading.

**28. `forensics_gamebook` / `validate_ff_engine_v2`** (Code)
- **What it does**: Forensic validation (missing sections, duplicates, empty sections, structural issues)
- **Why**: Provides detailed traces for debugging and repair; not the canonical schema validator
- **Type**: Code-only validation

**29. `validate_choice_completeness_v1`** (Code)
- **What it does**: Compares "turn to X" references in section text with extracted choices to find missing choices
- **Why**: Critical for 100% game engine accuracy; missing choices break gameplay
- **Type**: Code-only validation (pattern matching + comparison)

### Two Ways to Run the Pipeline

**1. Regular Production Runs** (output in `output/runs/`)
- **Purpose**: Real pipeline runs that should be preserved and tracked
- **Location**: Artifacts go to `output/runs/<run_id>/` (default or from recipe)
- **When to use**: Actual book processing, production runs, runs you want to keep
- **Manifest**: Automatically registered in `output/run_manifest.jsonl` for tracking
- **Example**:
  ```bash
  # Full canonical FF recipe run (GPT-5.1 OCR; no ARM64/MPS requirement)
  python driver.py --recipe configs/recipes/recipe-ff-ai-ocr-gpt51.yaml --run-id deathtrap-dungeon-20251225
  
  # With instrumentation
  python driver.py --recipe configs/recipes/recipe-ff-ai-ocr-gpt51.yaml --run-id deathtrap-dungeon-20251225 --instrument
  ```

**2. Temporary Test Runs** (output in `/tmp` or `/private/tmp`)
- **Purpose**: Quick testing, development, debugging, AI agent experimentation
- **Location**: Artifacts go to `/tmp` or `/private/tmp` (via `--output-dir` override)
- **When to use**: 
  - Testing new modules or recipe changes
  - Debugging pipeline issues
  - AI agents doing temporary test runs during development
  - Quick smoke tests on subsets
- **Not tracked**: These runs are NOT registered in `output/run_manifest.jsonl` (they're temporary)
- **Example**:
  ```bash
  # Temporary test run (AI agents use this for development/testing)
  python driver.py --recipe configs/recipes/recipe-ff-ai-ocr-gpt51.yaml \
    --run-id cf-ff-ai-ocr-gpt51-test \
    --output-dir /private/tmp/cf-ff-ai-ocr-gpt51-test \
    --force
  
  # Smoke test with subset (GPT-5.1 OCR; no ARM64/MPS requirement)
  python driver.py --recipe configs/recipes/recipe-ff-ai-ocr-gpt51.yaml \
    --settings configs/settings.ff-ai-ocr-gpt51-smoke-20.yaml \
    --run-id ff-ai-ocr-gpt51-smoke-20 \
    --output-dir /tmp/cf-ff-ai-ocr-gpt51-smoke-20 \
    --force
  ```

**Key Differences:**
- **Regular runs**: Use default `output/runs/<run_id>/` (or recipe `output_dir`), registered in manifest
- **Temporary runs**: Use `--output-dir` to override to `/tmp` or `/private/tmp`, NOT registered in manifest
- **AI Agents**: Should use temporary runs (`--output-dir /private/tmp/...`) for testing/development, and only use regular runs for actual production work

### Smoke Tests (Quick Reference)
- **Canonical smoke (current pipeline):** `configs/recipes/recipe-ff-ai-ocr-gpt51.yaml` + `configs/settings.ff-ai-ocr-gpt51-smoke-20.yaml`
- **Offline fixture smoke (no external calls):** `configs/recipes/recipe-ff-smoke.yaml` (uses `testdata/smoke/ff/`)
- **Legacy/archived smoke:** `configs/recipes/legacy/recipe-ocr-coarse-fine-smoke.yaml` and `configs/settings.ff-canonical-smoke*.yaml` (legacy OCR pipeline)

### Common Driver Commands

```bash
# Dry-run legacy OCR recipe (archived)
python driver.py --recipe configs/recipes/legacy/recipe-ocr.yaml --dry-run

# Text ingest with mock LLM stages (for tests without API calls)
python driver.py --recipe configs/recipes/recipe-text.yaml --mock --skip-done

# OCR pages 1–20 real run (auto-generated run_id/output_dir by default)
python driver.py --recipe configs/recipes/recipe-ff-ai-ocr-gpt51.yaml --force

# Reuse a specific run_id/output_dir (opt-in)
python driver.py --recipe configs/recipes/recipe-ff-ai-ocr-gpt51.yaml --run-id myrun --allow-run-id-reuse

# Resume legacy OCR run from portionize onward (reuses cached clean pages)
python driver.py --recipe configs/recipes/legacy/recipe-ocr.yaml --skip-done --start-from portionize_fine

# Swap modules: edit configs/recipes/*.yaml to choose a different module per stage
# (e.g., set stage: extract -> module: extract_text_v1 instead of extract_ocr_v1)
```

Runtime note: full non-mock OCR on the 113-page sample typically takes ~35–40 minutes for the portionize/LLM window stage (gpt-4.1-mini + boost gpt-5). Use `--skip-done` with `--start-from/--end-at` to resume or scope reruns without re-cleaning pages.

Each run emits a lightweight `timing_summary.json` in the run directory with wall seconds per stage (and pages/min for intake/extract when available).

### Apple Silicon vs x86_64 (legacy OCR + hi_res notes)
- **Canonical GPT-5.1 OCR** runs on any arch; no MPS requirement.
- Prefer the ARM64 Python env on Apple Silicon for **legacy** Unstructured `hi_res` intake: `~/miniforge3/envs/codex-arm/bin/python` (reports `platform.machine() == "arm64"`). Unstructured `hi_res` runs successfully here and yields far better header/section recall.
- On x86_64 (Rosetta) the TensorFlow build expects AVX and forces legacy `hi_res` to fall back to `strategy: fast`, which markedly reduces header detection and downstream section coverage.
- Legacy OCR ensemble recipes (archived under `configs/recipes/legacy/`) defaulted to `strategy: hi_res` and rely on EasyOCR; these notes apply only to legacy recipes.
- EasyOCR auto-uses GPU when Metal/MPS is available (Apple Silicon) and falls back to CPU otherwise; no flags needed. Use `--allow-run-id-reuse` only if you explicitly want to reuse an existing run directory; defaults now auto-generate a fresh run_id/output_dir per run.
- Metal-friendly env recipe (legacy EasyOCR; pins torch 2.9.1 / torchvision 0.24.1 / Pillow<13):
  ```bash
  conda create -n codex-arm-mps python=3.11
  conda activate codex-arm-mps
  pip install --no-cache-dir -r requirements-legacy-easyocr.txt -c constraints/metal.txt
  python - <<'PY'
  import torch; print(torch.__version__, torch.backends.mps.is_available())
  PY
  ```
  If `mps.is_available()` is false, you are on the wrong arch or missing the Metal wheel.
  After a GPU smoke run, sanity-check that EasyOCR used MPS:
  ```bash
  python scripts/regression/check_easyocr_gpu.py --debug-file /tmp/cf-easyocr-mps-5/ocr_ensemble/easyocr_debug.jsonl
  ```
  One-shot local smoke + check:
  ```bash
  ./scripts/smoke_easyocr_gpu.sh /tmp/cf-easyocr-mps-5
  ```
  MPS troubleshooting: ensure `platform.machine() == "arm64"`, Xcode CLTs installed, and you’re using the arm64 Python from the `codex-arm-mps` env. Reinstall with the Metal constraints if torch shows `mps.is_available() == False`.
- Keep the "hi_res first, fast fallback" knob: run ARM hi_res by default, and only flip to `settings.fast-intake.yaml` when the environment lacks ARM/AVX. Prior runs showed a large coverage drop when forced to fast, so treat fast as a compatibility fallback, not a peer mode.
- Recommended full run on ARM:  
  `~/miniforge3/envs/codex-arm/bin/python driver.py --recipe configs/recipes/recipe-ff-ai-ocr-gpt51.yaml --run-id <run> --output-dir <dir> --force`
- macOS-only Vision OCR: a new module `extract_ocr_apple_v1` (and optional `apple` engine in `extract_ocr_ensemble_v1`) uses `VNRecognizeTextRequest`. It compiles a Swift helper at runtime; only available on macOS with Xcode CLTs installed.
  - **Sandbox caveat:** In restricted/sandboxed execution, Apple Vision can fail with errors like `sysctlbyname for kern.hv_vmm_present failed` (and emit empty/no `apple` text). If you hit this, run the OCR stage outside the sandbox / with full host permissions, or disable `apple` for that run.

### DAG recipes (coarse+fine merge example)
```bash
# Dry-run canonical OCR (GPT-5.1)
python driver.py --recipe configs/recipes/recipe-ff-ai-ocr-gpt51.yaml --dry-run

# Text ingest DAG with mock LLM stages (fast, no API calls)
python driver.py --recipe configs/recipes/recipe-text-dag.yaml --mock --skip-done

# Quick smoke: coarse+fine+continuation on first 10 pages (legacy, archived)
python driver.py --recipe configs/recipes/legacy/recipe-ocr-coarse-fine-smoke.yaml --force

# Continuation regression check (after a run)
python scripts/regression/check_continuation_propagation.py \
  --hypotheses output/runs/deathtrap-ocr-dag/adapter_out.jsonl \
  --locked output/runs/deathtrap-ocr-dag/portions_locked_merged.jsonl \
  --resolved output/runs/deathtrap-ocr-dag/portions_resolved.jsonl
```

Key points:
- Stages have ids and `needs`; driver topo-sorts and validates schemas.
- Override per-stage outputs via either a stage-level `out:` key (highest precedence) or the recipe-level `outputs:` map.
- Removed (Story 025): image_crop_cv_v1, portionize_page_v1, portionize_numbered_v1, merge_portion_hyp_v1, consensus_spanfill_v1, enrich_struct_v1, build_appdata_v1; demo/alt recipes using them were deleted.

### Parameter validation & output overrides
- Each module can declare `param_schema` (JSON-Schema-lite) in its `module.yaml` to type-check params before the run. Supported fields per param: `type` (`string|number|integer|boolean`), `enum`, `minimum`/`maximum`, `pattern`, `default`; mark required via a top-level `required` list or `required: true` on the property.
- Driver merges `default_params` + recipe `params`, applies schema defaults, and fails fast on missing/unknown/invalid params with a message that includes the stage id and module id.
- Example: `Param 'min_conf' on stage 'clean_pages' (module clean_llm_v1) expected type number, got str`.
- Set custom filenames per stage with `out:` inside the stage config; this overrides recipe `outputs:` and the built-in defaults, and the resolved name is used for resume/skip-done and downstream inputs.
- Example snippet with stage-level `out`:
  ```yaml
  stages:
    - id: clean_pages
      stage: clean
      module: clean_llm_v1
      needs: [extract_text]
      out: pages_clean_custom.jsonl
  ```

Artifacts appear under `output/runs/<run_id>/` as listed in the recipe; use `--skip-done` to resume and `--force` to rerun stages.

## Output conventions
- `output/runs/<run_id>/` contains all artifacts: images/, ocr/, pages_raw/clean, hypotheses, locked/normalized/resolved portions, final JSON, `pipeline_state.json`.
- `output/run_manifest.jsonl` lists runs (id, path, date, notes).

## Instrumentation (timing & cost)
- Enable per-stage timing and LLM cost reporting with `--instrument` (off by default).
- Optional price sheet override via `--price-table configs/pricing.default.yaml` or recipe `instrumentation.price_table`.
- Outputs land beside artifacts: `instrumentation.json` (machine-readable), `instrumentation.md` (summary tables), and raw `instrumentation_calls.jsonl` when present. Manifest entries link to the reports.
- Modules can emit call-level usage via `modules.common.utils.log_llm_usage(...)`; the driver aggregates tokens/costs per stage and per model.

## Run monitoring
- Preferred: `scripts/run_driver_monitored.sh` (spawns driver, writes `driver.pid`, tails `pipeline_events.jsonl`).
  - Example: `scripts/run_driver_monitored.sh --recipe configs/recipes/recipe-ff-ai-ocr-gpt51.yaml --run-id <run_id> --output-dir output/runs -- --instrument`
  - **Important**: `run_driver_monitored.sh` expects `--output-dir` to be the parent (e.g., `output/runs`) and passes the full run dir to `driver.py`. Do not pass a run-specific path.
  - If you pass `--force`, the script pre-deletes the run dir, strips `--force`, and adds `--allow-run-id-reuse` so the driver accepts the created run dir without wiping the log/pidfile mid-run.
- Attach to an existing run: `scripts/monitor_run.sh output/runs/<run_id> output/runs/<run_id>/driver.pid 5`
- Foreground one-liner (useful if background terminal support interferes):
  - `while true; do date; tail -n 1 output/runs/<run_id>/pipeline_events.jsonl; sleep 60; done`
- Crash visibility: prefer `scripts/run_driver_monitored.sh` so stderr is captured in `driver.log`. `scripts/monitor_run.sh` now tails `driver.log` when the PID disappears to surface hard failures (e.g., OpenMP SHM errors).
- `scripts/monitor_run.sh` also appends a synthetic `run_monitor` failure event to `pipeline_events.jsonl` when the driver PID disappears, so tailing events shows the crash.
- `scripts/run_driver_monitored.sh` runs `scripts/postmortem_run.sh` on exit to append a `run_postmortem` failure event when the PID is gone.

### Cost/perf presets and benchmarks
- Preset settings live in `configs/presets/`:
  - `speed.text.yaml` (text recipe, gpt-4.1-mini, ~8s/page, ~$0.00013/page)
  - `cost.ocr.yaml` (OCR, gpt-4.1-mini, ~13–18s/page, ~$0.0011/page)
  - `balanced.ocr.yaml` (OCR, gpt-4.1, ~16–34s/page, ~$0.014–0.026/page)
  - `quality.ocr.yaml` (OCR, gpt-5, ~70–100s/page, ~$0.015–0.020/page)
- Use with the driver by passing `--settings`, e.g.:
  ```bash
  python driver.py --recipe configs/recipes/recipe-text.yaml --settings configs/presets/speed.text.yaml --instrument
  python driver.py --recipe configs/recipes/legacy/recipe-ocr.yaml  --settings configs/presets/cost.ocr.yaml --instrument
  ```
- Bench sessions write metrics to `output/runs/bench-*/bench_metrics.csv` and `metadata.json` (slices, models, price table, runs). Example sessions:
  - `output/runs/bench-cost-perf-ocr-20251124c/bench_metrics.csv`
  - `output/runs/bench-cost-perf-text-20251124e/bench_metrics.csv`

## Pipeline visibility dashboard
- Serve from repo root: `python -m http.server 8000` then open `http://localhost:8000/docs/pipeline-visibility.html`.
- The page polls `output/run_manifest.jsonl` for run ids, then reads `output/runs/<run_id>/pipeline_state.json` and `pipeline_events.jsonl` for live progress, artifacts, and confidence stats.
- A ready-to-use fixture run lives at `output/runs/dashboard-fixture` (listed in the manifest) so you can smoke the dashboard without running the pipeline.

## Roadmap (high level)
- Enrichment (choices, cross-refs, combat/items/endings)
- Turn-to validator (CYOA), layout-preserving extractor, image cropper/mapper
- Coarse+fine portionizer; continuation merge
- AI planner to pick modules/configs based on user goals

## Legacy OCR Strategy Choice (Unstructured intake)

**Legacy Unstructured intake only.** The canonical GPT-5.1 OCR pipeline does not use `hi_res`/`ocr_only` strategies.

**Legacy recommendation: `hi_res` on ARM64, `ocr_only` on x86_64**

**⚠️ Before choosing a strategy**: Check your Python architecture (`python -c "import platform; print(platform.machine())"`). On Apple Silicon Macs, verify if ARM64 environment exists even if your current shell is using x86_64.

After comprehensive testing comparing old Tesseract-based OCR with Unstructured strategies (`ocr_only` vs `hi_res`):

- **`hi_res` on ARM64**: ~15% faster (88s/page vs 105s/page), extracts ~35% more granular elements (better layout boundaries), same text quality as `ocr_only`. Use when ARM64 environment is available (Story 033 complete).
- **`ocr_only`**: More compatible (works on x86_64/Rosetta without JAX), similar text quality, fewer elements. Use as fallback or when maximum compatibility is needed.

**Note**: OCR text quality is source-limited (scanned PDF quality determines accuracy), so strategy choice primarily affects performance and element granularity, not character recognition accuracy.

## Legacy Environment Setup (Unstructured/EasyOCR)

**⚠️ IMPORTANT: This section applies to legacy Unstructured/EasyOCR intake only.**
The canonical GPT-5.1 OCR pipeline runs with `requirements.txt` on any arch and does not require ARM64/MPS or JAX.

**Check Your Environment First**

Before assuming x86_64/Rosetta, check if you have an ARM64 environment available:

```bash
# Check if ARM64 environment exists
ls -la ~/miniforge3/envs/codex-arm/bin/python 2>/dev/null && echo "ARM64 environment available"

# Check current Python architecture
python -c "import platform; print(f'Machine: {platform.machine()}')"
# ARM64 native: "Machine: arm64"
# x86_64/Rosetta: "Machine: x86_64"

# Check ARM64 environment architecture
~/miniforge3/envs/codex-arm/bin/python -c "import platform; print(f'Machine: {platform.machine()}')" 2>/dev/null
# Should show: "Machine: arm64"
```

**On Apple Silicon (M-series) Macs**: You likely have both environments. Always check for ARM64 first and use it for better performance unless you have a specific reason to use x86_64.

### x86_64/Rosetta (Legacy default, recommended for quick starts)

The default setup uses x86_64 Python running under Rosetta 2 on Apple Silicon. This is the most stable and compatible option.

**Setup:**
- Install Miniconda (x86_64): Download from https://docs.conda.io/en/latest/miniconda.html (choose macOS Intel 64-bit)
- Create environment: `conda create -n codex python=3.11`
- Install dependencies: `pip install -r requirements.txt`

**When to use:**
- Quick starts and one-off runs
- When you need maximum compatibility
- When `ocr_only` OCR strategy is sufficient

**OCR Strategy:**
- Uses `ocr_only` (JAX unavailable under Rosetta, so `hi_res` not possible)
- **Note**: If you're on Apple Silicon but using x86_64 Python, check if ARM64 environment exists and use that instead

**Limitations:**
- Cannot use `hi_res` OCR strategy (requires JAX, which has AVX incompatibilities under Rosetta)
- Slower performance (~3-5 minutes/page for OCR)
- No GPU acceleration

### ARM64 Native (Legacy recommended for heavy workloads)

For repeated processing or when you need `hi_res` OCR with table structure inference, use native ARM64 with JAX/Metal GPU acceleration.

**Setup:**
1. Install Miniforge (ARM64):
   ```bash
   wget https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-MacOSX-arm64.sh
   bash Miniforge3-MacOSX-arm64.sh -b -p ~/miniforge3
   ```
2. Create ARM64 environment:
   ```bash
   ~/miniforge3/bin/conda create -n codex-arm python=3.11 -y
   ~/miniforge3/envs/codex-arm/bin/pip install -r requirements.txt
   ```
3. Install JAX with Metal support:
   ```bash
   ~/miniforge3/envs/codex-arm/bin/pip install jax-metal
   ```
4. Fix pdfminer compatibility (required for unstructured):
   ```bash
   ~/miniforge3/envs/codex-arm/bin/pip install "pdfminer.six==20240706"
   ```
5. Verify JAX/Metal:
   ```bash
   ~/miniforge3/envs/codex-arm/bin/python -c "import jax; print(jax.devices())"
   # Should show: [METAL(id=0)]
   ```

**Activation:**
```bash
source ~/miniforge3/bin/activate
conda activate codex-arm
```

**When to use:**
- Processing many PDFs regularly
- Books with complex tables/layouts where `hi_res` helps
- When you want GPU acceleration (2-5× faster than x86_64/Rosetta)
- New machine/environment setup from scratch

**OCR Strategy:**
- Recommended: `hi_res` (~15% faster, better element boundaries)
- Fallback: `ocr_only` if needed

**Performance:**
- `hi_res` OCR: ~88s/page (tested on M4 Pro, pages 16-18)
- `ocr_only` OCR: ~105s/page (ARM64 native, no JAX)
- Expected 2-5× speedup over x86_64/Rosetta for `hi_res` workloads

**Known issues:**
- numpy version conflict: jax-metal requires numpy>=2.0, but unstructured requires numpy<2 (works despite warning)
- pdfminer.six must be pinned to 20240706 for unstructured 0.16.9 compatibility

**Rollback:** Simply use your existing x86_64 environment. Miniforge and Miniconda can coexist.

## Dev notes
- Requires Tesseract installed/on PATH.
- Models configurable; defaults use `gpt-4.1-mini` with `--boost_model gpt-5`.
- Artifacts are JSON/JSONL; runs are append-only and reproducible via configs.
- Driver unit tests run in CI via `tests.yml`. Run locally with:
  ```bash
  python -m unittest discover -s tests -p "driver_*test.py"
  ```
