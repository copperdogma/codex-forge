# Story: AI OCR Radical Simplification — Challenging the Escalation Assumption

**Status**: To Do  
**Created**: 2025-12-17  
**Updated**: 2025-12-18 (Added Mistral OCR 3)
**Priority**: High

---

## Goal

Challenge the current architectural assumption that we must use a complex ensemble of cheap OCR engines (Tesseract, EasyOCR, Apple Vision) with expensive AI escalation (GPT-4V). Evaluate if high-quality, low-cost AI OCR models (specifically Gemini 3 Flash and Mistral OCR 3) can be used as the **primary** OCR engine from the start, radically simplifying the pipeline by removing complex voting, repair, and escalation logic.

**Key Focus Areas**:
- **Simplicity**: Can we replace multiple stages (intake, ensemble, voting, repair, escalation) with a single high-quality AI OCR call?
- **Cost**: Is the "AI-first" approach cheaper or cost-competitive when considering the removal of complex multi-stage processing and developer overhead?
- **Accuracy**: Does a rock-solid AI OCR out of the gate provide better results than the current ensemble-then-repair approach?
- **Pipeline Impact**: Identify how many downstream modules (cleaning, dedupe, etc.) could be simplified or removed if OCR quality is high enough.

---

## Success Criteria

- [ ] **Benchmark comparison**: Compare Gemini 3 Flash, Mistral OCR 3, and other "cheap/good" models against the current 3-engine ensemble + GPT escalation.
- [ ] **Cost-benefit analysis**: Document total cost per book for "Ensemble+Escalation" vs "AI-First OCR".
- [ ] **Architectural proposal**: A draft of a "Simplified Pipeline" that removes redundant repair/voting stages.
- [ ] **Validation**: Verify that AI-First OCR handles fused headers and complex layouts without specialized heuristics.
- [ ] **Evidence**: Samples of OCR output from Gemini 3 Flash and Mistral OCR 3 on Deathtrap Dungeon "trouble pages".

---

## Candidates for "Primary AI OCR"

- **Gemini 3 Flash** (Released 2025-12-17): Top candidate for low-cost/high-quality vision.
- **Mistral OCR 3** (Released 2025-12-18): Specialized OCR model from Mistral.
- **GPT-5 Nano/Mini**: OpenAI's cost-optimized tiers.
- **Claude 3.5 Haiku / Sonnet**: Anthropic's efficiency/quality balance.
- **Hugging Face (Molmo / Qwen2-VL / Idefics)**: SOTA open-source models that can be hosted cheaply via serverless inference or dedicated endpoints.

---

## Tasks

### Phase 1: Rapid Benchmarking
- [ ] **Targeted Test**: Run Gemini 3 Flash and Mistral OCR 3 on the 20-page FF smoke set and compare accuracy to current ensemble output.
- [ ] **Failure Case Stress Test**: Run on "trouble pages" (fused headers, garbled text, low contrast).
- [ ] **Cost Logging**: Calculate exact cost for a 400-page book using AI-First OCR vs current hybrid stack.

### Phase 2: Pipeline Simplification Audit
- [ ] **Module Dependency Check**: List modules (clean, consensus, extract) that primarily fix bad OCR.
- [ ] **Simplified Recipe Draft**: Create a "Radical Simplification" recipe skipping ensemble/voting/repair.

### Phase 3: Prototyping
- [ ] **New Module Spike**: Create a minimal `intake_ai_ocr_v1` module.
- [ ] **End-to-End Run**: Run a 20-page sample through the simplified pipeline and compare final `gamebook.json` quality.

---

## Context

**Current Architecture**:
- 3-Engine Ensemble (Tesseract + EasyOCR + Apple Vision)
- Voting logic + post-OCR spell repair + escalation to GPT-4V.
- **Complexity**: High (many moving parts, multiple failure points).

**Proposed Architecture (Hypothesis)**:
- Single High-Quality AI OCR (e.g., Gemini 3 Flash or Mistral OCR 3)
- Direct to content-type classification and portionization.
- **Simplicity**: Very High (one source of truth, fewer stages).

---

## Work Log

### 2025-12-17 — Story created
- **Scope**: Evaluate radical pipeline simplification using "AI-First" OCR.
- **Hypothesis**: Gemini 3 Flash makes the complex ensemble/escalation logic obsolete.

### 2025-12-18 — Mistral OCR 3 & Hugging Face Added
- **Note**: Mistral OCR 3 released today. It is a specialized OCR model that may provide a strong alternative for high-fidelity extraction.
- **Update**: Added Hugging Face candidates (Molmo, Qwen2-VL). These models could provide SOTA vision performance at very low cost via optimized inference providers.
- **Next**: Run benchmarks on Gemini 3 Flash, Mistral OCR 3, and top HF vision candidates.

