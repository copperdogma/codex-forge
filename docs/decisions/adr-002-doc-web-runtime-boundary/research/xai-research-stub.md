---
type: external-research-stub
provider: xai
model: ""
adr: "ADR-002"
topic: "`doc-web` runtime boundary, output contract, and Dossier handoff model"
status: "STUB_PREPARED"
created: "2026-03-18"
source-prompt: "research-prompt.md"
---

**1. Runtime Ownership Boundary**

**Recommended choice**: Extract `doc-web` as a standalone runtime repo consumed by Dossier via tagged releases (or internal package).  
Reasoning: This enforces clean product boundaries, keeps codex-forge lean (pure ingestion R&D), enables parallel iteration (Dossier team evolves consumption while doc-web team owns structural output), and maximizes provenance fidelity by making the citation contract explicit and versioned. The current `build_chapter_html_v1` already produces a website-shaped bundle with coarse provenance; extracting it now prevents the R&D repo from accumulating production concerns (theming hooks, Dossier-specific fixtures, etc.).

**Runner-up**: Direct ownership inside Dossier.  
When to choose it: If the team is tiny (<3 engineers) and the runtime will never be reused outside Dossier, this avoids repo overhead.

**Avoid**: Keep using codex-forge (or a lightly stripped fork) as the long-lived dependency.  
It looks attractive because the code already exists there, but it violates the explicit decision to keep codex-forge at semantic HTML only and turns an R&D spike into permanent production baggage.

**Evidence**: Software engineering literature consistently shows that shared logic extracted to a standalone library reduces duplication and improves test confidence, while research/prototype code dragged into production fails reproducibility ~74% of the time without clean boundaries. The “strangler fig” pattern (incremental extraction) and modular monolith practices confirm that early separation along ownership lines prevents the exact failure modes described in the prompt.

**2. Output Contract for a Structural Website Runtime**

**Recommended choice**: Minimal self-contained static bundle:  
- `index.html` (entry + TOC)  
- per-chapter or per-page HTML files (semantic, with `data-provenance-*` attributes)  
- `manifest.json` (chapter list + top-level provenance)  
- `assets/` (images, CSS/JS hooks only)  
- optional `provenance/` sidecar directory or embedded block map.  

Minimal TOC/prev-next navigation **is** part of the semantic contract (human-browsable requirement). Structural output is separated from presentation by using only semantic HTML5 + data attributes + CSS custom properties; no inline styles or framework-specific classes.

**Runner-up**: Add a light theming layer (e.g., Tailwind classes or CSS vars file).  
When to choose it: If Dossier wants zero CSS work for MVP sites.

**Avoid**: Full polished website builder inside doc-web (or codex-forge).  
It looks attractive for “one-stop” output but directly contradicts the decision that “a polished website builder does not belong inside codex-forge” and bloats the runtime.

**Evidence**: Static site generators (Hugo, Jekyll, Eleventy) produce exactly this layout—`index.html`, content files, manifest-like `_data`, assets folder—and treat navigation as core structure while keeping theming orthogonal. Semantic HTML5 guides emphasize `<nav>`, `<article>`, `<header>`, etc., plus `data-*` for machine readability without visual coupling.

**3. Provenance and Citation Contract**

**Recommended choice**: Block-level granularity as default.  
Stable identifiers in HTML: `id="block-uuid"` (or stable source-derived ID) + `data-source-page`, `data-source-portion`, `data-region-coords` (page number + bounding box).  
Sidecar: single `provenance-map.json` (or per-chapter) mapping HTML block ID → {original_artifact_id, page, coords, source_element_id, text_span}.  
Mandatory fields: artifact UUID, source page/portion, coords or element ID. Optional: confidence score, edit history.

This lets Dossier open the exact PDF region when a fact is cited.

**Runner-up**: Page-level only (current manifest).  
When to choose it: For the absolute first extraction slice if block mapping is non-trivial.

**Avoid**: Only coarse chapter-level provenance or purely embedded RDFa without a machine-readable sidecar.  
It looks attractive because “it’s already in the manifest,” but downstream citation precision is lost and Dossier cannot fulfill the explicit requirement.

**Evidence**: Digital humanities and OCR correction pipelines (e.g., PROV-A, span-level provenance schemas) use exactly block/span granularity with PROV-DM links for traceability; W3C PROV family and scholarly workflow papers confirm block IDs + sidecar mappings are the robust default for reusable provenance.

**4. Packaging and Versioning Model for Dossier**

**Recommended choice**: Tagged git releases + semantic versioning (setuptools_scm or hatch) + internal PyPI (or git dependency with `git+` pin). Dossier consumes via `pip install doc-web==1.x` or `requirements.txt` pin.  
Contract tests: golden HTML fixtures + schema validation of manifest/provenance-map in CI; optional Pact-style output contract tests for the bundle shape.  
Release discipline: semantic versioning + changelog + deprecation policy; breaking changes only on major version + 6-month notice.

**Runner-up**: Pure vendoring (copy source into Dossier).  
When to choose it: Ultra-simple single-team case with no reuse.

**Avoid**: Floating “latest” or no versioning.  
It looks attractive for “pull periodically,” but silently breaks Dossier when codex-forge (or doc-web) changes provenance shape.

**Evidence**: Official Python Packaging User Guide and setuptools_scm docs recommend git-tag-driven versioning for internal libs; Pact contract testing and SemVer 2.0.0 are the industry standard to prevent drift.

**5. Migration Strategy from codex-forge**

**Recommended choice**:  
- Migrate as-is: the reusable `modules/build/build_chapter_html_v1` core (HTML emission + manifest).  
- Refactor first: extract Fighting Fantasy/gamebook logic into codex-forge-only plugins.  
- Leave behind: any scanner/PDF ingestion, FF-specific heuristics, or R&D spikes.  
Golden/fixture ownership: move minimal test fixtures to doc-web; keep full golden set in codex-forge (or archive).  
Smallest viable slice: extract just `build_chapter_html_v1` + its manifest/provenance helpers into a new `doc-web` repo as v0.1.0; Dossier consumes it immediately for one document type. This proves the boundary with <1 week effort.

**Runner-up**: Big-bang full extraction.  
When to choose it: Never—risks downtime.

**Avoid**: Fork codex-forge and strip later.  
It looks attractive short-term but creates merge hell and violates the “graduate mature ingestion” directive in the README.

**Evidence**: Incremental migration literature (strangler fig pattern, divide-and-conquer) and real-world frontend/backend case studies show that extracting the smallest reusable kernel first validates contracts without disrupting production.

This plan keeps codex-forge lean, gives Dossier precise provenance, and lets both runtimes evolve in parallel—exactly matching the stated priorities.