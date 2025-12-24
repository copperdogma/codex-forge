# Story: FF Pipeline Accel + Accuracy Guardrails

**Status**: To Do  
**Created**: 2025-12-04  
**Depends On**: story-035 (FF Pipeline Optimization must complete quality targets first)

## Goal
Speed up the **GPT‑5.1 HTML‑first** Fighting Fantasy pipeline with profiling and cost guardrails (not OCR ensemble/clean_llm). Maintain or improve section recall, text integrity, and choice completeness.

## Success Criteria
- [ ] End-to-end runtime reduced vs current GPT‑5.1 baseline (document numbers) without loss of section/choice recall.
- [ ] Profiling identifies top cost/time stages and validates the new hotspots (expected: OCR AI calls + HTML boundary/extract).
- [ ] Guardrails: section boundary recall ≥99%, no increase in empty‑text sections, navigation completeness check passes.
- [ ] Cost/regression report comparing before/after runs on a reference book (token + API cost + wall‑time).

## Tasks
- [ ] Profile GPT‑5.1 pipeline stages (timing + cost per module) and record baselines.
- [ ] Test calling gpt51 calls in parallel to speed up the pipeline.
- [ ] Can we use prompt caching to save costs?
- [ ] Add rate‑limit/backoff and concurrency controls for OCR AI calls (API stability).
- [ ] Add caching/hash reuse for unchanged page images to skip re‑OCR.
- [ ] Benchmark and capture baseline vs optimized runtimes and costs on a reference FF book.
- [ ] Add validation guard (boundary/section/choice recall) to fail fast on accuracy regressions.
- [ ] Target highest‑cost stages: reduce redundant OCR reruns, explore low‑cost OCR alternatives for fast‑path, and verify no recall loss.

## Work Log
### 20251221-1545 — Reframed story for GPT‑5.1 pipeline
- **Result:** Success.
- **Notes:** Updated scope to profiling + cost guardrails for the new HTML‑first pipeline; removed OCR ensemble/clean_llm assumptions.
- **Next:** Add baseline profiling run and identify current cost/time hotspots.
### 20251212-1330 — Dependency clarified
- **Result:** Success.
- **Notes:** This acceleration/guardrails work should start only after Story 035 achieves stable section/choice quality, to avoid optimizing a moving target.
- **Next:** Revisit once Story 035 is marked Done.
