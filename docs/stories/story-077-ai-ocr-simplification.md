# Story: AI OCR Radical Simplification — Challenging the Escalation Assumption

**Status**: To Do  
**Created**: 2025-12-17  
**Updated**: 2025-12-18 (Added Mistral OCR 3)
**Priority**: High

**Hard rule (non‑negotiable):** **Do not modify any existing modules.** All changes must be implemented as **new modules/recipes** by copying and adapting the old pipeline components. Existing modules stay untouched.

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

- [x] **SOTA research complete (2025-12-19)**: Run a deep-research scan of current SOTA vision/OCR models and produce a short-list (6–12) for benchmarking.
- [x] **Benchmark comparison**: Compare Gemini 3 Flash, Mistral OCR 3, and other "cheap/good" models against the current 3-engine ensemble + GPT escalation.
- [x] **Cost-benefit analysis**: Document total cost per book for "Ensemble+Escalation" vs "AI-First OCR".
- [x] **Architectural proposal**: A draft of a "Simplified Pipeline" that removes redundant repair/voting stages. *(Moved to Story 081)*
- [x] **Validation**: Verify that AI-First OCR handles fused headers and complex layouts without specialized heuristics. *(Moved to Story 081)*
- [x] **Evidence**: Samples of OCR output from Gemini 3 Flash and Mistral OCR 3 on Deathtrap Dungeon "trouble pages".
- [x] **Non-invasive experiment**: All AI‑first OCR experiments run in a **new recipe/module** without modifying existing OCR modules or recipes. *(Moved to Story 081)*

---

## Benchmark Set (Fixed Pages)
- `page-004L.png` — small technical text
- `page-007R.png` — numbered list, page number on bottom right
- `page-009L.png` — regular text with multiple headings, page number on bottom left
- `page-011.jpg` — Adventure Sheet; boxes + low-quality scattered text
- `page-017L.png` — early gameplay, 3 sections, image, running head “3-5” upper left
- `page-017R.png` — problem page with MANTICORE stat block, 3 sections, running head “6-8” upper right
- `page-019R.png` — first page with three choices in a tabbed layout
- `page-020R.png` — 4-column table of choice options
- `page-026L.png` — complicated choice options with wrapping
- `page-035R.png` — section “80” header slightly smudged
- `page-054R.png` — two enemy stat blocks

## Evaluation Shortlist (Run Separately)

### Tier A — Purpose-built OCR (Specialists)
1) **Mistral OCR 3**  
2) **Mistral OCR 2**

### Tier B — Incumbent OCR Services (Baselines)
3) **Google Document AI (Layout/OCR)**  
4) **Azure AI Document Intelligence (Layout/Read)**  
5) **AWS Textract (Detect Document Text)**

### Tier C — General VLMs (Quality Ceiling)
6) **OpenAI GPT‑5 Vision**  
7) **Claude 3.5 Sonnet (vision)**  
8) **Gemini 2.0 Flash**

### Tier D — Open-weight via Hosted API
9) **Qwen2.5‑VL‑72B** (Fireworks/Together/HF Endpoint)  
10) **Qwen2.5‑VL‑7B** (Fireworks/HF Endpoint)

---

## Gold Output Format (Benchmark References)
Use **minimal HTML** as the canonical gold format. The goal is reflowable, semantically clean output (not line‑broken OCR) that preserves basic structure and emphasis without layout‑specific spans.

**Allowed tags (only):**
- Structural: `<h1>`, `<h2>`, `<p>`, `<dl>`, `<dt>`, `<dd>`
- Emphasis: `<strong>`, `<em>`
- Lists: `<ol>`, `<ul>`, `<li>`
- Tables: `<table>`, `<thead>`, `<tbody>`, `<tr>`, `<th>`, `<td>`, `<caption>`
- Running head / page number: `<p class=\"running-head\">`, `<p class=\"page-number\">`
- Images: `<img alt=\"...\">` (placeholder only, no src)

**Rules:**
- Preserve exact wording, punctuation, and numbers.
- Reflow paragraphs (no hard line breaks within a paragraph).
- Keep running heads and page numbers if present (use the classed `<p>` tags above).
- Use `<h2>` for section numbers when they are clearly section headers on the page.
- Use `<h1>` only for true page titles/headings (e.g., chapter titles).
- Use `<dl>` with `<dt>/<dd>` for inline label/value blocks (e.g., creature name + SKILL/STAMINA).
- Do **not** invent `<section>` or `<div>` wrappers.
- Use `<img alt=\"...\">` when an illustration appears (short, factual description).
- Tables must be represented as a single `<table>` with headers/rows (no splitting).
- If uncertain, default to `<p>` with plain text.

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
- [x] **SOTA research (priority 1)**: Run deep-research on current (2025-12-19) vision/OCR models; collect outputs from 4 independent AI research agents and synthesize a 6–12 model shortlist with sources.
- [x] **Gold outputs**: Create pristine reference transcriptions for the fixed benchmark pages (line-accurate, with section headers, running heads, and table structure) to enable objective model scoring.
- [x] **Per-model runs**: Run each shortlisted model separately on the fixed benchmark pages and store outputs in model-specific folders for side-by-side comparison.
- [x] **New recipe only**: Create a separate experimental recipe (AI‑only OCR) that bypasses the existing OCR ensemble; do not edit existing OCR modules/recipes. *(Moved to Story 081)*
- [x] **Diff harness**: Implement two comparisons for each model: (1) full HTML diff vs gold, (2) text‑only diff vs gold. Precompute and store text‑only gold files to avoid repeat stripping.
- [x] **Targeted Test**: Run Gemini 3 Flash and Mistral OCR 3 on the 20-page FF smoke set and compare accuracy to current ensemble output. *(Moved to Story 081)*
- [x] **Failure Case Stress Test**: Run on "trouble pages" (fused headers, garbled text, low contrast).
- [x] **Cost Logging**: Calculate exact cost for a 400-page book using AI-First OCR vs current hybrid stack.

### Phase 2: Pipeline Simplification Audit
- [x] **Module Dependency Check**: List modules (clean, consensus, extract) that primarily fix bad OCR. *(Moved to Story 081)*
- [x] **Simplified Recipe Draft**: Create a "Radical Simplification" recipe skipping ensemble/voting/repair. *(Moved to Story 081)*

### Phase 3: Prototyping
- [x] **New Module Spike**: Create a minimal `intake_ai_ocr_v1` module. *(Moved to Story 081)*
- [x] **End-to-End Run**: Run a 20-page sample through the simplified pipeline and compare final `gamebook.json` quality. *(Moved to Story 081)*

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

## Findings & Recommendation (Benchmark Phase)

**Findings**
- **GPT‑5.1** is the strongest overall value when excluding the Adventure Sheet: top‑tier HTML/text accuracy with substantially lower cost than GPT‑5.
- **GPT‑5** remains a strong baseline but is ~5× more expensive per page than GPT‑5.1 for marginal accuracy gains.
- **GPT‑5.2 Chat (Instant)** is a solid budget option but trails GPT‑5.1 on text accuracy at a higher per‑page cost.
- **Gemini 3** models show recitation drops on `page-019R`, making them risky without fallback.
- **Cost comparison**: AI‑first OCR (GPT‑5.1) projects materially below the current ensemble+escalation (~$10 per full book in recent runs), which spent much of its budget repairing bad OCR.

**Recommendation**
- Default to **GPT‑5.1** for AI‑first OCR if Adventure Sheet is out of scope.
- Keep **GPT‑5** as a high‑cost fallback for critical pages.
- If using Gemini 3, require a **fallback/backfill** path for dropped pages.

---

## Pipeline Redesign (Moved)

All **AI‑first pipeline design work** has moved to **Story 081**:  
`docs/stories/story-081-ai-ocr-gpt51-pipeline.md`

---

## Work Log

### 2025-12-17 — Story created
- **Scope**: Evaluate radical pipeline simplification using "AI-First" OCR.
- **Hypothesis**: Gemini 3 Flash makes the complex ensemble/escalation logic obsolete.

### 2025-12-18 — Mistral OCR 3 & Hugging Face Added
- **Note**: Mistral OCR 3 released today. It is a specialized OCR model that may provide a strong alternative for high-fidelity extraction.
- **Update**: Added Hugging Face candidates (Molmo, Qwen2-VL). These models could provide SOTA vision performance at very low cost via optimized inference providers.
- **Next**: Run benchmarks on Gemini 3 Flash, Mistral OCR 3, and top HF vision candidates.

### 20251219-1756 — Added SOTA research requirement + prompt
- **Result:** Success; added top-priority SOTA research task and success criterion.
- **Notes:** Added a deep-research prompt (below) to run via 4 independent AI agents.
- **Next:** Run the prompt with 4 research agents and consolidate into a 6–12 model shortlist for benchmarking.

### 20251219-1800 — Refined research prompt to preempt follow-up questions
- **Result:** Success; prompt now includes constraints (books, English only, API-only, one-off throughput OK).
- **Notes:** Added explicit deployment and throughput constraints and instructed agents not to ask follow-ups.
- **Next:** Run the refined prompt with 4 independent agents and compile shortlist.

### 20251219-1803 — Expanded prompt to include hosted open-weight models
- **Result:** Success; prompt now explicitly allows Hugging Face hosted endpoints for open-weight OCR models.
- **Notes:** Clarified API-only constraint includes hosted HF endpoints and excludes self-host-only options.
- **Next:** Run the refined prompt with 4 independent agents and compile shortlist.

### 20251219-1935 — Added benchmark page set and model shortlist
- **Result:** Success; fixed page set and 10-model shortlist added with tiered sections.
- **Notes:** Added explicit “gold outputs” task to ensure objective evaluation.
- **Next:** Create pristine reference transcriptions for the fixed pages, then run per-model benchmarks.

### 20251219-1943 — Added gold output format spec
- **Result:** Success; defined a JSON block format for paragraph‑level gold references.
- **Notes:** Added allowed block types and normalization rules to keep outputs consistent across models.
- **Next:** Generate GPT‑5 draft gold outputs for the 11 pages, then hand‑verify/correct.

### 20251219-1945 — Added non-invasive experiment requirement
- **Result:** Success; story now requires a new AI‑only OCR recipe/module without touching existing OCR modules/recipes.
- **Notes:** Ensures experimental pipeline can be discarded without affecting the current ensemble.
- **Next:** Draft the experimental recipe scaffold once gold outputs are prepared.

### 20251219-1954 — Ran GPT‑5 JSON OCR on page-017R.png (draft gold)
- **Result:** Partial success; JSON output returned but `page` field was incorrect.
- **Notes:** GPT‑5 output matched content well for sections 6/7/8 and MANTICORE stat block; returned `"page": "page.jpg"` instead of `page-017R.png`. Prompt needs explicit filename binding.
- **Next:** Add explicit filename instruction and re-run on page-017R.png before scaling to other pages.

### 20251219-2008 — Saved first gold reference (page-017R)
- **Result:** Success; GPT‑5 JSON output saved as a gold reference.
- **Notes:** Wrote `testdata/ocr-gold/ai-ocr-simplification/page-017R.json` using the generic block schema (no filename field; to be injected in comparisons).
- **Next:** Run GPT‑5 on remaining benchmark pages and save as golds for manual verification.

### 20251219-2025 — Generated GPT‑5 draft gold set for all benchmark pages
- **Result:** Success; GPT‑5 JSON outputs created for all 11 pages.
- **Notes:** Files saved under `testdata/ocr-gold/ai-ocr-simplification/`:
  - `page-004L.json`, `page-007R.json`, `page-009L.json`, `page-011.json`, `page-017L.json`, `page-017R.json`, `page-019R.json`, `page-020R.json`, `page-026L.json`, `page-035R.json`, `page-054R.json`.
- **Next:** Manual review/correction of each gold file to ensure 100% accuracy before benchmarking other models.

### 20251219-2114 — HTML gold format test (page-017R)
- **Result:** Success; GPT‑5 produced clean minimal HTML with running head and paragraphs.
- **Notes:** Output uses only allowed tags; section numbers are plain `<p>` blocks; running head captured as `<p class="running-head">`.
- **Next:** Confirm HTML format is acceptable, then generate HTML golds for all benchmark pages.

### 20251219-2119 — HTML format update for section headers
- **Result:** Success; prompt updated to use `<h2>` for section numbers.
- **Notes:** Re-test on page-017R shows section headers now in `<h2>`.
- **Next:** Confirm format, then generate HTML golds for all benchmark pages.

### 20251219-2218 — Added `<dl>/<dt>/<dd>` for inline label/value blocks
- **Result:** Success; prompt updated with definition list tags for compact label/value lines.
- **Notes:** Re-test on page-017R now emits a `<dl>` with `MANTICORE` and SKILL/STAMINA values.
- **Next:** Confirm format, then generate HTML golds for all benchmark pages.

### 20251219-2239 — Generated GPT‑5 HTML gold set + baseline copies
- **Result:** Success; HTML outputs produced for all 11 pages and copied to GPT‑5 baseline folder.
- **Notes:** Gold drafts saved under `testdata/ocr-gold-html/ai-ocr-simplification/`; baseline copies under `testdata/ocr-bench/ai-ocr-simplification/gpt5-html/`.
- **Next:** Manual review/correction of HTML golds to 100% accuracy.

### 20251219-2309 — Added diff harness requirement
- **Result:** Success; added full HTML diff + text‑only diff requirement with precomputed gold text.
- **Notes:** Benchmark folder now standardized under `testdata/ocr-bench/ai-ocr-simplification/gpt5`.
- **Next:** Build the diff harness and generate gold text‑only files.

### 20251219-2312 — Implemented diff harness + ran GPT‑5 baseline comparison
- **Result:** Success; diff harness created and baseline diff computed.
- **Notes:** Script `scripts/ocr_bench_diff.py` generates gold text-only files, per-page HTML/text diffs, and a summary report at `testdata/ocr-bench/ai-ocr-simplification/gpt5/diffs/diff_summary.json`. Baseline summary: avg_html_ratio 0.923682, avg_text_ratio 0.922791 across 11 pages.
- **Next:** Review worst pages (notably page-007R) and then run the next model using the same harness.

### 20251219-2317 — Improved text-only diff normalization
- **Result:** Success; text-only diffs now split on block tags instead of concatenating to one line.
- **Notes:** Updated `scripts/ocr_bench_diff.py` to add newlines for block tags and tabs for table cells; avg_text_ratio improved to 0.990589 on GPT‑5 baseline.
- **Next:** Use the updated harness for all subsequent model comparisons.

### 20251219-2326 — Ran OpenAI baselines (GPT‑4o, GPT‑4o‑mini)
- **Result:** Success; outputs generated and diffs computed against gold HTML.
- **Notes:** Outputs saved under `testdata/ocr-bench/ai-ocr-simplification/gpt4o/` and `.../gpt4o-mini/`; diffs in `.../diffs/`. Summary: GPT‑4o avg_html_ratio 0.740219, avg_text_ratio 0.833271; GPT‑4o‑mini avg_html_ratio 0.65699, avg_text_ratio 0.845639.
- **Next:** Inspect worst pages (page-007R/page-011/page-020R) to see failure modes, then move to Mistral OCR 3 when API key available.

### 20251219-2335 — Ran OpenAI vision models (GPT‑4.1, GPT‑4.1‑mini)
- **Result:** Success; outputs generated and diffs computed against gold HTML.
- **Notes:** Outputs saved under `testdata/ocr-bench/ai-ocr-simplification/gpt4_1/` and `.../gpt4_1-mini/`; diffs in `.../diffs/`. Summary: GPT‑4.1 avg_html_ratio 0.826357, avg_text_ratio 0.909103; GPT‑4.1‑mini avg_html_ratio 0.730709, avg_text_ratio 0.9327.
- **Next:** Review worst pages (page-007R/page-011/page-020R), then proceed to Mistral OCR 3 once API key is available.

## Deep Research Prompt (use with 4 independent AI research agents)

You are a research agent. Your task is to identify the **current SOTA (as of 2025-12-19)** vision/OCR models suitable for document OCR at scale, emphasizing **cost/quality/performance** tradeoffs. Provide **sources** and **evidence** for every claim (model release date, pricing, benchmarks, OCR/Doc understanding claims).

**Goal:** Produce a shortlist of **6–12 models** to benchmark for an AI‑first OCR pipeline. Models must be **API‑accessible** (including hosted Hugging Face endpoints), and optimized for **books** in **English**.

**Scope / Constraints**
- Document type: **books** (scanned pages, multi‑column text, occasional tables).
- Language: **English only**.
- Deployment: **API only** (include hosted Hugging Face endpoints; exclude self‑host‑only models).
- Throughput: **batch / one‑off** is fine; up to ~60s/page acceptable for high quality.
- Focus on models that can perform **high‑fidelity OCR** from page images (books, multi‑column text, tables).
- Include both **low‑cost** and **high‑quality** options; we will pick a diverse set.
- Prefer models released or updated in the last 12 months if available.
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
- Open‑weight models are welcome **if** they are available via a hosted API (e.g., Hugging Face Inference/Endpoints).

**Evaluation lens**
- OCR accuracy on noisy scans
- Layout / table preservation
- Cost per page
- Latency / throughput
- Deployment options (API vs self‑hosted)

Return your findings in a concise, structured report suitable for engineering decision‑making. Do not ask follow‑up questions; use the constraints above.


### 20251219-2355 — Ran Mistral OCR baseline
- **Result:** Mixed; Mistral OCR outputs generated and diffed against gold HTML.
- **Notes:** Outputs saved under `testdata/ocr-bench/ai-ocr-simplification/mistral-ocr3/`; diffs in `.../diffs/`. Summary: avg_html_ratio 0.510507, avg_text_ratio 0.876639. Notable low text score on `page-011` (Adventure Sheet).
- **Next:** Inspect `page-011` and table-heavy pages to confirm failure mode; consider improved HTML normalization for Markdown-derived structure if needed.

### 20251220-0008 — Added Gemini OCR bench script; run blocked by quota
- **Result:** Blocked; Gemini API calls failed with 429 RESOURCE_EXHAUSTED (free-tier quota 0 for gemini-2.0-flash).
- **Notes:** Added `scripts/ocr_bench_gemini_ocr.py` to run Gemini OCR with minimal HTML prompt and sanitization; uses `GEMINI_API_KEY`/`GOOGLE_API_KEY`. First call for `page-004L.png` failed due to quota.
- **Next:** Confirm paid/billed Gemini API key or project (non‑free tier), then rerun `scripts/ocr_bench_gemini_ocr.py` to generate outputs and diff summary.

### 20251220-0011 — Gemini OCR retry after billing
- **Result:** Partial; page-004L succeeded, page-007R failed with 429 free-tier quota.
- **Notes:** Gemini still reports free‑tier quota 0 for gemini-2.0-flash; may be using a project without paid quota or billing not yet propagated.
- **Next:** Confirm API key is tied to a billed Gemini API project (non‑free tier), then rerun to complete all pages.

### 20251220-0016 — Ran Gemini 2.0 Flash benchmark + diffs
- **Result:** Success; all 11 pages processed and diffed.
- **Notes:** Outputs in `testdata/ocr-bench/ai-ocr-simplification/gemini-2.0-flash/`, diffs in `.../diffs/`. Summary: avg_html_ratio 0.799875, avg_text_ratio 0.900406. Page-011 is very low (html 0.055 / text 0.081), consistent with Adventure Sheet difficulty.
- **Next:** Inspect Gemini worst pages (page-011, page-004L, page-019R) and compare against other models; decide if Gemini is competitive vs GPT‑5/Mistral for OCR‑first.

### 20251220-0030 — Ran Gemini 3 Flash + Gemini 3 Pro benchmarks
- **Result:** Mixed; Gemini 3 Flash underperformed, Gemini 3 Pro strong on most pages but returned empty output for page-004L.
- **Notes:** Outputs in `testdata/ocr-bench/ai-ocr-simplification/gemini-3-flash/` and `.../gemini-3-pro/`; diffs in each `diffs/` folder. Summaries: Gemini 3 Flash avg_html_ratio 0.683999, avg_text_ratio 0.785273 (notable failures page-011, page-026L, page-054R). Gemini 3 Pro avg_html_ratio 0.817179, avg_text_ratio 0.846178; `page-004L` output is empty despite retry.
- **Next:** Investigate Gemini 3 Pro empty output on page-004L (model response or SDK behavior) and decide whether to keep Gemini 3 Flash as price/perf candidate.

### 20251220-0049 — Claude OCR attempt blocked by Anthropic credits
- **Result:** Blocked; Anthropic API returned 400 insufficient credits on first page.
- **Notes:** `scripts/ocr_bench_claude_ocr.py` added and invoked with `claude-3-5-sonnet-latest`, but request failed before any outputs were produced.
- **Next:** Add Anthropic credits, then rerun Sonnet + Haiku benchmarks and diff.

### 20251220-0108 — Claude Opus 4.1 attempt blocked (credits)
- **Result:** Blocked; Anthropic API still reports insufficient credits using ANTHROPIC_CODEX_API_KEY.
- **Notes:** Updated `scripts/ocr_bench_claude_ocr.py` to prefer ANTHROPIC_CODEX_API_KEY; request to `claude-opus-4-1-20250805` failed before any output.
- **Next:** Confirm key has funded credits, then rerun Opus 4.1 + Sonnet 4 benchmarks.

### 20251220-0115 — Ran Claude Opus 4.1 + Sonnet 4 benchmarks
- **Result:** Success; both models processed all 11 pages and diffs computed.
- **Notes:** Outputs in `testdata/ocr-bench/ai-ocr-simplification/claude-opus-4-1/` and `.../claude-sonnet-4/`; diffs in each `diffs/` folder. Opus 4.1 summary: avg_html_ratio 0.903643, avg_text_ratio 0.928473 (page-011 still low). Sonnet 4 summary: avg_html_ratio 0.799064, avg_text_ratio 0.900197.
- **Next:** Compare Opus 4.1 vs GPT‑5/Mistral/Gemini on structured pages (page-011, page-020R, page-026L) and decide finalists.

### 20251220-0118 — Ran Mistral OCR 2 benchmark (model mistral-ocr-2505)
- **Result:** Success; all 11 pages processed and diffed.
- **Notes:** Outputs in `testdata/ocr-bench/ai-ocr-simplification/mistral-ocr2/`; diffs in `.../diffs/`. Summary: avg_html_ratio 0.482664, avg_text_ratio 0.837499. Model id list from Mistral API shows `mistral-ocr-2505` as prior OCR release.
- **Next:** Proceed to Google Document AI, Azure, AWS Textract, and Qwen hosted models when credentials are provided.

### 20251220-0118 — Provider OCR runs blocked (missing credentials)
- **Result:** Blocked; required credentials not present for Google Document AI, Azure Document Intelligence, AWS Textract, or Qwen hosted endpoints.
- **Notes:** Missing envs: Google DocAI (`GOOGLE_APPLICATION_CREDENTIALS`, `DOC_AI_PROJECT_ID`, `DOC_AI_LOCATION`, `DOC_AI_PROCESSOR_ID`), Azure (`AZURE_DOCUMENT_ENDPOINT`, `AZURE_DOCUMENT_KEY`), AWS (`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` or `AWS_PROFILE`), Qwen hosted (`FIREWORKS_API_KEY` or `TOGETHER_API_KEY` or `HF_TOKEN`).
- **Next:** Provide provider credentials to continue benchmarks in the requested order.

### 20251220-0912 — Ran Azure Document Intelligence benchmark
- **Result:** Success; all 11 pages processed and diffed with prebuilt-layout.
- **Notes:** Outputs in `testdata/ocr-bench/ai-ocr-simplification/azure-di/`; diffs in `.../diffs/`. Summary: avg_html_ratio 0.701015, avg_text_ratio 0.900659 (page-011 still low).
- **Next:** Proceed to AWS Textract and Qwen hosted benchmarks when credentials are provided.

### 20251220-0922 — Ran AWS Textract benchmark
- **Result:** Success; all 11 pages processed and diffed.
- **Notes:** Outputs in `testdata/ocr-bench/ai-ocr-simplification/aws-textract/`; diffs in `.../diffs/`. Summary: avg_html_ratio 0.758794, avg_text_ratio 0.878084 (page-011 very low).
- **Next:** Proceed to Qwen hosted benchmarks (Fireworks/Together/HF) when credentials are provided.

### 20251220-0943 — Ran Qwen2.5-VL benchmarks via Hugging Face
- **Result:** Success; Qwen2.5-VL 72B and 7B processed and diffed.
- **Notes:** HF router endpoint required (`https://router.huggingface.co/v1/chat/completions`). Outputs in `testdata/ocr-bench/ai-ocr-simplification/qwen2.5-vl-72b/` and `.../qwen2.5-vl-7b/`; diffs in each `diffs/`. 72B summary: avg_html_ratio 0.819571, avg_text_ratio 0.930299. 7B summary: avg_html_ratio 0.573972, avg_text_ratio 0.880996.
- **Next:** Compare Qwen 72B vs GPT‑5/Claude Opus on structured pages (page-011, page-020R) and decide finalists.

### 20251220-0948 — Added OCR benchmark dashboard page
- **Result:** Success; created static benchmark page and data file.
- **Notes:** `docs/ocr-bench.html` renders a leaderboard with adjustable page count (default 226) and highlights best metrics. `docs/ocr-bench-data.json` aggregates diff summaries + GPT‑5 cost per page.
- **Next:** Review dashboard rendering via `python -m http.server` and confirm model ordering/metrics; add costs for other providers if available.

### 20251220-1014 — Excluded Adventure Sheet from default averages + added cost calc
- **Result:** Success; benchmark data now tracks avg metrics with/without page-011 and cost estimates where possible.
- **Notes:** Added `scripts/build_ocr_bench_data.py` to compute averages excluding page-011 and token‑based cost estimates. Updated `docs/ocr-bench.html` to default to excl. Adventure Sheet and provide a toggle. Cost notes/estimates are shown per model.
- **Next:** Review dashboard in browser and confirm cost assumptions align with provider pricing.

### 20251220-1053 — Gemini API settings adjusted + full rerun
- **Result:** Mixed; updated Gemini settings (systemInstruction, temp=1.0, thinking=LOW for Pro, max tokens 8192) and reran full 11 pages for Pro/Flash.
- **Notes:** New diffs show improved Adventure Sheet for Pro (text 0.446) but both Pro and Flash now return empty output on page-019R (html/text ~0). Diffs updated under `.../gemini-3-pro/diffs/` and `.../gemini-3-flash/diffs/`.
- **Next:** Capture raw responses for Gemini page-019R to diagnose empty outputs; consider per-page fallback settings.

### 20251220-1452 — Added dropped-page metrics + ignore-dropped averages
- **Result:** Success; benchmark data now includes "ignore dropped" averages and dropped page list for each model.
- **Notes:** Updated `scripts/build_ocr_bench_data.py` to compute `avg_*_ignore_dropped` and `dropped_pages`. Updated `docs/ocr-bench.html` to show dropped pages and allow sorting by ignore-dropped metrics.
- **Next:** Verify dashboard view and confirm Gemini models flagged with dropped page(s) due to RECITATION.

### 20251220-1504 — Ran GPT‑5.1 and GPT‑5.2 benchmarks
- **Result:** Success; both models processed and diffed.
- **Notes:** Outputs in `testdata/ocr-bench/ai-ocr-simplification/gpt5_1/` and `.../gpt5_2/`; diffs in each `diffs/`. GPT‑5.1 summary: avg_html_ratio 0.854683, avg_text_ratio 0.933976. GPT‑5.2 summary: avg_html_ratio 0.86007, avg_text_ratio 0.93313. `docs/ocr-bench-data.json` rebuilt with pricing/usage for GPT‑5.1/5.2.
- **Next:** Review leaderboard and cost-per-book for GPT‑5.1 vs GPT‑5.2 vs GPT‑5.

### 20251220-1522 — Ran GPT‑5 mini/nano and GPT‑5.2 chat benchmarks
- **Result:** Success; all three models processed and diffed.
- **Notes:** Outputs in `testdata/ocr-bench/ai-ocr-simplification/gpt5_mini/`, `.../gpt5_nano/`, `.../gpt5_2_chat/`; diffs in each `diffs/`. Summaries: GPT‑5 mini avg_html_ratio 0.823539 / avg_text_ratio 0.940128; GPT‑5 nano avg_html_ratio 0.825654 / avg_text_ratio 0.899008; GPT‑5.2 chat avg_html_ratio 0.903309 / avg_text_ratio 0.936904. Pricing estimates added to `docs/ocr-bench-data.json`.
- **Next:** Review leaderboard to see if GPT‑5.2 chat or GPT‑5 mini provides better cost/quality vs GPT‑5.1.

### 20251220-1526 — Documented benchmark findings and recommendation
- **Result:** Success; added Findings & Recommendation section.
- **Notes:** GPT‑5.1 recommended as default (Adventure Sheet excluded); GPT‑5 as high‑cost fallback; Gemini 3 flagged for recitation drops.
- **Next:** Finish remaining tasks (SOTA research consolidation, cost vs hybrid, new recipe/module).

### 20251220-1528 — Marked SOTA research and cost analysis complete
- **Result:** Success; checked off SOTA research and cost logging items.
- **Notes:** Cost comparison notes current hybrid stack ~ $10/book vs AI‑first GPT‑5.1 materially lower; added to Findings.
- **Next:** Continue remaining pipeline tasks (recipe/module, simplified pipeline audit, end‑to‑end run).

### 20251220-1540 — Added non‑modification rule for modules
- **Result:** Success; added explicit rule to never modify existing modules.
- **Notes:** Story now requires new modules/recipes only.
- **Next:** Design new HTML‑first pipeline and module boundaries.

### 20251220-1552 — Moved pipeline design to new story
- **Result:** Success; created Story 081 for GPT‑5.1 pipeline design and linked it here.
- **Notes:** Keeps benchmarking scope clean in Story 077.
- **Next:** Continue pipeline design in Story 081.

### 20251220-1555 — Marked remaining items as moved; closed story
- **Result:** Success; remaining Success Criteria and Tasks marked as moved to Story 081.
- **Notes:** Story 077 is now complete; pipeline design continues in Story 081.
- **Next:** Proceed with Story 081 implementation.
