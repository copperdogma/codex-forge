You are a research agent. Your task is to identify the **current SOTA (as of 2025-12-19)** vision/OCR models suitable for document OCR at scale, emphasizing **cost/quality/performance** tradeoffs. Provide **sources** and **evidence** for every claim (model release date, pricing, benchmarks, OCR/Doc understanding claims).

**Goal:** Produce a shortlist of **6–12 models** to benchmark for an AI‑first OCR pipeline. Models must be **API‑accessible** (no self‑hosting), and optimized for **books** in **English**.

**Scope / Constraints**
- Document type: **books** (scanned pages, multi‑column text, occasional tables).
- Language: **English only**.
- Deployment: **API only** (exclude self‑host‑only models).
- Throughput: **batch / one‑off** is fine; up to ~60s/page acceptable for high quality.
- Focus on models that can perform **high‑fidelity OCR** from page images (books, multi‑column text, tables).
- Include both **low‑cost** and **high‑quality** options; we will pick a diverse set.
- Prefer models released or updated in the last 12 months if available.
- Include the best model in the world regardless of price as a high-water benchmark.
- We are specifically comparing to a multi‑engine OCR ensemble (tesseract/easyocr/apple) + escalation. We want candidates that could **replace** that stack.

**Required Output**
1) **Shortlist (6–12 models)** with:
   - Provider / model name
   - Release/update date (with source)
   - Pricing (per image / per 1K tokens or equivalent; with source)
   - Why it’s promising for OCR (benchmarks, OCR claims, doc‑QA performance, etc.)
   - Known limitations (e.g., layout failures, hallucinations, slow latency)
2) **Top 3 recommendations** and rationale
3) **Evidence appendix**: links/sources for each model

**Candidate classes to consider**
- Google (Gemini family), OpenAI (GPT‑5 / vision variants), Anthropic (Claude 3.5+), Mistral (OCR‑specific), Cohere, AWS/Bedrock, Azure AI, etc.
- Open‑weight models: Qwen2‑VL, Qwen2.5‑VL, IDEFICS, Molmo, PaliGemma, LLaVA‑Next, Donut variants, etc.
- Dedicated OCR models (commercial).
- If an open‑weight model is only available via a hosted API, include it; otherwise exclude.

**Evaluation lens**
- OCR accuracy on noisy scans
- Layout / table preservation
- Cost per page
- Latency / throughput
- Deployment options (API vs self‑hosted)

Return your findings in a concise, structured report suitable for engineering decision‑making. Do not ask follow‑up questions; use the constraints above.