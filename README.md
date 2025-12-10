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
- `settings.example.yaml`: sample config
- Driver snapshots: each run writes `snapshots/` (recipe.yaml, plan.json, registry.json, optional settings/pricing/instrumentation configs) and records paths in `output/run_manifest.jsonl` for reproducibility.
- Shared helpers for module entrypoints live in `modules/common/` (utils, OCR helpers).

## Modular driver (current)
- Modules live under `modules/<stage>/<module_id>/`; recipes live in `configs/recipes/`.
- Driver orchestrates stages, stamps artifacts with schema/module/run IDs, and tracks state in `pipeline_state.json`.
- Swap modules by changing the recipe, e.g. OCR vs text ingest.

### Two Ways to Run the Pipeline

**1. Regular Production Runs** (output in `output/runs/`)
- **Purpose**: Real pipeline runs that should be preserved and tracked
- **Location**: Artifacts go to `output/runs/<run_id>/` (default or from recipe)
- **When to use**: Actual book processing, production runs, runs you want to keep
- **Manifest**: Automatically registered in `output/run_manifest.jsonl` for tracking
- **Example**:
  ```bash
  # Full canonical FF recipe run
  python driver.py --recipe configs/recipes/recipe-ff-canonical.yaml --run-id deathtrap-dungeon-20251208
  
  # With instrumentation
  python driver.py --recipe configs/recipes/recipe-ff-canonical.yaml --run-id deathtrap-dungeon-20251208 --instrument
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
  python driver.py --recipe configs/recipes/recipe-ff-canonical.yaml \
    --run-id cf-ff-canonical-test \
    --output-dir /private/tmp/cf-ff-canonical-test \
    --force
  
  # Smoke test with subset
  python driver.py --recipe configs/recipes/recipe-ff-canonical.yaml \
    --settings settings.smoke.yaml \
    --run-id ff-canonical-smoke \
    --output-dir /tmp/cf-ff-canonical-smoke \
    --force
  ```

**Key Differences:**
- **Regular runs**: Use default `output/runs/<run_id>/` (or recipe `output_dir`), registered in manifest
- **Temporary runs**: Use `--output-dir` to override to `/tmp` or `/private/tmp`, NOT registered in manifest
- **AI Agents**: Should use temporary runs (`--output-dir /private/tmp/...`) for testing/development, and only use regular runs for actual production work

### Common Driver Commands

```bash
# Dry-run OCR recipe
python driver.py --recipe configs/recipes/recipe-ocr.yaml --dry-run

# Text ingest with mock LLM stages (for tests without API calls)
python driver.py --recipe configs/recipes/recipe-text.yaml --mock --skip-done

# OCR pages 1–20 real run
python driver.py --recipe configs/recipes/recipe-ocr-1-20.yaml --force

# Resume long OCR run from portionize onward (reuses cached clean pages)
python driver.py --recipe configs/recipes/recipe-ocr.yaml --skip-done --start-from portionize_fine

# Swap modules: edit configs/recipes/*.yaml to choose a different module per stage
# (e.g., set stage: extract -> module: extract_text_v1 instead of extract_ocr_v1)
```

Runtime note: full non-mock OCR on the 113-page sample typically takes ~35–40 minutes for the portionize/LLM window stage (gpt-4.1-mini + boost gpt-5). Use `--skip-done` with `--start-from/--end-at` to resume or scope reruns without re-cleaning pages.

### Apple Silicon vs x86_64 (intake quality)
- Prefer the ARM64 Python env on Apple Silicon: `~/miniforge3/envs/codex-arm/bin/python` (reports `platform.machine() == "arm64"`). Unstructured `hi_res` runs successfully here and yields far better header/section recall.
- On x86_64 (Rosetta) the TensorFlow build expects AVX and forces us to fall back to `strategy: fast`, which markedly reduces header detection and downstream section coverage.
- Canonical FF recipe (`configs/recipes/recipe-ff-canonical.yaml`) defaults to `strategy: hi_res`; if you must stay on x86_64, pass `--settings settings.fast-intake.yaml` to override to `fast` and expect lower quality.
- Keep the "hi_res first, fast fallback" knob: run ARM hi_res by default, and only flip to `settings.fast-intake.yaml` when the environment lacks ARM/AVX. Prior runs showed a large coverage drop when forced to fast, so treat fast as a compatibility fallback, not a peer mode.
- Recommended full run on ARM:  
  `~/miniforge3/envs/codex-arm/bin/python driver.py --recipe configs/recipes/recipe-ff-canonical.yaml --run-id <run> --output-dir <dir> --force`
- macOS-only Vision OCR: a new module `extract_ocr_apple_v1` (and optional `apple` engine in `extract_ocr_ensemble_v1`) uses `VNRecognizeTextRequest`. It compiles a Swift helper at runtime; only available on macOS with Xcode CLTs installed.

### DAG recipes (coarse+fine merge example)
```bash
# Dry-run DAG OCR with adapter merge
python driver.py --recipe configs/recipes/recipe-ocr-dag.yaml --dry-run

# Text ingest DAG with mock LLM stages (fast, no API calls)
python driver.py --recipe configs/recipes/recipe-text-dag.yaml --mock --skip-done

# Quick smoke: coarse+fine+continuation on first 10 pages (manual)
python driver.py --recipe configs/recipes/recipe-ocr-coarse-fine-smoke.yaml --force

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

### Cost/perf presets and benchmarks
- Preset settings live in `configs/presets/`:
  - `speed.text.yaml` (text recipe, gpt-4.1-mini, ~8s/page, ~$0.00013/page)
  - `cost.ocr.yaml` (OCR, gpt-4.1-mini, ~13–18s/page, ~$0.0011/page)
  - `balanced.ocr.yaml` (OCR, gpt-4.1, ~16–34s/page, ~$0.014–0.026/page)
  - `quality.ocr.yaml` (OCR, gpt-5, ~70–100s/page, ~$0.015–0.020/page)
- Use with the driver by passing `--settings`, e.g.:
  ```bash
  python driver.py --recipe configs/recipes/recipe-text.yaml --settings configs/presets/speed.text.yaml --instrument
  python driver.py --recipe configs/recipes/recipe-ocr.yaml  --settings configs/presets/cost.ocr.yaml --instrument
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

## OCR Strategy Choice

**Recommended: `hi_res` on ARM64, `ocr_only` on x86_64**

**⚠️ Before choosing a strategy**: Check your Python architecture (`python -c "import platform; print(platform.machine())"`). On Apple Silicon Macs, verify if ARM64 environment exists even if your current shell is using x86_64.

After comprehensive testing comparing old Tesseract-based OCR with Unstructured strategies (`ocr_only` vs `hi_res`):

- **`hi_res` on ARM64**: ~15% faster (88s/page vs 105s/page), extracts ~35% more granular elements (better layout boundaries), same text quality as `ocr_only`. Use when ARM64 environment is available (Story 033 complete).
- **`ocr_only`**: More compatible (works on x86_64/Rosetta without JAX), similar text quality, fewer elements. Use as fallback or when maximum compatibility is needed.

**Note**: OCR text quality is source-limited (scanned PDF quality determines accuracy), so strategy choice primarily affects performance and element granularity, not character recognition accuracy.

## Environment Setup

**⚠️ IMPORTANT: Check Your Environment First**

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

### x86_64/Rosetta (Default, Recommended for Quick Starts)

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

### ARM64 Native (Recommended for Heavy Workloads)

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
