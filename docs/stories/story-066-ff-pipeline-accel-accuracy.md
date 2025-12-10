# Story: FF Pipeline Accel + Accuracy Guardrails

**Status**: To Do  
**Created**: 2025-12-04  

## Goal
Speed up the Fighting Fantasy pipeline (especially per-page clean + extraction) while preserving or improving accuracy (section recall, text integrity, choices completeness).

## Success Criteria
- [ ] End-to-end runtime reduced vs current baseline (document numbers TBD) without loss of section/choice recall.
- [ ] Per-page clean_llm_v1 calls parallelized or selectively escalated (cheap-first, boost on low confidence).
- [ ] Guardrails: section boundary recall ≥99%, no increase in empty-text sections, navigation completeness check passes.
- [ ] Cost/regression dashboard or report comparing before/after runs on a reference book.

## Tasks
- [ ] Parallelize clean_llm_v1 (batch or thread/process) with rate-limit/backoff.
- [ ] Add cheap-first, escalate-on-low-confidence flow (gpt-4.1-mini → gpt-5) with min_conf tuning.
- [ ] Add caching/hash reuse for unchanged pages to skip re-cleaning.
- [ ] Benchmark and capture baseline vs optimized runtimes and costs on a reference FF book.
- [ ] Add validation guard (boundary/section/choice recall) to fail fast on accuracy regressions.
- [ ] Target OCR + clean as highest-cost stages: reduce redundant reruns, consider page-level skip when downstream unchanged, and explore OCR quality/psm tuning for speed without recall loss.

## Work Log
