# Story: ARM64 Environment Cleanup Investigation

**Status**: Done  
**Created**: 2025-12-23  
**Priority**: Medium  
**Parent Story**: story-081 (GPT‑5.1 AI‑First OCR Pipeline), story-087 (Retire Legacy OCR Recipe)

---

## Goal

Investigate whether ARM64/MPS environment requirements are still needed now that the canonical pipeline uses AI-first OCR (GPT-5.1) instead of EasyOCR. Clean up code and documentation if the requirements are obsolete.

---

## Motivation

The current canonical recipe (`recipe-ff-ai-ocr-gpt51.yaml`) uses GPT-5.1 for AI-first OCR and does not use EasyOCR or the OCR ensemble. However, documentation and scripts still mandate ARM64 + MPS (Metal Performance Shaders) environment setup, which was specifically needed for EasyOCR's GPU acceleration via PyTorch/MPS.

**Hypothesis**: The ARM64/MPS requirement was only needed for EasyOCR, and since we're no longer using EasyOCR in the canonical pipeline, these requirements may be obsolete.

---

## Success Criteria

- [x] Investigate all references to ARM64/MPS environment requirements
- [x] Determine if any current modules depend on MPS/torch (beyond legacy EasyOCR)
- [x] Verify that the canonical recipe (`recipe-ff-ai-ocr-gpt51.yaml`) has no MPS/torch dependencies
- [x] Check if `requirements.txt` still needs torch/easyocr for any active use cases
- [x] Update or remove `scripts/check_arm_mps.py` if obsolete
- [x] Update `AGENTS.md` and `README.md` to reflect actual requirements
- [x] Remove or update SHM-safe environment variable documentation if only needed for EasyOCR
- [x] Document findings and any cleanup actions in work log

---

## Background

### Historical Context

- **Story 033**: ARM64-native pipeline environment was established for performance with JAX/Metal GPU acceleration
- **Story 065**: EasyOCR was stabilized as a third OCR engine, requiring PyTorch/MPS for GPU acceleration
- **Story 067**: GPU acceleration for OCR pipeline (EasyOCR MPS support)
- **Story 081**: GPT-5.1 AI-first OCR pipeline replaced the OCR ensemble approach
- **Story 087**: Legacy OCR-only recipe retirement (in progress)

### Current State

- **Canonical recipe**: `recipe-ff-ai-ocr-gpt51.yaml` uses `ocr_ai_gpt51_v1` module (no EasyOCR, no torch)
- **Legacy recipe**: `recipe-ff-canonical.yaml` still uses `extract_ocr_ensemble_v1` with EasyOCR (deprecated)
- **Requirements**: `requirements.txt` still includes `easyocr==1.7.1`, `torch==2.9.1`, `torchvision==0.24.1`
- **Documentation**: `AGENTS.md` mandates ARM64 + MPS; `README.md` has extensive ARM64/JAX setup docs
- **Scripts**: `scripts/check_arm_mps.py` checks for ARM64 + MPS availability

### Key Questions

1. Does the canonical recipe (`recipe-ff-ai-ocr-gpt51.yaml`) require ARM64/MPS?
2. Are there any other modules (besides legacy OCR ensemble) that use torch/MPS?
3. Should `requirements.txt` still include torch/easyocr if only legacy recipes use them?
4. Is the ARM64/JAX documentation in README.md still relevant (for unstructured `hi_res` strategy)?
5. Should `check_arm_mps.py` be removed, updated, or kept for legacy recipe support?

---

## Tasks

- [x] Search codebase for all torch/MPS imports and usage
- [x] Verify canonical recipe module dependencies (check `ocr_ai_gpt51_v1` and all downstream modules)
- [x] Check if any non-legacy modules import or use torch/MPS
- [x] Review `requirements.txt` and determine if torch/easyocr can be moved to optional/legacy
- [x] Review `AGENTS.md` environment setup section
- [x] Review `README.md` ARM64/JAX documentation (check if unstructured `hi_res` is still used)
- [x] Review `scripts/check_arm_mps.py` usage and determine if it should be removed/updated
- [x] Check for SHM-safe environment variable usage (KMP_USE_SHMEM, etc.)
- [x] Update documentation to reflect actual requirements
- [x] Document findings and recommendations in work log

---

## Work Log

### 20251223-0000 — Story created
- **Result:** Story created to investigate ARM64/MPS environment requirements.
- **Notes:** 
  - Current canonical recipe uses GPT-5.1 AI-first OCR, which does not use EasyOCR
  - Legacy OCR ensemble recipe (deprecated) still uses EasyOCR with MPS
  - Documentation and scripts still mandate ARM64 + MPS setup
  - Need to verify if these requirements are still needed
- **Next:** Search codebase for torch/MPS usage and verify canonical recipe dependencies.

### 20251225-1406 — Scanned codebase for torch/MPS usage and canonical recipe deps
- **Result:** Success; torch/MPS usage is confined to legacy OCR ensemble paths and helper scripts.
- **Notes:**
  - `modules/extract/extract_ocr_ensemble_v1/main.py` imports torch and sets MPS device; no other active modules import torch.
  - `scripts/check_arm_mps.py` and `scripts/regression/check_easyocr_gpu.py` are the only other torch/MPS touchpoints.
  - Canonical recipe `configs/recipes/recipe-ff-ai-ocr-gpt51.yaml` uses `ocr_ai_gpt51_v1` and contains no EasyOCR/torch modules.
  - `requirements.txt` and `constraints/metal.txt` still pin `easyocr`, `torch`, and `torchvision`.
- **Next:** Review legacy recipes/docs to decide whether to demote ARM64/MPS to legacy-only guidance and move EasyOCR/torch to optional installs.

### 20251225-1410 — Scoped ARM64/MPS to legacy EasyOCR and split legacy requirements
- **Result:** Success; docs now clarify ARM64/MPS as legacy-only, and EasyOCR/torch pins moved to a dedicated requirements file.
- **Notes:**
  - Created `requirements-legacy-easyocr.txt` and removed EasyOCR/torch pins from `requirements.txt`.
  - Updated `constraints/metal.txt` usage comment for legacy installs.
  - Adjusted `AGENTS.md` and `README.md` to state GPT-5.1 OCR runs on any arch; ARM64/MPS is only for legacy EasyOCR/ensemble or Unstructured `hi_res`.
  - Updated `scripts/check_arm_mps.py` messaging to explicitly mark legacy EasyOCR scope.
- **Next:** Decide whether to deprecate legacy EasyOCR scripts or keep them documented for archived recipes; update `docs/stories.md` if story status changes.

### 20251225-1412 — Tightened legacy-only wording in README
- **Result:** Success; headings and recommendations now explicitly labeled legacy to avoid confusion with canonical GPT-5.1 OCR.
- **Notes:**
  - Renamed OCR strategy/environment headings to “Legacy …” and clarified “Legacy recommendation” phrasing.
  - No historical docs or CHANGELOG edits.
- **Next:** Confirm if we should add a short legacy EasyOCR install section or mark Story 101 done.

### 20251225-1416 — Ran GPT‑5.1 smoke run to confirm pipeline still executes
- **Result:** Success; smoke run completed end-to-end with expected missing/ orphan counts for 20pp subset.
- **Notes:**
  - Command: `python driver.py --recipe configs/recipes/recipe-ff-ai-ocr-gpt51.yaml --settings configs/settings.ff-ai-ocr-gpt51-smoke-20.yaml --run-id ff-ai-ocr-gpt51-smoke-20 --output-dir /tmp/cf-ff-ai-ocr-gpt51-smoke-20 --force`
  - Run output: `/tmp/cf-ff-ai-ocr-gpt51-smoke-20/` (validation passed; reachability expected false on partial run).
  - Key artifacts: `.../03_ocr_ai_gpt51_v1/pages_html.jsonl`, `.../10_portionize_html_extract_v1/portions_enriched.jsonl`, `.../21_build_ff_engine_with_issues_v1/gamebook_raw.json`.
- **Next:** Decide whether to mark Story 101 done or add a short legacy EasyOCR install section in README.

### 20251225-1419 — Marked Story 101 complete
- **Result:** Success.
- **Notes:** Checked all tasks and success criteria; story status set to Done.
- **Next:** None.
