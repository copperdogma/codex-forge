# ADR-001: Document-Wide Consistency Planning and Source-Aware Re-Extraction Strategy

**Status:** ACCEPTED — Document-wide consistency planning and plan-aware selective reruns adopted

<!-- Status lifecycle: PENDING → RESEARCHING → DISCUSSING → ACCEPTED -->
<!-- Alternatives: REJECTED / DEFERRED / SUPERSEDED -->
<!-- Process: docs/runbooks/adr-creation.md -->

## Context

Codex-forge relies on AI-first extraction from source documents, often at page scope. That compromise gets strong raw extraction quality, but it also creates representation drift: the same underlying source pattern can emerge as different HTML structures across adjacent pages or chapters.

Story 141 surfaced the issue sharply in the Onward genealogy converter. In one reviewed run, the same genealogy structure appears as:
- a canonical table with split `BOY` / `GIRL` columns;
- near-identical tables that still use a combined `BOY/GIRL` header;
- family/context headings embedded inside table headers on one page but emitted as external headings on the next;
- repeated headerless mini-tables that are clearly fragments of the same conceptual structure.

At first glance this looks like an HTML normalization problem. That framing is too narrow. The real question is where canonicalization should happen:
- during extraction from source, with broader context;
- after extraction, by aligning and rerunning flagged structures from source;
- or after extraction, by rewriting HTML into a canonical shape.

Local repo evidence already points toward a strong constraint: when extraction quality is poor or inconsistent, the strongest available source-aware model usually beats post-extraction cleanup. That suggests the default response to inconsistency should probably be "go back to source with better context," not "repair mediocre HTML."

This ADR therefore settles the architectural strategy for consistency:
- should codex-forge treat inconsistency as a trigger for selective, context-aware re-extraction from source;
- should some recipes move to broader run-aware extraction from the start;
- what role should deterministic/statistical analysis play in detection, clustering, acceptance, and provenance;
- when is HTML-only normalization still justified as a secondary or fallback tool;
- and whether consistency decisions should be emitted as explicit per-document artifacts instead of being buried inside prompts or ad hoc code.

Chapter-level drift detection was a useful first seam because it matched the existing pipeline and was cheap to validate. It should not be mistaken for the long-term architecture. True consistency has to be decided at document scope. A single document may contain multiple legitimate pattern families, each with its own sensible representation. The consistency engine therefore needs to discover those families across the whole artifact, choose document-local conventions for each, and emit those choices explicitly so later repair passes and human reviewers can inspect them.

This ADR now centers on three document-local artifacts:
- `pattern_inventory` — what repeated structured pattern families exist in this document, where they appear, and how confident the engine is;
- `consistency_plan` — what conventions the engine chose for each detected family, including how to represent context rows, subgroup rows, marginal notes, summaries, and other repeated structure choices;
- `conformance_report` — which pages, runs, chapters, or document regions violate that chosen plan after repair or rebuild.

## Ideal Alignment

In the Ideal, extraction itself would emit faithful, provenance-rich, globally consistent structure, and no downstream repair layer would be needed. The same source pattern would naturally produce the same representation everywhere.

Today we are not there. A source-aware consistency strategy moves us toward the Ideal if it:
- prefers better source-grounded extraction over downstream guesswork;
- preserves original artifacts and provenance rather than silently replacing them;
- makes consistency decisions explicit, inspectable, and reversible;
- remains modular and removable as upstream extraction quality improves.

## Options

### Option A: Selective source-aware re-extraction after document-wide first-pass analysis
Run the normal first-pass extractor, analyze the resulting artifact set at document scope to discover repeated pattern families and draft a document-local consistency plan, then selectively re-extract only flagged runs from source using broader context and the frozen plan for the relevant pattern family.

Pros:
- matches the observed failure mode without paying for a second flagship pass over the whole document;
- preserves the current page-level pipeline while adding a controlled escalation path;
- keeps provenance, fallback, and acceptance/rejection tractable;
- gives deterministic/statistical code a clear role in detection, clustering, plan validation, and quality gating;
- creates explicit artifacts that make model choices inspectable and revisable.

Cons:
- adds a second-pass architecture with more moving parts;
- depends on reliable run detection and acceptance logic;
- adds a document-analysis pass before reruns;
- if too many pages get flagged, the pipeline may still be operating at the wrong granularity.

### Option B: Run-aware or chapter-aware extraction from the start
For recipes dominated by repeated structures, extract directly from source at run/chapter scope instead of page scope so consistency is produced, not repaired.

Pros:
- likely highest quality when repeated structures dominate the document;
- avoids order-dependent repair loops and some second-pass complexity;
- may produce cleaner canonical structure with less downstream alignment logic.

Cons:
- highest upfront cost and latency if applied broadly;
- harder to generalize across mixed-layout documents;
- larger extraction units can make provenance, retries, and failure isolation more complex.

### Option C: Post-extraction HTML normalization and consistency alignment
Analyze extracted HTML, detect compatible structures, and rewrite HTML into a canonical shape, with little or no return to source.

Pros:
- cheaper than a second source-aware extraction pass;
- can still improve rendering consistency substantially for some cases;
- useful as a fallback or light cleanup layer after better extraction.

Cons:
- weaker than source-aware re-extraction when semantic understanding is needed;
- higher risk of silently flattening or losing distinctions;
- easy to overinvest in repairing artifacts that should have been re-extracted instead.

### Option D: Mostly deterministic/statistical normalization
Use DOM similarity, schema matching, clustering, sequence alignment, and rule-based canonicalization as the primary solution.

Pros:
- lowest recurring model cost;
- reproducible and easy to test;
- likely valuable for detection, gating, and acceptance even if not used as the main repair mechanism.

Cons:
- likely weakest on semantic hierarchy problems such as heading ownership, context fusion, and mixed heading/table representations;
- high risk of recipe overfitting;
- may re-create a brittle approximation of judgments that strong source-aware models already handle better.

## Research Needed

- [x] What existing libraries, products, or research are useful for detecting repeated structures or schema-compatible runs before deciding whether to re-extract?
- [x] What evidence exists that source-aware re-extraction with broader context beats post-extraction normalization for semi-structured document extraction?
- [x] What deterministic or statistical techniques are strong enough for low-cost run detection, clustering, schema inference, acceptance/rejection, and provenance reporting?
- [x] When is broader run-aware extraction from the start better than targeted second-pass re-extraction?
- [x] What role, if any, should HTML-only normalization play after adopting a source-aware consistency strategy?
- [x] What cost/quality thresholds should trigger a recipe redesign instead of repeated second-pass reruns?

## Repo Constraints / Existing Context

- `docs/ideal.md`: traceable, faithful output is the product.
- `docs/spec.md`: the current pipeline is a compromise and should use detection mechanisms to know when a compromise is no longer justified.
- Story 140 improved page-local genealogy rescue but did not solve chapter-wide structural consistency.
- Story 141 now captures the completed investigation slice. Its local baselines already show that a strong model over a broader source-informed scope outperforms the current deterministic cleanup.
- Story 142 completed the first concrete Onward slice under this ADR with read-only detection and rerun gating.
- Current modules such as `table_rescue_onward_tables_v1` and `build_chapter_html_v1` already contain partial normalization logic and should not keep absorbing unrelated responsibility.
- OCR/source reads are expensive, so any second pass must be selective by default.
- No prior ADRs exist yet beyond this one.

## Dependencies

- Story 141 supplied the investigation and handoff evidence for this ADR.
- Story 142, Story 143, and Story 144 now provide the first completed implementation ladder under this ADR.
- May affect future stories for heading consistency, list consistency, repeated-record extraction, and other format-specific run-aware extraction policies.
- No upstream ADR dependencies.

## Research Summary

<!-- Fill after research. Distill findings; do not paste raw model output. -->
- Cross-provider convergence is strong. OpenAI, Gemini, xAI, and Opus all recommend the same high-level architecture: detect repeated structures cheaply, rerun only the drifted regions from source with stronger schema/context, and keep HTML normalization light and deterministic.
- The main disagreement is not direction but thresholding. OpenAI is slightly more aggressive about redesigning extraction granularity (`25-30%` rerun coverage warning band), while Gemini is more tolerant (`30-40%`). xAI and Opus both cluster near `30%`. Current synthesis recommendation: `25%` warning band, `30%` redesign trigger across multiple documents.
- The reports agree that the first implementation slice should not jump straight to automated reruns. The safest first slice is a read-only detector/report that clusters likely same-schema runs, flags drift, infers provisional schema hints, and measures rerun coverage on real artifacts.
- The reports also converge on deterministic building blocks that are realistic to adopt now: header/column/span fingerprints, DOM/tag-sequence similarity, MinHash/SimHash-style screening, clustering, and optional tree-edit-distance or record-linkage for deeper validation.
- Research left representation target as the strongest open question, but Story 143 and Story 144 provided enough local evidence to settle the operational default: use direct HTML for the next repair slice, and escalate to a structured intermediate only if plan-aware reruns cannot reliably reduce conformance failures.

## Discussion

<!-- Chronological discussion notes, disagreements, corrections, and reasoning. -->
- 20260314: The initial framing was "HTML normalization and consistency alignment," but that risked overcommitting to post-hoc HTML repair as the main answer.
- 20260314: Local repo experience suggests a stronger principle: when better source-aware extraction is available, it usually beats repairing weaker extracted HTML.
- 20260314: The likely right question is not "how do we normalize HTML?" but "how do we achieve consistent canonical structure with the right mix of source-aware extraction, selective reruns, and light canonicalization?"
- 20260314: Provider synthesis tightened the rollout shape. All four reports converged on source-aware reruns plus deterministic detection, but they also converged that the first safe implementation slice is read-only drift detection and rerun gating, not immediate rerun automation.
- 20260314: The most useful synthesis outcome is the decision boundary: use rerun coverage as the signal for when page-scope extraction has become the wrong granularity. Current provisional band is `25%` warning / `30%` redesign trigger across multiple documents.
- 20260314: Story 143 materially strengthened the direct-HTML case for Onward genealogy reruns. A bounded coarse-page validation loop accepted `13/14` target pages and cleared three of the four reviewed bad chapters, but page `32` still shows that mixed context-heading plus family-heading pages may ultimately need a more structured target than raw HTML.
- 20260315: Manual inspection of the Story 143 artifacts showed broader format inconsistency beyond the reviewed chapter set. Fragmented tables, concatenated subgroup headings, fused `BOY/GIRL` headers, and left-column-only family rows can persist even when the current validator passes, which strengthens the case for document-wide pattern discovery plus explicit conformance artifacts.
- 20260315: The desired product is not a rigid global style guide. The consistency engine should infer document-local conventions from scratch each time, but it must emit those conventions as artifacts so they can be inspected, debugged, and later revised by users or downstream passes.
- 20260315: Story 144 is enough evidence to accept the document-consistency architecture now. The remaining uncertainty is implementation sequencing, not the decision itself, so the repair target is settled as direct HTML first with a structured intermediate held in reserve if plan-aware reruns prove insufficient.

## Decisions

<!-- Final decisions with rationale. Use "Settled — DO NOT suggest alternatives" for key calls. -->
- Settled — consistency should be treated as a document-wide pattern-discovery and conformance problem, not only as chapter-local drift detection. Chapter/run scope remains important for repair targeting and validation, but the policy source should be the whole document.
- Settled — each consistency-capable recipe should aim to emit three inspectable document-local artifacts: `pattern_inventory`, `consistency_plan`, and `conformance_report`.
- Settled — `consistency_plan` is document-local and may be generated fresh per document by AI. Codex-forge should not require a rigid cross-document formatting rulebook for every structure class.
- Settled — a single document may contain multiple legitimate pattern families. The engine may choose different conventions for different families, but those choices must be made explicit in the emitted plan.
- Settled — repair and rerun passes must be guided by the emitted `consistency_plan` and either conform to it or explicitly revise it. The policy must not drift invisibly across later passes.
- Settled — global invariants remain fixed even when the plan is adaptive: preserve source content, avoid semantic corruption, preserve provenance, and maximize internal consistency rather than forcing global sameness.
- Settled — the default architecture should be `extract -> document-wide pattern discovery -> consistency_plan -> selective rerun -> light canonicalization -> conformance_report`.
- Settled — use `25%` rerun coverage as an operational warning band and `30%` across multiple documents as the trigger to prototype broader extraction granularity for a recipe. These are evidence-based heuristics, not immutable thresholds.
- Settled — the next repair slice should emit direct HTML by default. Escalate to a structured intermediate representation only if plan-aware reruns cannot reliably reduce conformance failures, especially around mixed heading/family ownership cases.

## Integration Checklist

- [x] **docs/spec.md / docs/ideal.md / docs/requirements.md** — update any project direction or compromise implications
- [x] **Related stories** — update `Decision Refs` and add any new tasks or constraints
- [x] **AGENTS.md** — update if this changes workflow, conventions, or agent guardrails
- [x] **Runbooks / supporting docs** — update any operational docs affected by the decision
- [x] **Other ADRs / decision docs** — no other ADRs currently require cross-references
- [x] **Audit** — verify each decision is reflected in the right project artifact

## Remaining Work

<!-- Future stories, follow-ups, or open questions that flow from this ADR. -->
- [x] Story 142 completed the read-only detection/gating first slice under the synthesized strategy.
- [x] Story 143 completed the first automated schema-frozen rerun slice: the final reused-artifact run targeted `14` bounded coarse pages, accepted `13`, cleared `chapter-013.html`, `chapter-014.html`, and `chapter-015.html`, and reduced `chapter-010.html` from drift score `45` to `25` while preserving the reviewed good chapters.
- [x] Story 144 now captures the first document-level planning follow-up: emit `pattern_inventory`, `consistency_plan`, and `conformance_report` for the Onward genealogy slice, using the residual hard-page, fragmentation, fused-header, and concatenated-heading failures as validation cases.
- Next likely story: use the emitted `consistency_plan` to guide plan-aware selective reruns instead of relying on narrower schema hints alone.
- [x] The resulting workflow and decision heuristics are now distilled into reusable guidance in `docs/runbooks/document-consistency-planning.md` and `AGENTS.md`, so future sessions do not have to reconstruct the pattern from ADR-001.
- Next concrete implementation step: create the plan-aware selective rerun story that consumes `consistency_plan` and measures before/after conformance deltas.

## Work Log

<!-- YYYYMMDD-HHMM — event: outcome, evidence, next -->
- 20260314-1832 — ADR created: captured the shift from a table-only framing to a broader consistency decision; next step was external research.
- 20260314-1912 — ADR reframed: changed the core question from HTML normalization to source-aware consistency alignment and selective re-extraction, with normalization demoted to a secondary/fallback path; next step is research focused on run detection, rerun strategy, and cost/quality thresholds.
- 20260314-1957 — research kickoff: moved ADR-001 to `RESEARCHING` and created provider-specific research stubs for xAI and Opus so parallel external research can start from the same canonical prompt and feed into the synthesis step.
- 20260314-2324 — provider research runs completed: captured raw search-grounded reports from OpenAI (`gpt-5` + `web_search_preview`) and Gemini (`gemini-2.5-pro` + `google_search`) under `research/openai-research-report.md` and `research/gemini-research-report.md`; next step is synthesis back into the ADR and Story 142.
- 20260314-2352 — synthesis complete: combined xAI, Opus, OpenAI, and Gemini reports into one directionally consistent recommendation; moved ADR-001 to `DISCUSSING`, recorded the converged rollout shape, and shifted Story 142 toward detection/gating as the first implementation slice.
- 20260314-1818 — Story 142 closed the first implementation slice with a real-pipeline detector/report stage. The validated Onward run preserved the reviewed bad/good chapter split, mapped flagged drift back to culprit pages, and measured `strong_rerun_candidate_page_coverage=0.1607`, so the next implementation step remains targeted automated reruns rather than broader extraction granularity.
- 20260314-2147 — Story 143 created as the next explicit implementation slice: schema-frozen selective reruns for Story 142's strongest culprit pages, with provenance-preserving acceptance/rejection and rebuilt-chapter validation against the same reviewed bad/good chapter set.
- 20260314-2352 — Story 143 completed with a fresh reused-artifact validation run: bounded coarse-page reruns accepted `13/14` pages, cleared `chapter-013.html`, `chapter-014.html`, and `chapter-015.html`, reduced `chapter-010.html` from `45` to `25`, and preserved the reviewed good chapters. The main remaining open question is the mixed-heading page `32` case, now split into Story 144.
- 20260315-1027 — ADR reframed again after manual artifact inspection and follow-up design discussion: chapter-level gating is now explicitly treated as an early seam, while the intended architecture becomes document-wide pattern discovery plus explicit `pattern_inventory`, `consistency_plan`, and `conformance_report` artifacts for later repair passes and debugging.
- 20260315-1758 — Story 144 completed with validated document-level planning artifacts. Driver run `story144-onward-document-consistency-plan-r5` emitted `pattern_inventory`, `consistency_plan`, and `conformance_report` sidecars that surfaced the previously missed manual format-failure chapters (`011/012/013/014/018/019/020`), kept `chapter-009.html` in a row-semantic-containing bucket instead of pure format drift, and established the current chapter-first validator as an upstream signal producer rather than the policy source.
- 20260315-1231 — Story 144 validation hardening: a `/validate` follow-up exposed two normalization bugs in the first planning slice, so the planner now splits pure format-drift summaries from mixed issue summaries and rejects unsupported AI issue types that are not backed by dossier signals. Revalidation run `story144-onward-document-consistency-plan-r7` preserved the missed-format coverage, kept `chapter-009.html` out of pure-format summary buckets, and restored clean `chapter-023.html` to conformant status.
- 20260315-1347 — ADR accepted: Stories 142–144 resolved the major architecture questions. Codex-forge now treats document-wide consistency planning plus plan-aware selective reruns as the default strategy, adopts direct HTML as the next repair target by default, and reserves a structured intermediate for evidence-driven escalation rather than speculative upfront design.
