# Story: AI Vision Engine Evaluation — Best Value for Pipeline

**Status**: To Do  
**Created**: 2025-12-17  
**Updated**: 2025-12-18 (Added Mistral OCR 3)
**Priority**: Medium

---

## Goal

Evaluate AI vision engines to determine which provides the best value for the codex-forge pipeline. Compare across multiple providers, model sizes (small to large), and use cases to identify optimal cost/quality/performance tradeoffs for OCR, page cleaning, boundary detection, and other vision-dependent stages.

**Key Focus Areas**:
- Compare existing engines (GPT-4V, GPT-5 series) against new releases:
  - Gemini Flash 3 (released 2025-12-17)
  - Mistral OCR 3 (released 2025-12-18)
- Evaluate both smaller (cost-effective) and larger (quality-focused) models within each provider.
- Research alternative vision models that may outperform current options.
- Determine best value proposition for pipeline stages (OCR, cleaning, boundary detection, content type classification).

---

## Success Criteria

- [ ] **Comprehensive model inventory**: Document all relevant vision models from major providers (OpenAI, Google, Anthropic, Mistral, others) with pricing, capabilities, and release dates.
- [ ] **Benchmark results**: Run comparative tests on representative pipeline tasks (OCR accuracy, text extraction quality, layout understanding, cost per page).
- [ ] **Value analysis**: Produce cost/quality/performance matrix comparing models across pipeline use cases.
- [ ] **Recommendations**: Clear guidance on which models to use for which pipeline stages, with justification.
- [ ] **Integration plan**: Identify any new engines worth integrating and document integration requirements.
- [ ] **Evidence-based**: All comparisons backed by actual test runs on real pipeline data (Deathtrap Dungeon sample pages).

---

## Models to Evaluate

### OpenAI
- **GPT-4V (gpt-4o, gpt-4-turbo)**: Current baseline.
- **GPT-5 series**: 
  - GPT-5 (flagship)
  - GPT-5 mini / nano / pro (cost-optimized tiers)
  - GPT-5.1 (if available with vision)

### Google
- **Gemini Flash 3** (released 2025-12-17): New release to evaluate.
- **Gemini Pro / Ultra**: Larger models for comparison.
- **Gemini 1.5 Flash / Pro**: Previous generation for baseline.

### Mistral
- **Mistral OCR 3** (released 2025-12-18): New specialized OCR model for high-fidelity extraction.

### Anthropic
- **Claude Sonnet / Opus** (if vision-capable): Evaluate if applicable.

### Hugging Face / Open Source
- **Molmo / Idefics / Qwen2-VL**: Investigate current SOTA open-source vision models.
- **Cost Analysis**: Research Inference Endpoints, Serverless Inference, or local hosting costs on ARM64/MPS.
- **Value**: Open-source models on Hugging Face can often be run surprisingly cheaply via specialized providers or dedicated inference endpoints.

---

## Evaluation Tasks

### Phase 1: Research & Inventory
- [ ] **Model discovery**: Research all available vision models from major providers.
- [ ] **Hugging Face Sweep**: Search Hugging Face Hub for SOTA vision models (Molmo, Qwen, etc.) and evaluate their reported OCR/layout performance.
- [ ] **Pricing collection**: Gather current pricing for all models (per token, per image, rate limits).
- [ ] **Inference Costs**: Specifically research the cheapest way to run Hugging Face models (Inference Endpoints, Modal, Groq, Together, etc.).
- [ ] **Capability mapping**: Document vision capabilities (OCR quality, layout understanding, multimodal reasoning, context windows).

### Phase 2: Benchmark Design
- [ ] **Test dataset**: Select representative pages from Deathtrap Dungeon (clean text, fused headers, complex layouts).
- [ ] **Metrics**: Define criteria: OCR accuracy, layout preservation, cost per page, latency.

### Phase 3: Comparative Testing
- [ ] **Test Runs**: Run OpenAI, Google, and Mistral models on benchmark set.
- [ ] **Pipeline integration**: Run tests through actual pipeline stages.

---

## Work Log

### 2025-12-17 — Story created
- **Scope**: Comprehensive evaluation of AI vision engines for pipeline optimization.

### 2025-12-18 — Mistral OCR 3 & Hugging Face Added
- **Note**: Mistral OCR 3 released today (2025-12-18). Included in the evaluation list as a specialized OCR candidate.
- **Update**: Added Hugging Face models (Molmo, Qwen2-VL, etc.) to the comparison list. Research indicates open-source SOTA models can often be hosted cheaply or used via high-performance inference providers.
- **Next**: Begin benchmarking Gemini Flash 3, Mistral OCR 3, and identifying top 2-3 HF candidates.

