---
type: synthesis-prompt
topic: "doc-web-runtime-boundary"
created: "2026-03-19T05:30:30.761711+00:00"
auto-generated: true
---

# Synthesis Prompt

You are acting as lead research editor. Your task is to read multiple independent research reports on the same topic, reconcile them, and produce one final, implementation-ready synthesis.

## Research Context

## Context

`codex-forge` is an AI-first ingestion R&D repo for turning scanned books, PDFs, and images into provenance-rich semantic HTML and other structured artifacts for a downstream system called Dossier. The project's near-term priority shifted after the Onward pipeline became good enough that the semantic HTML output itself is now treated as the final ingestion-layer artifact.

The user has explicitly decided:

- codex-forge should stop at semantic HTML or a structural website bundle;
- a polished website builder does not belong inside codex-forge;
- a new runtime named `doc-web` should be defined for the reusable document-to-website conversion layer;
- Dossier will eventually consume `doc-web`;
- Dossier requires provenance back to the original uploaded artifact so downstream systems can cite a fact and open the original PDF or source at the relevant location.

Current local repo evidence:

- `README.md` now says codex-forge intentionally stops at semantic HTML and should graduate mature ingestion into Dossier.
- `modules/build/build_chapter_html_v1/main.py` already emits:
  - `index.html`
  - chapter/page HTML files
  - minimal prev/next/index nav
  - a chapter manifest with source page and source portion metadata
- The current output is therefore already website-shaped in a structural sense, not just a bag of HTML fragments.
- Provenance is present but still coarse. The current manifest tracks chapter/page-level provenance such as `source_pages`, `source_printed_pages`, and portion metadata, but it does not yet define a block-level citation contract suitable for exact fact citations.
- `docs/pipeline/ff-specificity-audit.md` shows that codex-forge contains substantial Fighting Fantasy and gamebook-specific logic that should not automatically move into a generic runtime.

The architectural question is which ownership and contract model is best:

1. extract `doc-web` as a standalone runtime repo and have Dossier consume tagged releases;
2. move the reusable runtime directly into Dossier and skip a standalone repo;
3. keep using codex-forge itself, or a lightly stripped fork, as the runtime dependency.

The research should optimize for:

- provenance fidelity
- clean product boundaries
- ease of long-term maintenance
- parallel work by multiple agents
- practical Dossier integration
- keeping codex-forge lean instead of turning it into a permanent runtime

## What I Need

### 1. Runtime Ownership Boundary

Compare these approaches:

- standalone `doc-web` repo consumed by Dossier
- direct Dossier ownership of the runtime
- codex-forge or codex-forge-derived repo as the long-lived dependency

Questions:

- Which ownership model best balances maintainability, contract clarity, and parallel iteration?
- In what situations is a standalone runtime repo clearly better than direct product ownership?
- What failure modes commonly appear when an R&D repo becomes a production dependency without a clean extraction step?

### 2. Output Contract for a Structural Website Runtime

Assume the runtime does **not** own final visual polish, but it **does** own structural website output.

Questions:

- What should the minimum `doc-web` bundle contain if the output must be both AI-usable and human-browsable?
- Should minimal TOC/prev-next navigation be considered part of the semantic contract?
- What is the best way to separate structural website output from later presentation-layer theming?
- What bundle layout is most robust? For example:
  - `index.html`
  - chapter/page HTML files
  - document manifest
  - image assets
  - provenance sidecars

### 3. Provenance and Citation Contract

The downstream need is precise citation back to the original artifact, such as opening a PDF to the relevant page/region when a fact is cited.

Questions:

- What provenance granularity is the right default for a document-to-HTML runtime?
- What identifiers should be stable in the HTML itself: DOM IDs, `data-*` attributes, block IDs, source element IDs, text span IDs?
- What sidecar format is most robust for mapping HTML blocks back to original artifact pages, coordinates, and source element IDs?
- What should be considered mandatory vs optional provenance fields for a first contract?

### 4. Packaging and Versioning Model for Dossier

Questions:

- What dependency model is the most practical for Dossier consuming `doc-web`: tagged git releases, vendoring, internal package publishing, or another approach?
- What contract tests or fixtures should exist between Dossier and `doc-web` to avoid drift?
- If Dossier only wants to "pull periodically," what release discipline prevents silent breaking changes?

### 5. Migration Strategy from codex-forge

Questions:

- Which classes of code should migrate as-is, which should be refactored first, and which should definitely stay behind?
- How should fixture or golden ownership be handled if codex-forge is archived or reduced to storage?
- What is the smallest viable first extraction slice that proves the boundary without moving the whole repo?

## Output Format

For each section, provide:
1. **Recommended choice** with reasoning
2. **Runner-up** and when to choose it instead
3. **Avoid** — options that look attractive but have meaningful downsides
4. **Evidence** — sources, benchmarks, adoption signals, or concrete examples

## Reports to Synthesize

You will receive 4 research reports, each produced by a different AI model. Each report covers the same research question from the instructions above.

## Your Synthesis Goals

1. Grade each source report on quality: evidence density, practical applicability, specificity, and internal consistency (0–5 scale for each, with a one-paragraph critique).
2. Extract key claims by topic area.
3. Identify where reports agree (high confidence) vs. disagree (needs adjudication).
4. Resolve contradictions with explicit reasoning — evaluate the strength of each report's evidence, not majority vote.
5. Separate "proven / high confidence" from "promising but uncertain."
6. Produce one concrete recommendation, not a menu of options.
7. If one report is clearly higher quality, weight it accordingly and say why.

## Required Output Format

Begin your response with:

---
canonical-model-name: "{the product name you are — e.g., chatgpt, claude, gemini, grok — lowercase, no version numbers}"
report-date: "{today's date in ISO 8601}"
research-topic: "doc-web-runtime-boundary"
report-type: "synthesis"
---

Then produce the following sections:

1. **Executive Summary** (8–12 bullets)
2. **Source Quality Review** (table with scores + short commentary per report)
3. **Consolidated Findings by Topic**
4. **Conflict Resolution Ledger** (claim, conflicting views, final adjudication, confidence level)
5. **Decision Matrix** (if applicable — weighted, with scoring rationale)
6. **Final Recommendation** (concrete, with rationale)
7. **Implementation Plan / Next Steps** (if applicable)
8. **Open Questions & Confidence Statement**

## Quality Instructions

- Be concrete and specific, not generic.
- Clearly label assumptions and uncertainty.
- Prefer practical reliability over novelty.
- If evidence is weak across all reports, say so — do not manufacture false confidence.
- Do not simply merge or average — adjudicate.
- Note which report(s) contributed each key finding.
- Score each source report on its merits regardless of which AI model produced it. Do not assume the most detailed report is the most accurate — weight verifiable citations over unverified claims.
