# ADR-002: `doc-web` Runtime Boundary, Output Contract, and Dossier Handoff Model

**Status:** ACCEPTED — standalone `doc-web` runtime, structural website contract, and seam-first extraction adopted

<!-- Status lifecycle: PENDING → RESEARCHING → DISCUSSING → ACCEPTED -->
<!-- Alternatives: REJECTED / DEFERRED / SUPERSEDED -->
<!-- Process: docs/runbooks/adr-creation.md -->

## Context

Codex-forge's near-term priority changed once the Onward HTML path became good enough to treat as the desired semantic output layer. The repo no longer needs to absorb a polished website builder. Instead, it needs a clear graduation path for the reusable document-to-HTML runtime that Dossier can eventually consume.

The open architectural question is not whether to keep working on ingestion. It is where that ingestion runtime should live and what exactly it should output.

Current local evidence:

- `README.md` now states that codex-forge intentionally stops at semantic HTML and that the shared Dossier stop-point should be "ingest to semantic HTML" before downstream semantic processing.
- `modules/build/build_chapter_html_v1/main.py` already emits more than loose HTML fragments. It writes a structural site bundle with:
  - `index.html`
  - chapter or fallback page HTML files
  - minimal prev/next/index navigation
  - a chapter manifest containing page ranges and source-page lists
- Dossier's actual product need is stronger than "return HTML." It must preserve provenance back to the original uploaded artifact so downstream systems such as Storybook can cite a fact and open the original source at the relevant page, paragraph, or region.
- The current HTML manifest is helpful but still coarse. It tracks chapter/page-level provenance fields such as `source_pages`, `source_printed_pages`, and source portion metadata, but it does not yet define a block-level citation contract. Also, no dedicated schema class for `chapter_html_manifest_v1` is currently defined in `schemas.py`.
- `docs/pipeline/ff-specificity-audit.md` shows that this repo still contains substantial Fighting Fantasy and gamebook-specific logic that Dossier should not inherit as part of a generic intake runtime.

That leaves three realistic directions:

1. keep using `codex-forge` itself as the runtime dependency;
2. move the reusable code directly into Dossier and let Dossier own it outright;
3. extract a new standalone runtime, named `doc-web`, that Dossier consumes via a versioned boundary while codex-forge is archived or reduced to research-only status.

This ADR exists to settle the hard-to-reverse part of that choice:

- what `doc-web` is;
- whether it should exist as a separate runtime repo;
- what its output contract must contain;
- how Dossier should consume it;
- and what must stay behind in codex-forge.

## Ideal Alignment

In the Ideal, Dossier could ingest any document directly and produce provenance-rich structured output without the user thinking about intermediate tooling. Codex-forge exists because that ideal is not yet operationally real for every document type.

This decision moves the project toward the Ideal if it:

- keeps traceability first instead of collapsing provenance while "simplifying" the runtime;
- treats semantic, navigable HTML as a Dossier-ready artifact rather than as a one-off website hack;
- graduates mature ingestion capability out of codex-forge instead of letting the R&D lab become a permanent product runtime;
- preserves a clean boundary between structural website output and later presentation polish.

The wrong move would be to optimize for short-term convenience by dragging the whole codex-forge repo into Dossier or by confusing visual website polish with the reusable ingestion contract.

## Options

### Option A: Extract `doc-web` as a standalone runtime repo and have Dossier consume versioned releases

Create a new repo focused on document or book to structural website conversion: semantic HTML pages, minimal machine-useful navigation, manifests, and provenance sidecars. Dossier depends on this runtime through an explicit versioned integration boundary.

Pros:

- keeps the reusable ingestion runtime focused and free of codex-forge story/docs/eval overhead;
- allows parallel work on ingestion without forcing every experiment directly into Dossier;
- makes the runtime usable and testable outside Dossier;
- preserves a clean graduation story: codex-forge researches, `doc-web` operationalizes, Dossier consumes;
- matches the user's preference for a component whose shape is dictated by downstream product needs but can still evolve independently.

Cons:

- adds repo and release-management overhead;
- introduces one more boundary to version and test;
- risks drift if `doc-web` and Dossier evolve without disciplined contract tests.

### Option B: Move the reusable ingestion runtime directly into Dossier

Port the reusable modules, schemas, and bundle contract straight into Dossier and retire codex-forge as soon as the move begins. Dossier becomes the only maintained home for the runtime.

Pros:

- one fewer repo to manage;
- makes Dossier the canonical owner immediately;
- removes packaging or release-boundary questions.

Cons:

- increases the chance that Dossier absorbs codex-forge baggage or ongoing ingestion churn;
- makes it harder to run multiple agents on a sharply bounded ingestion component without stepping into Dossier concerns;
- blurs the distinction between reusable intake runtime work and downstream semantic processing;
- makes the transition more brittle if the runtime contract is still incomplete, especially around provenance granularity.

### Option C: Keep `codex-forge` or a long-lived fork as the runtime dependency

Use codex-forge itself, or a lightly stripped fork, as the thing Dossier periodically pulls from.

Pros:

- lowest immediate migration effort;
- preserves current tests, fixtures, and run history with minimal change;
- avoids setting up a new repo right away.

Cons:

- bakes in FF/gamebook-specific baggage, story tooling, and research overhead Dossier does not want;
- weakens mission clarity for both repos;
- leaves the runtime boundary implicit instead of contract-first;
- creates ongoing confusion about whether codex-forge is archived, active R&D, or a production dependency.

## Research Needed

- [x] What is the best ownership model for the mature ingestion runtime: standalone `doc-web`, direct Dossier ownership, or codex-forge-as-dependency?
- [x] What is the minimum output contract for `doc-web` if the artifact must function as a structural website and also support Dossier or Storybook provenance and citation needs?
- [x] What provenance granularity is required beyond the current chapter-level manifest: block IDs, DOM anchors, source element IDs, bounding boxes, text spans, or PDF coordinate links?
- [x] What package or release model should Dossier use to consume `doc-web`: tagged git releases, vendoring, internal package distribution, or another pattern?
- [x] Which current codex-forge modules, schemas, fixtures, and docs should migrate as-is, refactor before migration, or remain behind permanently?

## Repo Constraints / Existing Context

- `docs/ideal.md` and `docs/spec.md` make "Dossier-ready output" and "Graduate to Dossier" first-class obligations, not optional cleanup.
- `README.md` now explicitly says codex-forge stops at semantic HTML and that presentation-layer website generation is outside repo scope.
- Story 130 was moved to `Won't Do` in codex-forge because the polished website builder no longer belongs here.
- Story 151 exists specifically to define `doc-web` as the standalone runtime, choose the boundary, and create the follow-up migration plan.
- `modules/build/build_chapter_html_v1` already emits `index.html`, chapter/page HTML files, basic navigation, and a manifest. That is evidence that the current runtime output is already website-shaped in a structural sense.
- `schemas.py` already preserves provenance-rich `UnstructuredElement` and `_codex` metadata, but the final HTML bundle contract is not yet formalized at block-level granularity.
- `configs/recipes/recipe-onward-images-html-mvp.yaml` shows the currently working narrow path from images to semantic HTML for the Onward book.
- `docs/pipeline/ff-specificity-audit.md` inventories where gamebook/FF logic lives and is the current best internal source for deciding what should not move into a generic runtime.
- ADR-001 is relevant as background for provenance-preserving, source-aware extraction strategy but does not settle runtime ownership or the Dossier handoff contract.

## Dependencies

- Story 151 — this ADR is the primary decision artifact required by that story.
- ADR-001 (`docs/decisions/adr-001-source-aware-consistency-strategy/adr.md`) — relevant prior architectural direction for source-aware extraction and inspectable planning artifacts.
- Likely affects: `README.md`, `docs/spec.md`, `docs/build-map.md`, Story 151, and any follow-up migration or Dossier-handoff stories.

## Research Summary

<!-- Fill after research. Distill findings; do not paste raw model output. -->
- Four-provider convergence is strong. xAI, Opus, OpenAI, and Gemini all recommend extracting `doc-web` as a standalone runtime rather than leaving codex-forge as the dependency. Direct Dossier ownership appears only as the runner-up for a very small, permanently single-consumer case.
- All reports agree that `doc-web` should output a structural website bundle, not loose HTML fragments and not a polished themed site. Minimal TOC and prev/next navigation are part of the structural contract.
- All reports also agree that the current chapter-level manifest is too coarse for Dossier's citation requirement. Provenance must move to block-level; the synthesis resolves the small granularity disagreement by choosing paragraph-level blocks as the default first citation unit.
- The main practical disagreement was packaging rigor. Opus prefers a private registry from the start, while xAI/OpenAI/Gemini are comfortable with tagged releases and version pins. Synthesis recommendation: start with tagged releases + SemVer + Dossier contract tests now; move to a private registry later only if multiple consumers or release volume justify it.
- Migration should be strangler-style. The first extraction slice should be the bundle-emission seam — manifest/provenance models plus a refactored HTML emitter split from `build_chapter_html_v1` — not a big-bang repo fork and not the whole OCR pipeline.

## Discussion

<!-- Chronological discussion notes, disagreements, corrections, and reasoning. -->
- 20260318-2300 — ADR created from Story 151 after the user settled the runtime name as `doc-web`. The immediate open question is not naming; it is repo boundary, output contract, and Dossier consumption model.
- 20260318-2300 — Current local evidence suggests that the reusable runtime already outputs a structural website, not merely loose semantic HTML fragments. The remaining uncertainty is whether that structural bundle should be extracted into its own repo or absorbed directly into Dossier.
- 20260318-2329 — OpenAI and Gemini automated runs completed and were normalized into the ADR's canonical report filenames. Combined with the pasted xAI and Opus reports, the four-provider research now converges on the same high-level direction: standalone `doc-web`, structural website contract, stronger provenance, and strangler-style extraction.
- 20260318-2329 — The only material disagreement after synthesis is packaging ceremony. Research quality favors Opus on theory and xAI on pragmatic rollout, so the synthesis resolves this in favor of a lighter first step: tagged SemVer releases plus contract tests now, private registry later if scale justifies it.

## Decisions

<!-- Final decisions with rationale. Use "Settled — DO NOT suggest alternatives" for key calls. -->
- Settled — DO NOT suggest alternatives: the runtime name is `doc-web`, unless later external packaging or legal checks reveal a blocking conflict.
- Settled — `doc-web` should be a standalone runtime repo, not a long-lived `codex-forge` dependency.
- Settled — `doc-web` owns structural website output: semantic HTML pages, reading order, minimal navigation, manifests, and provenance sidecars. Polished presentation remains outside its scope.
- Settled — provenance must be block-level, with paragraph-level blocks as the default first citation unit for the first contract.
- Settled — Dossier consumes `doc-web` through tagged SemVer releases with explicit version pins and contract tests. Private package-registry infrastructure can wait until scale justifies it.
- Settled — the first extraction slice is the bundle-emission seam and its schemas, not a big-bang repo move and not the whole OCR pipeline.

## Integration Checklist

- [x] **docs/spec.md / docs/ideal.md / docs/requirements.md** — `docs/spec.md` updated with the accepted `doc-web` handoff direction; no `ideal.md` or `requirements.md` change needed
- [x] **Related stories** — Story 151 updated; follow-up stories 152-154 created for contract, extraction, and Dossier handoff
- [x] **AGENTS.md** — reviewed; no workflow or guardrail change required from this ADR
- [x] **Runbooks / supporting docs** — existing ADR/deep-research runbooks remain valid; added `docs/notes/standalone-dossier-intake-runtime-plan.md` for the extraction inventory
- [x] **Other ADRs / decision docs** — build map now references ADR-002; ADR-001 remains background only
- [x] **Audit** — README, spec, build map, Story 151, follow-up stories, and ADR-local research artifacts now reflect the accepted direction

## Remaining Work

<!-- Future stories, follow-ups, or open questions that flow from this ADR. -->
- Run the research pass defined in `research/research-prompt.md`.
- Produce the migrate/refactor/leave-behind inventory for current codex-forge surfaces.
- Decide whether `doc-web` needs a new bundle schema, or whether it should formalize and extend the current HTML manifest/output shape.
- Create follow-up implementation stories for repo extraction, provenance-contract upgrades, and Dossier integration once the ADR reaches `DISCUSSING` or `ACCEPTED`.
- Story 152 — define the `doc-web` bundle and provenance contract
- Story 153 — extract the generic `doc-web` bundle emitter seam
- Story 154 — publish the Dossier `doc-web` semantic HTML handoff contract

## Work Log

<!-- YYYYMMDD-HHMM — event: outcome, evidence, next -->
- 20260318-2300 — ADR created: scoped the `doc-web` decision around runtime ownership, structural website contract, provenance granularity, and Dossier handoff. Evidence: `README.md` mission change, Story 151, `build_chapter_html_v1` structural site output, and the FF specificity audit. Next: fill the stand-alone research prompt and cross-link Story 151.
- 20260318-2308 — research scaffold prepared: filled `research/research-prompt.md`, wired `research/final-synthesis.md` to the expected provider report files, and created OpenAI, Gemini, Opus, and xAI stub report files so the ADR can move straight into a multi-provider research pass without more setup.
- 20260318-2329 — research and synthesis completed: pasted xAI and Opus manual reports, ran OpenAI and Gemini automated research, normalized the generated files into the repo's canonical report names, and synthesized the four reports into one recommendation. Result: strong convergence on standalone `doc-web`, structural website output, stronger provenance, and seam-first extraction; the main unresolved decision is only how much release infrastructure to adopt on day one.
- 20260318-2337 — ADR accepted: user approved the synthesized direction. Propagated the accepted `doc-web` handoff model into `README.md`, `docs/spec.md`, `docs/build-map.md`, the new extraction-plan note, and the follow-up story set. The remaining work is now implementation, not architecture.
