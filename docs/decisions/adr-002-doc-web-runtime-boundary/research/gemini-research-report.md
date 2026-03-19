---
type: research-report
topic: doc-web-runtime-boundary
canonical-model-name: gemini-3.1-pro-preview
research-mode: standard
collected: '2026-03-19T05:30:23.394942+00:00'
---

Here is the architectural research and recommendation for extracting `doc-web` and integrating it with Dossier, optimized for provenance, clean boundaries, and AI-agent maintainability.

---

### 1. Runtime Ownership Boundary

**1. Recommended choice: Standalone `doc-web` repo consumed by Dossier**
*   **Reasoning:** Extracting `doc-web` into its own repository enforces a strict, network-level API/contract boundary. It prevents Dossier’s product requirements (e.g., user auth, database schemas) from leaking into the document conversion layer. Crucially, for AI-driven development, parallel agents work best when repositories have single, well-defined responsibilities. An agent working on Dossier won't accidentally break the HTML generation logic, and an agent optimizing `doc-web` won't get confused by Dossier's application code.
*   **Runner-up: Direct Dossier ownership (Monorepo / Sub-directory)**
    *   *When to choose:* If the overhead of managing multiple repositories, CI/CD pipelines, and version bumps severely bottlenecks your current velocity. You would place `doc-web` in a `packages/doc-web` folder within Dossier.
*   **Avoid: `codex-forge` (or a lightly stripped fork) as the dependency**
    *   *Downsides:* `codex-forge` contains R&D dead-ends and domain-specific logic (Fighting Fantasy). Using an R&D repo as a production dependency inevitably leads to "dependency bloat," where downstream systems inherit heavy ML libraries, experimental parsers, and fragile scripts they don't need.
*   **Evidence:** Conway’s Law applies to AI agents as much as humans; isolated repos create isolated, focused agent behaviors. The failure mode of "R&D repo becomes Prod dependency" is a classic anti-pattern (often called "Prototype to Production without Rewrite"), leading to high maintenance costs and deployment fragility.

---

### 2. Output Contract for a Structural Website Runtime

**1. Recommended choice: Standardized "Document Bundle" (Directory + Manifest)**
*   **Reasoning:** The output must be a self-contained directory. Structural navigation (TOC, prev/next) *is* part of the semantic contract because it defines the graph of the document. Visual polish is excluded.
    *   **Bundle Layout:**
        *   `index.html` (Entry point, TOC, book-level metadata)
        *   `chapters/` (Individual semantic HTML files)
        *   `assets/` (Images, extracted diagrams)
        *   `manifest.json` (Machine-readable TOC, reading order, metadata)
        *   `provenance.json` (Sidecar mapping HTML IDs to source coordinates)
    *   **Separation of Structure/Presentation:** HTML should use strict HTML5 semantic tags (`<article>`, `<section>`, `<nav>`, `<aside>`). No inline styles. Dossier will inject a `theme.css` at runtime.
*   **Runner-up: Single-file HTML with embedded assets and JSON-LD**
    *   *When to choose:* If the documents are consistently small (e.g., short papers, not full books) and you want to avoid managing directory structures in Dossier's storage layer.
*   **Avoid: Emitting raw UI Components (e.g., React/Vue files) or Markdown**
    *   *Downsides:* Emitting React couples the runtime to a specific frontend framework. Emitting Markdown loses the semantic richness (tables, complex nested lists, asides) required for high-fidelity book ingestion.
*   **Evidence:** The EPUB standard utilizes exactly this model (structural HTML + XML manifests + assets in a zipped bundle). Static Site Generators (like Hugo or Next.js) rely on intermediate structural representations before applying themes.

---

### 3. Provenance and Citation Contract

**1. Recommended choice: Block-level `data-prov-id` with a JSON Sidecar**
*   **Reasoning:** To support exact fact citations (opening a PDF to a specific paragraph), provenance must be at the **block level** (paragraph, header, list item, image).
    *   **HTML Contract:** Every structural block gets a stable ID: `<p data-prov-id="blk_01H..."></p>`.
    *   **Sidecar Contract (`provenance.json`):** Maps `blk_01H...` to:
        *   `source_file`: "original.pdf"
        *   `source_page`: 42
        *   `bbox`: `[x1, y1, x2, y2]` (bounding box for highlighting)
        *   `extraction_confidence`: 0.98
    *   *Why sidecar?* It keeps the HTML clean and lightweight for AI context windows. Injecting bounding boxes directly into HTML attributes bloats the DOM and distracts LLMs reading the HTML.
*   **Runner-up: Inline Data Attributes**
    *   *When to choose:* If managing a separate sidecar file creates too much complexity in Dossier's database, you can embed minimal provenance directly: `<p data-source-page="42" data-source-bbox="...">`.
*   **Avoid: Character-level provenance or DOM-hierarchy selectors (XPath)**
    *   *Downsides:* Character-level tracking requires massive data structures (e.g., source maps) that are brittle to whitespace changes. XPath selectors break the moment Dossier wraps a paragraph in a `<div>` for styling.
*   **Evidence:** The W3C Web Annotation Data Model separates the "Target" (the HTML ID) from the "Body" (the annotation/provenance data). Standard RAG (Retrieval-Augmented Generation) pipelines use block-level chunking with metadata sidecars for citation.

---

### 4. Packaging and Versioning Model for Dossier

**1. Recommended choice: Tagged Git Releases consumed via Package Manager**
*   **Reasoning:** `doc-web` should be versioned using Semantic Versioning (SemVer) via Git tags (e.g., `v1.2.0`). Dossier consumes it using standard package manager git-dependencies (e.g., `pip install git+https://...` or `npm install git+https://...`).
    *   **Contract Tests:** Dossier must maintain a suite of "Golden Fixtures" (a set of known `doc-web` output bundles). During Dossier's CI, it parses these fixtures. If `doc-web` changes the manifest schema or HTML structure, Dossier's tests fail.
    *   **Release Discipline:** `doc-web` only merges to `main` via PR. Tags are cut manually or via CI. Dossier updates its dependency pin explicitly.
*   **Runner-up: Internal Package Registry (Private PyPI / GitHub Packages)**
    *   *When to choose:* When `doc-web` matures and is consumed by *multiple* downstream systems, not just Dossier, making Git-URL dependencies cumbersome.
*   **Avoid: Git Submodules or Vendoring (Copy-pasting code)**
    *   *Downsides:* Submodules are notoriously difficult for AI agents (and humans) to manage correctly regarding detached heads and synchronized commits. Vendoring destroys the boundary and makes updates a manual, error-prone diffing process.
*   **Evidence:** "Consumer-Driven Contracts" is a proven microservices pattern. Pinning to Git tags is the standard lightweight distribution method in Go, Python, and Node ecosystems before committing to a formal package registry.

---

### 5. Migration Strategy from codex-forge

**1. Recommended choice: "Strangler Fig" Extraction (Smallest Viable Slice)**
*   **Reasoning:** Do not attempt a massive rewrite.
    *   **First Slice:** Extract *only* the generic data models (Chapter, Page, Manifest) and the `build_chapter_html_v1` emitter into `doc-web`.
    *   **Refactor:** Strip out any Fighting Fantasy logic from the emitter. The emitter should only accept generic structural data.
    *   **Integration:** Update `codex-forge` to import `doc-web` as a dependency. `codex-forge` retains the FF-specific parsers, transforms that data into `doc-web`'s generic models, and calls `doc-web` to generate the HTML.
    *   **Golden Ownership:** The generic HTML/Manifest fixtures move to `doc-web`. The FF-specific PDF-to-HTML fixtures stay in `codex-forge`.
*   **Runner-up: Clean Break / Fresh Start**
    *   *When to choose:* If `build_chapter_html_v1` is so deeply entangled with FF-logic that untangling it takes longer than writing a clean, generic HTML emitter from scratch in `doc-web`.
*   **Avoid: "Lift and Shift" (Moving the whole repo and deleting later)**
    *   *Downsides:* Moving `codex-forge` to `doc-web` and trying to delete the R&D/FF code later usually results in leftover dead code, confusing abstractions, and a polluted git history in the new runtime.
*   **Evidence:** Martin Fowler’s "Strangler Fig Application" pattern is the industry standard for migrating legacy/R&D systems to clean architectures. Extracting pure functions and data models first minimizes regression risk.