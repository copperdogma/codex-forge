# Story: ARM64 Environment Cleanup Investigation

**Status**: To Do  
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

- [ ] Investigate all references to ARM64/MPS environment requirements
- [ ] Determine if any current modules depend on MPS/torch (beyond legacy EasyOCR)
- [ ] Verify that the canonical recipe (`recipe-ff-ai-ocr-gpt51.yaml`) has no MPS/torch dependencies
- [ ] Check if `requirements.txt` still needs torch/easyocr for any active use cases
- [ ] Update or remove `scripts/check_arm_mps.py` if obsolete
- [ ] Update `AGENTS.md` and `README.md` to reflect actual requirements
- [ ] Remove or update SHM-safe environment variable documentation if only needed for EasyOCR
- [ ] Document findings and any cleanup actions in work log

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

- [ ] Search codebase for all torch/MPS imports and usage
- [ ] Verify canonical recipe module dependencies (check `ocr_ai_gpt51_v1` and all downstream modules)
- [ ] Check if any non-legacy modules import or use torch/MPS
- [ ] Review `requirements.txt` and determine if torch/easyocr can be moved to optional/legacy
- [ ] Review `AGENTS.md` environment setup section
- [ ] Review `README.md` ARM64/JAX documentation (check if unstructured `hi_res` is still used)
- [ ] Review `scripts/check_arm_mps.py` usage and determine if it should be removed/updated
- [ ] Check for SHM-safe environment variable usage (KMP_USE_SHMEM, etc.)
- [ ] Update documentation to reflect actual requirements
- [ ] Document findings and recommendations in work log

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


