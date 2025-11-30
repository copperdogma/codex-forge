Fighting Fantasy / CYOA Sectionization Strategy

(Build spec for the implementation AI)

0. Purpose and Constraints

We are building a high-quality sectionizer for CYOA / Fighting Fantasy gamebooks using Unstructured as the intake layer.

Key facts:
	•	Input: scanned PDFs of gamebooks.
	•	Unstructured provides a verbose element IR (elements_full.jsonl).
	•	We must detect:
	•	Macro sections (cover, front matter, rules, intro, etc.).
	•	Game sections (numbered story sections, usually 1–400).

Prime directive:
Misidentifying a section is the worst failure.
If in doubt, omit or mark uncertain rather than guessing. All downstream logic assumes section boundaries are correct.

We will:
	•	Use Unstructured only for initial extraction.
	•	Immediately reduce to a minimal internal IR for all AI work.
	•	Use AI for all “messy” decisions (section headers, structure, verification).
	•	Use simple deterministic code only for:
	•	File/artifact management,
	•	Slicing by seq ranges,
	•	Sanity checks.

We want this design to be generic, with a CYOA “profile” as a specific configuration.

⸻

1. Artifacts Overview

The pipeline will produce and consume these main artifacts:
	•	elements_full.jsonl
Raw Unstructured output (input to pipeline, never mutated).
	•	elements_core.jsonl
Reduced internal IR derived from elements_full.
	•	header_candidates.jsonl
Per-element header classification results (macro + game-section candidates).
	•	sections_structured.json
Global structured view of the document:
	•	Macro sections (front matter vs game sections).
	•	Game section start positions and metadata.
	•	section_boundaries.jsonl
Final per-section boundaries, ready for downstream extraction.

The rest of the codex-forge pipeline (extract → build → validate) will read section_boundaries.jsonl.

⸻

2. Stage 0 – IR Reduction

Goal: normalize Unstructured’s verbose IR into a small, stable schema for all AI operations.

Input
	•	elements_full.jsonl — a sequence of Unstructured elements in reading order.
	•	Each element has an id, text, metadata (page, bbox, etc.).

Output
	•	elements_core.jsonl — one JSON object per line:

{
  "id": "unstruct-abc123",
  "seq": 217,                  // integer: global reading-order index (0-based)
  "page": 15,                  // integer: page number as reported by Unstructured
  "kind": "text",              // "text" | "image" | "table" | "other"
  "text": "raw text or ''",    // original text, unchanged except whitespace normalization
  "layout": {
    "h_align": "center",       // "left" | "center" | "right" | "unknown"
    "y": 0.42                  // optional, normalized vertical position 0–1 on page
  }
}



Implementation notes
	1.	Determine seq from the inherent order in elements_full.jsonl.
	2.	Determine kind:
	•	Map Unstructured element types to "text", "image", "table", "other".
	3.	Determine h_align and y using available layout metadata if present; otherwise "unknown" and null/omit.
	4.	Do not alter text beyond:
	•	Normalizing line breaks (\n → \n or spaces),
	•	Trimming leading/trailing whitespace.

After this stage, all subsequent AI work should depend only on elements_core.jsonl plus any derived artifacts.

⸻

3. Stage 1 – Header Classification (Local, AI-Driven)

Goal: identify candidate section headers (macro + game sections) at the element level. This stage does not decide the final 1..N mapping; it only labels candidates.

We will do this via batched AI calls over segments of elements_core.

Input
	•	elements_core.jsonl

Additionally, for CYOA we provide a doc profile (static configuration):

{
  "doc_type": "cyoa_gamebook",
  "expected_macro_sections": [
    "cover",
    "title_page",
    "publishing_info",
    "toc",
    "character_sheet",
    "rules",
    "introduction",
    "game_sections"
  ],
  "game_section_hint": {
    "numeric_range": [1, 400],
    "typical_layout": [
      "centered number alone on a line, followed by text",
      "image, then centered number alone on a line, followed by text"
    ]
  }
}

Model task per batch

We will process elements_core in batches of e.g. 50–100 sequential elements.

For each batch, the model receives:
	•	A JSON array of elements:

[
  {
    "seq": 210,
    "page": 15,
    "kind": "text",
    "text": "YOU ARE ABOUT TO EMBARK...",
    "layout": { "h_align": "center", "y": 0.18 }
  },
  ...
]


	•	The CYOA profile (doc_type and hints).
	•	Clear instructions:
	•	For each element, decide:
	•	Is it a macro section header (cover/title/toc/rules/intro/etc.)?
	•	Is it a game section header?
	•	If game section header: what section number does it claim (as printed)?
	•	It is better to say “no header / unknown” than to incorrectly mark a header.
	•	Output only JSON, no prose.

Expected model output for one batch:

{
  "elements": [
    {
      "seq": 210,
      "macro_header": "introduction",         // or "none"
      "game_section_header": false,
      "claimed_section_number": null,
      "confidence": 0.96
    },
    {
      "seq": 217,
      "macro_header": "none",
      "game_section_header": true,
      "claimed_section_number": 1,
      "confidence": 0.98
    },
    ...
  ]
}

Redundancy and aggregation

To increase robustness:
	•	Optionally run:
	•	A forward pass (elements 0 → end),
	•	A backward pass (elements end → 0),
	•	And/or multiple low-cost calls with different sampling seeds.
	•	Aggregate results per seq by:
	•	Majority vote for categorical labels,
	•	Average/max for confidence.

Output artifact

Write header_candidates.jsonl:

Each line:

{
  "seq": 217,
  "page": 15,
  "macro_header": "none",                // or "cover" | "rules" | "introduction" | ...
  "game_section_header": true,
  "claimed_section_number": 1,           // integer or null
  "confidence": 0.98
}

We include all elements, not just positives, so downstream logic has full context.

⸻

4. Stage 2 – Global Structuring (AI with Constraints)

Goal: from header_candidates, construct a coherent global structure:
	•	Macro sections with start/end seq ranges.
	•	Game sections with:
	•	Section numbers (1..N),
	•	Start seq (and implicitly end seq).

This is a single AI call on a compact summary of candidates, using strong constraints.

Input
	•	header_candidates.jsonl (all elements, but we only need a summary).
	•	CYOA profile:
	•	doc_type: "cyoa_gamebook"
	•	Target numeric range (e.g. 1–400).
	•	A derived summary you prepare in code:

{
  "doc_type": "cyoa_gamebook",
  "target_section_range": [1, 400],
  "elements": [
    {
      "seq": 0,
      "page": 1,
      "macro_header": "cover",
      "game_section_header": false,
      "claimed_section_number": null,
      "confidence": 0.95
    },
    {
      "seq": 87,
      "page": 6,
      "macro_header": "none",
      "game_section_header": true,
      "claimed_section_number": 1,
      "confidence": 0.98
    },
    ...
  ]
}



You can filter to just elements with any nontrivial header signal (macro_header ≠ “none” or game_section_header == true) to keep the payload smaller, plus a few context points if needed.

Model instructions (high level)

The model should:
	1.	Identify macro sections:
	•	Group ranges into things like:
	•	cover/title/publishing/toc/character_sheet/rules/introduction.
	•	At minimum, distinguish:
	•	"front_matter": everything before the first game section.
	•	"game_sections_region": from the first game section header to the last.
	2.	Identify game sections:
	•	Decide which candidates are real game section headers.
	•	For each real game section header, assign:
	•	section_number (1..N),
	•	start_seq.
	•	Ensure:
	•	Section numbers are in strictly increasing numeric order as seq increases.
	•	start_seq is strictly increasing with section number.
	•	If uncertain about a section:
	•	It may mark it as status: "uncertain" with start_seq: null, instead of guessing.
	3.	Behave conservatively:
	•	It is better to:
	•	Leave a section out,
	•	Or mark it uncertain,
	•	Than to assign a wrong start.

Expected output schema:

{
  "macro_sections": [
    {
      "id": "front_matter",
      "start_seq": 0,
      "end_seq": 86,
      "confidence": 0.9
    },
    {
      "id": "game_sections",
      "start_seq": 87,
      "end_seq": 1200,
      "confidence": 0.95
    }
  ],
  "game_sections": [
    {
      "id": 1,
      "start_seq": 87,
      "status": "certain",           // "certain" | "uncertain"
      "confidence": 0.98
    },
    {
      "id": 2,
      "start_seq": 113,
      "status": "certain",
      "confidence": 0.97
    },
    {
      "id": 47,
      "start_seq": null,
      "status": "uncertain",
      "confidence": 0.4
    }
  ]
}

Post-processing in code

Once you have sections_structured.json:
	1.	Validate:
	•	For all game_sections with status == "certain":
	•	start_seq strictly increasing with id.
	•	All start_seq in [0, max_seq].
	2.	Compute end_seq deterministically:
	•	For each section with status == "certain":
	•	end_seq = next.start_seq - 1 (where next is the next certain section in numeric order).
	•	For the last section:
	•	end_seq = macro_sections["game_sections"].end_seq or max_seq.

Sections marked "uncertain" may be left out of section_boundaries.jsonl or handled specially (e.g., logged for review).

⸻

5. Stage 3 – Section Boundaries Assembly

Goal: produce a simple, final boundary file for downstream extraction.

Input
	•	elements_core.jsonl
	•	sections_structured.json

Output
	•	section_boundaries.jsonl, one line per certain game section:

{
  "section_id": "1",
  "start_seq": 87,
  "end_seq": 94,
  "start_element_id": "unstruct-xyz123",
  "end_element_id": "unstruct-xyz129",
  "confidence": 0.98
}



Implementation steps
	1.	Load elements_core into memory keyed by seq.
	2.	For each certain section in game_sections:
	•	Find start_seq / end_seq.
	•	Resolve start_element_id / end_element_id from elements_core.
	3.	Emit one JSON line per section.

This stage is deterministic and non-AI.

⸻

6. Stage 4 – Verification Pass (AI “Paranoia”)

Goal: double-check that game section boundaries are correct, and adjust or flag any suspicious ones. This stage can use more calls and/or stronger models if needed.

We run two kinds of checks:

4.1. Zoom-in boundary check (per section)

For each certain section:
	1.	Prepare a small context window around its start:
	•	e.g. elements with seq in [start_seq - 3, start_seq + 3], clamped to valid range.
	2.	Send to an AI model with:
	•	The section number k,
	•	Instructions:
	•	“Within this window, which element seq is the most appropriate start for section <k>? If none is clearly correct, return unknown.”
	3.	Compare the model’s suggested seq with the existing start_seq:
	•	If they match (or are within some tolerance), keep as is.
	•	If they differ and model’s confidence is high, optionally adjust start_seq and recompute end_seq.
	•	If they differ and model’s confidence is low, mark the section for further review.

4.2. Zoom-out consistency sampling

Optionally, for sampled or all sections:
	1.	Provide:
	•	The last few lines of section k-1,
	•	The supposed heading and first lines of section k.
	2.	Ask:
	•	“Do these look like two distinct sections with different section numbers, or does it appear we mis-split/merged them?”
	3.	If suspicious:
	•	Mark as “needs review” or re-check with a stronger model.

Output / integration
	•	This stage may produce:
	•	A revised sections_structured.json (corrected start_seq),
	•	Or a section_verification_report.json with:
	•	Confirmations,
	•	Corrections,
	•	Flags.

The important part: this stage is allowed to be slow and overcautious, but should still be fully automated.

⸻

7. Generic vs CYOA-specific Behavior

The pipeline is generic; CYOA is just a profile:
	•	The generic sectionizer consists of:
	•	Stage 0 (IR reduce),
	•	Stage 1 (header classification),
	•	Stage 2 (global structuring),
	•	Stage 4 (verification).
	•	The CYOA profile provides:
	•	Macro section expectations (cover/title/toc/rules/etc.),
	•	Numeric game section patterns (1–400, centered numbers, image+number patterns),
	•	Domain hints for prompts.

For other document types (genealogy, novel, etc.), we can swap in different hints and label sets but reuse the same mechanics.

⸻

8. Design Principles (for the implementation)
	•	AI does all “messy” work:
	•	No regex-based sectioning logic beyond trivial pre- or post-processing if desired.
	•	No complex consensus/dedupe graphs.
	•	Code is simple and deterministic:
	•	Artifact plumbing,
	•	IR reduction,
	•	Range slicing,
	•	Sanity checks and validations.
	•	Conservatism over cleverness:
	•	When in doubt, the models mark headers or sections as “uncertain” or “none”.
	•	Global structuring prefers to omit a section rather than misassign it.
	•	Artifacts are explicit and debuggable:
	•	You can inspect elements_core, header_candidates, sections_structured, and section_boundaries independently to find where errors enter.
	•	Multi-call strategies are encouraged:
	•	Forward/backward passes,
	•	Multiple cheap models,
	•	Escalation to stronger models for low-confidence or flagged cases.

This is the strategy the implementation AI should follow when building the sectionization part of the pipeline in codex-forge.