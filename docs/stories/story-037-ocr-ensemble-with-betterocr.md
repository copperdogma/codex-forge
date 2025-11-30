# Story: Fighting Fantasy OCR Ensemble with BetterOCR

Status: Open
Created: 2025-11-30
Parent Story: story-031 (pipeline redesign - COMPLETE)

⸻

Goal

Integrate a multi-engine OCR ensemble (via BetterOCR) into the Fighting Fantasy pipeline to dramatically improve raw text quality before sectionizing. Use multiple local OCR engines plus an LLM reconciliation step to:
	•	Reduce OCR-induced missing/garbled sections,
	•	Provide a robust “Page → ordered list of lines” IR,
	•	Flag low-confidence pages for escalation to OpenAI Vision.

This is a focused upgrade to the OCR intake stage that feeds the already-redesigned pipeline from story-031.

Current OCR Situation (implicit from story-031 baseline):
	•	Single-engine OCR occasionally:
	•	Drops headers/section numbers,
	•	Produces garbled lines (e.g., section 277),
	•	Introduces page-number / header noise into section text.
	•	Downstream effects:
	•	24 missing sections,
	•	157 sections with no text,
	•	Garbled text requiring manual inspection.

Target: Establish a reliable, ensemble-based OCR layer that produces clean PageLines IR with line-level consensus and automated escalation of bad pages, reducing OCR-related failures in section detection and extraction.

⸻

Success Criteria
	•	BetterOCR successfully installed and callable on Mac M4 (Apple Silicon) by the pipeline.
	•	Multi-engine OCR in place (at minimum: Tesseract + EasyOCR via BetterOCR; Apple Vision optionally wrapped as a separate path).
	•	New OCR intake produces:
	•	A PageLines IR: page -> ordered list of text lines, for all pages.
	•	A per-page disagreement / quality score.
	•	Pipeline re-run on a target gamebook shows:
	•	Fewer obviously garbled sections (e.g., reduce “repair candidates” by ≥50% vs previous run).
	•	Fewer OCR-induced missing headers (e.g., section numbers actually present in page text).
	•	Pages with low consensus automatically:
	•	Flagged for review and/or
	•	Re-OCRed with OpenAI Vision using a strict transcription prompt.
	•	All improvements verified by:
	•	Manual inspection of a sample of pages (raw OCR vs ensemble result),
	•	Comparison of downstream metrics (missing/empty/garbled sections) vs story-031 baseline.

(Note: the section/choice targets from story-031 remain the higher-level goals; this story specifically addresses the OCR layer feeding those metrics.)

⸻

Tasks

Priority 1: Integrate BetterOCR as OCR Orchestrator
	•	Install BetterOCR and dependencies:
	•	Install Tesseract via Homebrew (if not already): brew install tesseract.
	•	Install Python dependencies:
	•	pip install betterocr easyocr
	•	Ensure torch / EasyOCR dependencies are available (CPU is fine; MPS GPU optional).
	•	Verify BetterOCR can import and run a minimal example on a single PNG.
	•	Configure BetterOCR engines for this pipeline:
	•	Enable at least:
	•	Tesseract (for classic OCR and TSV-like behavior),
	•	EasyOCR (for a second neural OCR perspective).
	•	Confirm BetterOCR is using both engines per page (no silent fallback to just one).
	•	Define OCR input/output contract:
	•	Input: single page image (PNG/JPEG) at 300 DPI.
	•	Output: raw per-page text (BetterOCR’s unified transcription) plus, if available:
	•	Per-engine raw outputs (for analysis),
	•	Any confidence/metadata BetterOCR exposes.
	•	Document this in docs/pipeline/ocr_ensemble.md.
	•	Wrap BetterOCR in a pipeline-friendly module:
	•	Create ocr_ensemble/ module exposing a function like:
	•	run_betterocr_on_page(image_path) -> { "text": "...", "by_engine": {...} }.
	•	Ensure it can be called by an AI agent via CLI or Python:
	•	CLI wrapper script: python -m ocr_ensemble.run --page path/to/page.png --out path/to/page.json.

⸻

Priority 1b: Build PageLines IR from BetterOCR
	•	PageLines IR definition:
	•	Define a canonical IR struct:

{
  "page": <int>,
  "lines": [
    { "text": "<line text>", "source": "betterocr", "meta": { "engines": {...} } },
    ...
  ]
}


	•	Keep it simple: focus on text and order; allow optional meta for confidence/engine details.

	•	Line segmentation:
	•	Decide how to split BetterOCR’s unified text into lines:
	•	Prefer newline-based splitting from the OCR output.
	•	If BetterOCR doesn’t preserve line breaks reliably, add a fallback using heuristics (e.g., original engines’ per-line outputs or length thresholds).
	•	Ensure blank lines (paragraph breaks) are preserved.
	•	Per-engine line alignment (optional, but recommended):
	•	Capture per-engine page text separately:
	•	tess_lines, easyocr_lines.
	•	Implement a basic line alignment strategy:
	•	Sort by reading order,
	•	Use text similarity to match lines across engines.
	•	Store aligned per-line engine variants in meta for later consensus/disagreement analysis.
	•	Persist PageLines IR:
	•	Write per-page IR to output/ocr_ensemble/<run_id>/pages/page-XXX.json.
	•	Produce an index file: pagelines_index.json with page → file mapping.

⸻

Priority 2: Disagreement Scoring & Flagging
	•	Define a disagreement / quality metric:
	•	For each page, compute:
	•	Per-line edit distance between engines,
	•	Fraction of tokens where engines disagree,
	•	Simple “gibberish” heuristics: non-alpha ratio, dictionary-word ratio, etc.
	•	Aggregate into a disagreement_score per page (0–1).
	•	Thresholds and categories:
	•	Define thresholds:
	•	0–0.05: high-confidence page,
	•	0.05–0.15: medium (OK but watch),
	•	>0.15: low-confidence (candidate for re-OCR).
	•	Store disagreement_score in the PageLines IR.
	•	Flag outputs for downstream:
	•	Annotate flagged pages with {"needs_escalation": true}.
	•	Add a summary file: ocr_quality_report.json listing pages ranked by disagreement.

⸻

Priority 2b: LLM-Based Line/Token Adjudication (Text-Only)
	•	Design LLM reconciliation prompt:
	•	Create a concise, domain-tuned prompt for a text model (no vision):
	•	Input: 2–3 candidate lines from different engines.
	•	Task: choose the best candidate or minimally corrected version.
	•	Constraints: “do not invent new sentences; only fix obvious OCR errors.”
	•	Store prompt template in prompts/ocr_line_reconcile.md.
	•	Implement line-level reconciliation:
	•	For lines with moderate disagreement, call text-LLM to:
	•	Pick between engine outputs or correct them.
	•	Replace the BetterOCR line text with reconciled text in PageLines IR.
	•	Track which lines were LLM-touched (for debugging).
	•	Performance safeguards:
	•	Limit LLM reconciliation to:
	•	Only lines above a per-line disagreement threshold,
	•	And only for pages below the “escalate to GPT-4 Vision” threshold (so we don’t double-spend).

⸻

Priority 3: GPT-4 Vision Escalation for Bad Pages
	•	Strict transcription prompt for GPT-4 Vision:
	•	Draft a prompt that:
	•	Demands exact transcription,
	•	Preserves line breaks,
	•	Includes headers/footers/page numbers if visible.
	•	Store in prompts/ocr_page_gpt4v.md.
	•	Escalation logic:
	•	For pages with disagreement_score > threshold:
	•	Call GPT-4V with the page image.
	•	Replace entire PageLines IR for that page with GPT-4V output.
	•	Mark these pages as {"source": "gpt4v"} in IR.
	•	Cost-control guardrails:
	•	Hard cap per run: max N pages escalated (configurable).
	•	Log escalations with cost estimate per run.
	•	Validation on sample problematic pages:
	•	Test GPT-4V escalation on known-bad pages (e.g., garbled ones from previous runs).
	•	Verify that:
	•	Section numbers are intact,
	•	Text is readable and faithful,
	•	Line breaks are preserved.

⸻

Priority 4: Integrate OCR Ensemble into Full Pipeline & Measure Impact
	•	Swap OCR stage in pipeline:
	•	Replace legacy OCR input with PageLines IR from BetterOCR pipeline.
	•	Ensure sectionizing stages (Stages 1–6) now consume PageLines IR instead of old text source.
	•	Re-run on reference gamebook:
	•	Pick the same book used for story-031 baseline.
	•	Run full pipeline with OCR ensemble.
	•	Capture metrics:
	•	Missing sections,
	•	Empty sections,
	•	Sections flagged for typo/garble repair,
	•	Choices detection stats.
	•	Compare against story-031 baseline:
	•	Check:
	•	Are missing sections reduced (because headers weren’t dropped by OCR)?
	•	Are empty sections reduced (less garbled/empty input)?
	•	Are garbled sections like 277 improved even before repair passes?
	•	Document improvements (or regressions) with concrete examples.
	•	Feedback into higher-level stories:
	•	If OCR improvements significantly reduce missing/empty sections:
	•	Update story-031 / “Pipeline Optimization” notes to reflect OCR’s contribution.
	•	Adjust future optimization stories to focus more on section logic vs OCR.

⸻

Artifacts for Reference

New OCR Ensemble Artifacts (proposed):
	•	output/runs/<run_id>/ocr_ensemble/pages/page-XXX.json
	•	PageLines IR for each page.
	•	output/runs/<run_id>/ocr_ensemble/pagelines_index.json
	•	Index of page → IR file path.
	•	output/runs/<run_id>/ocr_ensemble/ocr_quality_report.json
	•	Per-page disagreement scores, escalation flags, engine stats.
	•	docs/pipeline/ocr_ensemble.md
	•	Design doc for BetterOCR integration, PageLines IR schema, escalation rules.
	•	prompts/ocr_line_reconcile.md
	•	Text-only LLM line reconciliation prompt.
	•	prompts/ocr_page_gpt4v.md
	•	GPT-4 Vision page transcription prompt.

Existing Baseline Artifacts (for downstream comparison):
	•	output/runs/ff-redesign-v2-improved/gamebook.json
	•	output/runs/ff-redesign-v2-improved/validation_report.json
	•	output/runs/ff-redesign-v2-improved/sections_structured.json
	•	output/runs/ff-redesign-v2-improved/portions_enriched.jsonl

(Used to measure impact of new OCR on missing/empty/garbled sections.)

⸻

Notes
	•	BetterOCR is the orchestrator, not the whole story:
	•	We still want PageLines IR, disagreement metrics, and GPT-4V escalation logic on top.
	•	Keep prompts simple and constrained:
	•	For line reconciliation and GPT-4V, emphasize exact transcription and no invention.
	•	Evidence-driven:
	•	Always compare OCR outputs line-by-line on a few pages before assuming improvement.
	•	Log example lines where engines disagree and how LLM resolves them.
	•	Cost-awareness:
	•	GPT-4 Vision is reserved for bad pages, not the whole book.

⸻

Work Log
	•	(empty – to be filled as work progresses)