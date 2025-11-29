## Story: ARM64-native pipeline environment & performance

**Status**: To Do  
**Created**: 2025-11-29  

---

### Goal
Establish a documented, reproducible ARM64-native Python environment for codex-forge on Apple Silicon (M-series), validate that the full pipeline runs correctly under it, and benchmark whether the ARM64 + `jax-metal` + `hi_res` OCR strategy provides enough benefit over the current x86_64/Rosetta `ocr_only` setup to justify migration.

### Success Criteria / Acceptance
- ARM64-native environment for codex-forge is fully documented (creation commands, Python version, key dependencies, environment name).
- All existing automated tests and core smoke recipes (OCR + text + FF export) pass under the ARM64 environment with no regressions.
- Benchmarks comparing x86_64/Rosetta (`ocr_only`) vs ARM64 (`hi_res` with table structure inference, when available) are captured for at least one representative book, including:
  - Wall-clock processing time per page / per book.
  - OCR quality notes (legibility, layout handling, tables).
- Clear guidance is documented on **when to stay on x86_64** versus **when to adopt ARM64**, including tradeoffs (setup cost, fragility of `jax-metal`, performance/quality gains).
- Default project docs remain conservative: x86_64/Rosetta path is preserved and remains the primary, stable recommendation unless benchmarks show strong, repeatable wins.

### Context
- Current setup:
  - Miniconda is installed as x86_64 (`osx-64`) and runs under Rosetta 2 on an ARM64 M4 chip.
  - This caused JAX/AVX incompatibilities when experimenting with GPU-accelerated paths.
  - The pipeline is currently working using an x86_64 environment with `ocr_only` OCR strategy.
- ARM64-native options:
  - Miniforge/Miniconda provide `osx-arm64` installers for Apple Silicon.
  - System Python at `/usr/bin/python3` is a universal binary supporting ARM64.
  - `jax-metal` enables JAX on Apple Silicon GPUs via Metal (`pip install jax-metal`).
- Performance expectations:
  - x86_64 + `ocr_only` is functional but slow (~3–5 minutes/page) and cannot use `hi_res` or table-structure inference.
  - ARM64 + `jax-metal` + `hi_res` is expected to be **2–5× faster** and unlock higher-quality layout/table handling, at the cost of a more complex environment and potential dependency conflicts.
- Prior recommendation:
  - For one-off or infrequent runs with acceptable OCR quality, staying on x86_64/Rosetta is recommended to avoid disruptive environment rebuilds.
  - ARM64 becomes attractive if:
    - Many PDFs will be processed regularly.
    - Books include complex tables/layouts where `hi_res` helps.
    - A new machine/environment is being set up from scratch.

---

### Approach
1. **Baseline documentation and benchmarking (x86_64/Rosetta).**
2. **Design an ARM64 migration plan** that can co-exist with the current environment (separate conda env, no destructive changes).
3. **Prototype the ARM64 environment** using Miniforge/conda:
   - Create a fresh `osx-arm64` env (e.g., `codex-arm`).
   - Install Python and project requirements.
   - Add `jax-metal` and any OCR-related dependencies.
4. **Run tests and core recipes** (smoke tests, FF recipes) on ARM64 to confirm correctness.
5. **Benchmark and compare** x86_64 vs ARM64 on a representative book (e.g., `06 deathtrap dungeon`):
   - Measure runtime and resource usage.
   - Compare OCR/hi_res output quality (including table handling where relevant).
6. **Document guidance and defaults**:
   - Update docs to describe both paths.
   - Keep x86_64 as default unless ARM64 benefits are clearly compelling.
   - Capture a “migration checklist” and rollback strategy.

---

### Tasks
- [ ] **Baseline the current x86_64/Rosetta environment**
  - [ ] Record current Python version, conda distribution (Miniconda vs Miniforge), env name, and key packages relevant to OCR and JAX.
  - [ ] Capture a timing baseline for one end-to-end OCR-heavy recipe (e.g., `recipe-ocr.yaml` or `recipe-ocr-dag.yaml`) on `06 deathtrap dungeon` (pages/minute and total runtime).
- [ ] **Design ARM64 migration plan (non-destructive)**
  - [ ] Specify the recommended ARM64 stack (Miniforge installer URL, `osx-arm64` target, Python version).
  - [ ] Define a new environment name (e.g., `codex-arm`) and document the creation commands.
  - [ ] Identify any platform-specific wheels or packages (e.g., JAX, OCR libs, ONNX runtimes) and how they will be installed.
  - [ ] Write a simple rollback plan (how to switch back to x86_64 env, what not to delete).
- [ ] **Prototype ARM64 environment creation**
  - [ ] Install Miniforge (ARM64) without disturbing the existing x86_64 Miniconda:
    - `wget https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-MacOSX-arm64.sh`
    - `bash Miniforge3-MacOSX-arm64.sh`
  - [ ] Create `codex-arm` env: `conda create -n codex-arm python=3.11`.
  - [ ] Activate and install codex-forge dependencies: `pip install -r requirements.txt`.
  - [ ] Install `jax-metal` and verify that a trivial JAX program can run on Metal.
- [ ] **Validate codex-forge on ARM64**
  - [ ] Run unit tests (`pytest`) under `codex-arm` and confirm all pass or document any ARM-specific failures.
  - [ ] Run key driver recipes (at least one OCR recipe and one FF export recipe) and ensure outputs validate with `validate_artifact.py`.
  - [ ] Confirm that non-AVX code paths work and that no Rosetta-specific assumptions exist in scripts or modules.
- [ ] **Evaluate hi_res OCR strategy on ARM64**
  - [ ] Enable `hi_res` OCR with table structure inference in the ARM64 environment and run on a small page range from `06 deathtrap dungeon` and, if helpful, a table-heavy sample.
  - [ ] Compare OCR quality (text accuracy, layout fidelity, table parsing) and performance against the x86_64 `ocr_only` baseline.
  - [ ] Document any instability or configuration fragility in `jax-metal` or hi_res dependencies.
- [ ] **Document guidance and defaults**
  - [ ] Add or update docs (likely `README.md` and/or a dedicated environment section) to:
    - Describe both x86_64/Rosetta and ARM64 setups.
    - Recommend x86_64 for quick starts/one-offs and ARM64 for repeated heavy workloads or table-heavy books.
  - [ ] Capture a concise migration playbook (steps to create `codex-arm`, install `jax-metal`, and verify the pipeline).
  - [ ] Note any future work (e.g., Docker images, CI matrix including ARM64) if ARM64 becomes the primary target.

---

### Work Log
- 20251129-1200 — Story stub created to track potential migration from x86_64/Rosetta to native ARM64 with `jax-metal`.
  - **Result:** Success (story scaffold, goals, and tasks drafted).
  - **Notes:** Captured current recommendation to stick with x86_64 for now while defining a safe, optional path to ARM64. Emphasized non-destructive env creation, full test coverage, and benchmarking before changing defaults.
  - **Next:** When prioritized, begin by recording the current x86_64 environment details and timing baseline, then prototype the `codex-arm` environment as described.


