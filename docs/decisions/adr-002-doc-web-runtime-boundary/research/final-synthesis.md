---
type: synthesis-report
topic: "`doc-web` runtime boundary, output contract, and Dossier handoff model"
synthesis-model: "codex-gpt-5"
source-reports:
  - "xai-research-stub.md"
  - "opus-research-stub.md"
  - "openai-research-report.md"
  - "gemini-research-report.md"
synthesized: "2026-03-18"
---

# Final Synthesis

## Decision Summary

Cross-report convergence is strong enough to recommend the core direction now:

- `doc-web` should be a standalone runtime repo, not a long-lived `codex-forge` dependency.
- Its contract should be a structural website bundle, not loose HTML fragments and not a polished presentation layer.
- Minimal navigation is part of the structural contract.
- Provenance must move beyond the current chapter-level manifest to block-level citation support.
- Dossier should consume versioned `doc-web` releases with explicit contract tests.
- Migration should be strangler-style, starting with the narrowest proven seam rather than a big-bang fork or repo import.

## Source Quality Assessment

### Highest-confidence reports

- **Opus**: strongest overall research quality. It brought the best boundary thinking, the clearest provenance tradeoff analysis, and the strongest external precedent set. It is the most useful report for deciding where to draw the architectural line.
- **xAI**: strongest practical implementation guidance. It was less deeply sourced than Opus but very good on migration sequencing, package discipline, and the dangers of leaving codex-forge as the runtime dependency.

### Medium-confidence reports

- **OpenAI**: directionally aligned with the stronger reports, but the evidence was thinner and more repetitive. Useful as a convergence check, not as the main deciding source.
- **Gemini**: also directionally aligned and crisp on bundle shape and provenance sidecars, but less rigorous than Opus on the ownership and packaging tradeoffs.

## Agreements

All four reports agree on these points:

1. **Ownership boundary**: `doc-web` should be extracted as its own runtime rather than living permanently inside `codex-forge`.
2. **Avoided path**: using `codex-forge` or a lightly stripped fork as the production dependency is the weakest option.
3. **Output shape**: the runtime should emit a structural website bundle with semantic HTML, machine-readable structure, and asset organization.
4. **Navigation**: TOC and prev/next links are structural, not merely presentational.
5. **Provenance direction**: chapter-level provenance is too coarse for the downstream citation requirement; a block-level mapping is needed.
6. **Migration strategy**: do not do a big-bang fork or rewrite. Extract the smallest coherent seam first.

## Disagreements and Resolution

### 1. Standalone repo vs direct Dossier ownership

- **Disagreement**: minimal. All reports choose standalone `doc-web` as the default. Direct Dossier ownership appears only as a runner-up for a very small team or a permanently single-consumer component.
- **Resolution**: choose the standalone repo. Your stated goals already imply a second boundary: codex-forge research vs Dossier consumption. You also want parallel work without stepping on unrelated product concerns. That is exactly the situation where a standalone runtime is justified.

### 2. Provenance granularity

- **Disagreement**: xAI/OpenAI/Gemini recommend "block-level" as the default. Opus is more precise and argues for **paragraph-level as the default block unit**, with sentence-level provenance only when needed.
- **Resolution**: treat this as compatible rather than contradictory. The right first contract is:
  - **block-level provenance**
  - with **paragraph as the default block type**
  - sentence-level provenance deferred until a concrete consumer needs it

This satisfies the citation requirement without overbuilding source maps on day one.

### 3. Packaging and release model

- **Disagreement**:
  - Opus prefers a private/internal package registry plus contract tests.
  - xAI prefers tagged releases with SemVer, optionally backed by internal PyPI.
  - OpenAI/Gemini prefer tagged releases consumed via package manager or git pinning.
- **Resolution**: start with **tagged git releases + SemVer + explicit Dossier pins + contract tests**.

Reason:

- current scale does not justify package-registry ceremony yet;
- the real safety mechanism is not the registry, it is explicit version pins plus consumer-driven contract tests;
- if `doc-web` later gains multiple consumers or release frequency becomes awkward, move to a private package registry without changing the contract model.

So the practical rollout is:

- start with tagged releases
- require changelog + SemVer
- pin exact versions in Dossier
- add golden fixture contract tests immediately
- only add private package infrastructure when scale actually demands it

### 4. First extraction slice

- **Disagreement**:
  - xAI leans toward migrating `build_chapter_html_v1` core first.
  - Gemini recommends generic models plus the emitter.
  - Opus recommends one complete seam plus an anti-corruption layer if needed.
- **Resolution**: first extraction slice should be:
  - the **bundle contract** itself
  - generic manifest/provenance models
  - a refactored HTML emitter split out of `build_chapter_html_v1`

That is better than moving the current module wholesale, because the current builder still mixes:

- structural website output
- embedded CSS
- some output-shaping choices

The seam should therefore be "generic document bundle emission" rather than "copy the current builder unchanged."

## Recommended Architecture

### 1. Runtime boundary

`doc-web` should become the standalone runtime for **mature document-to-structural-website conversion**.

That means:

- input can eventually expand to PDFs, images, and other documents
- output is a structural, navigable, provenance-rich website bundle
- polished visual presentation remains outside this runtime

`codex-forge` remains the research/archive context, not the runtime dependency.

### 2. Output contract

The minimum first-class `doc-web` bundle should be:

- `index.html`
- `chapters/` or equivalent content HTML files
- `assets/` for extracted images and other static resources
- `manifest.json` for reading order, titles, identifiers, and bundle metadata
- `provenance.json` or `provenance/*.jsonl` for block-level source mapping

The HTML contract should use:

- semantic HTML5 elements
- stable block IDs
- minimal structural hooks only
- no framework-specific UI output
- no polished theming requirements

Minimal navigation belongs in the contract:

- TOC
- prev/next links
- stable reading order

### 3. Provenance contract

Recommended first contract:

- **paragraph-level blocks as the default citation unit**
- stable HTML IDs for each block
- sidecar mapping from HTML block ID to:
  - source artifact ID/path
  - source page
  - bounding box or equivalent location reference when available
  - source element ID when available
  - extraction metadata such as confidence/method when available

Heavier provenance should live in the sidecar, not be stuffed into every HTML node.

Minimal inline HTML provenance is still useful:

- `id`
- optional lightweight `data-prov-id`
- optionally `data-source-page` if it materially helps debugging

But the citation-grade mapping should live in a machine-readable sidecar.

### 4. Dossier integration model

Dossier should consume `doc-web` through:

- tagged releases
- SemVer
- explicit version pins
- golden fixture / contract tests in Dossier CI

The contract tests should validate at least:

- bundle layout
- manifest schema
- provenance schema
- stability of key HTML hooks and block IDs on golden fixtures

### 5. Migration strategy

Use a strangler-style extraction:

1. Define the `doc-web` bundle and provenance schemas.
2. Split the generic HTML/bundle emitter out of `build_chapter_html_v1`.
3. Move that seam into `doc-web`.
4. Keep FF/gamebook logic, OCR research, story system, and evaluation overhead out of the new repo.
5. Let codex-forge call into `doc-web` temporarily if needed, until the old runtime role is fully retired.

## Recommended Next Decisions for the ADR

These are ready to move from "open question" to "leading recommendation" in the ADR:

- `doc-web` should be a standalone runtime repo.
- `codex-forge` should not become a production dependency.
- `doc-web` owns structural website output, not final presentation polish.
- provenance must be block-level, with paragraph as the default unit.
- Dossier should start with tagged release pins and contract tests, not floating dependencies.
- first extraction slice should be the bundle-emission seam, not the whole repo.

## Open Questions

These still need explicit follow-up stories rather than hand-wavy agreement:

1. **Exact schema design** for `manifest.json` and `provenance.json`.
2. **How much provenance to inline** in HTML vs. keep only in sidecars.
3. **Whether `doc-web` v0` also owns any mature OCR/portionization stages immediately**, or only the bundle-emission layer at first.
4. **Whether codex-forge is archived completely or kept as cold storage plus golden fixtures.**

## Bottom Line

The research does not support "pull codex-forge into Dossier" and it does not support "keep codex-forge as the runtime."

The strongest direction is:

- archive or reduce codex-forge to research/storage
- extract `doc-web` as the standalone runtime
- make its first-class artifact a structural website bundle with block-level provenance
- have Dossier consume tagged, tested releases
- migrate by the smallest clean seam first
