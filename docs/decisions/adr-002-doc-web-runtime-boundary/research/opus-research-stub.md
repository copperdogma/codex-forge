---
type: external-research-stub
provider: anthropic
model: "Claude Opus"
adr: "ADR-002"
topic: "`doc-web` runtime boundary, output contract, and Dossier handoff model"
status: "STUB_PREPARED"
created: "2026-03-18"
source-prompt: "research-prompt.md"
---

# Five architectural decisions for a document-to-website runtime

A document-to-website conversion layer ("doc-web") sitting between an R&D repo and a product requires decisive answers on ownership, contracts, provenance, packaging, and migration. **The strongest overall pattern is a standalone extracted library with a phased graduation, consuming via a private package registry, using paragraph-level provenance anchored by W3C Web Annotation selectors, and outputting classless semantic HTML with a JSON manifest.** Each decision below draws on real-world extractions (Jupyter's Big Split, React's Instagram-driven decoupling, TensorFlow's tf.contrib disaster) and mature standards (EPUB, W3C Web Annotation, Dublin Core) to separate what works from what merely looks attractive.

---

## 1. A standalone repo wins the ownership boundary question

**Recommended: Standalone `doc-web` repo consumed via tagged releases (Option A).** This forces what Martin Fowler calls a "Published Interface" — an API surface with explicit backward-compatibility obligations that is stronger than merely "public" code. When multiple AI agents work on different parts, repo-level separation acts as an architectural wall: agents modifying Dossier operate against a versioned contract while agents iterating on doc-web internals cannot accidentally couple product code to runtime implementation details. The monorepo.tools documentation confirms that "repo boundaries act as walls for both humans and AI assistants."

The key enabler is **contract clarity**. A standalone repo forces the team to define and version the interface, adopt semantic versioning, and maintain a changelog. This creates the discipline needed for parallel iteration — the runtime can ship **v1.3.0** while Dossier stays pinned to **v1.2.x** until ready to upgrade.

**Runner-up: Absorb the runtime directly into Dossier (Option B).** Choose this only if doc-web will never serve a second consumer and the team wants maximum velocity with zero coordination overhead. Microsoft's DevBlogs notes that in a single-codebase model, teams "can always change a piece of code with all its clients in a single PR" — a real advantage for small teams. The moment a second product needs the runtime, however, absorption kills reuse and forces a painful re-extraction.

**Avoid: Keeping the R&D repo (codex-forge) as a long-lived dependency (Option C).** This is the most dangerous option. The Google "Hidden Technical Debt in ML Systems" paper (Sculley et al., 2015, cited 5,000+ times) explicitly warns about "Prototype Smell": relying on a prototyping environment in production creates brittle systems. TensorFlow's `tf.contrib` is the canonical failure case — despite explicit warnings that `tf.contrib` carried no compatibility guarantees, thousands of production systems depended on it. The TensorFlow 2.0 migration had to **completely remove tf.contrib**, breaking tutorials, courses, and production deployments wholesale. Features scattered to four different destinations: TF core, tensorflow-addons, external repos, or discontinued entirely. Hyrum's Law is unforgiving: with sufficient users, all observable behaviors become depended upon regardless of disclaimers.

**Evidence.** The IPython→Jupyter "Big Split" (2014–2015) demonstrates both the pain of delayed extraction and the path forward. IPython 3.x bundled interactive shell, notebook server, Qt console, messaging protocol, and parallel computing in one repository. The split moved language-agnostic components to Jupyter: `IPython.html` → `notebook`, `IPython.kernel` → `jupyter_client` + `ipykernel`, `IPython.config` → `traitlets.config`, and more. Configuration files moved locations, breaking existing setups. The lesson: delaying extraction until the project was massive made the split far more painful than it needed to be. Block's (Cash App) engineering blog documents polyrepo failure modes at the other extreme — 450 interconnected services without semver, where "some teams declared 'dependency bankruptcy,' ignoring dependency updates entirely." The CNCF maturity model (Sandbox → Incubating → Graduated) and Kubernetes Gateway API graduation criteria (full conformance tests, multiple implementations, **≥6 months soak time**) provide the clearest frameworks for when experimental code is ready for promotion.

---

## 2. Classless semantic HTML with a JSON manifest defines the output contract

**Recommended: A publication manifest (JSON) plus semantic HTML content pages with no custom CSS classes.** Cross-referencing EPUB 3, W3C Publication Manifest, and Readium WebPub Manifest reveals a convergent minimal structure:

```
manifest.json          # Metadata, reading order, resource inventory
index.html             # Entry point
nav.html               # Hierarchical TOC as <nav> elements
content/
  chapter-1.html       # Semantic HTML5 (<article>, <section>, <main>)
  chapter-2.html
assets/
  style.css            # Classless CSS default (swappable)
  images/
```

The manifest serves as the machine-readable "brain" — analogous to EPUB's `content.opf` — providing `readingOrder` (array of content documents), `resources` (assets), and Dublin Core metadata (title, identifier, language, modified date). Every major documentation tool (Sphinx, mdBook, MkDocs, Docusaurus) defines reading order and navigation as **structural data**, not presentation. Navigation belongs in the contract.

**Navigation is structural, not presentational.** EPUB 3 makes this unambiguous: `nav.xhtml` is a required structural component using `<nav epub:type="toc">` with nested `<ol>` lists. Sphinx uses `toctree` directives. mdBook uses `SUMMARY.md`. Docusaurus uses `sidebars.js`. MkDocs uses `nav:` in YAML. In every case, the visual rendering (sidebar vs. hamburger menu vs. bottom pagination) is the theme's job, but the hierarchical structure and reading order are defined at the content layer. The output contract should embed `<link rel="prev">` and `<link rel="next">` in each page's `<head>` — derivable from the manifest's reading order — and include landmarks (cover, start-of-content, bibliography) following EPUB 3's `epub:type="landmarks"` pattern.

**The classless CSS approach is the theming contract.** Classless CSS frameworks (Water.css at ~2KB, Pico.css at ~10KB) demonstrate that **semantic HTML needs zero custom classes** to render beautifully. They style elements directly: `<article>`, `<section>`, `<nav>`, `<table>`. Theming happens entirely via CSS custom properties: `--color-primary`, `--font-body`, `--max-width`. A Hugo "Classless" theme exists that generates pure semantic HTML, letting users swap between Pico.css, Water.css, and Simple.css by changing a single `<link>` tag. This is the CSS Zen Garden philosophy applied to document websites — and it means the runtime's HTML output is the **stable contract** while any theme can be applied without modifying a single element.

**Runner-up: BEM/semantic class naming when truly needed.** If specific structural hooks are required beyond HTML5 semantics (e.g., `doc-toc`, `doc-chapter`, `doc-citation`), use structural names rather than presentational ones. SMACSS explicitly separates Theme rules from Layout and Module rules, providing a framework for when classes become necessary.

**Avoid: Tailwind-style utility classes or custom presentational classes in the structural output.** This couples the runtime's HTML to a specific CSS framework, violating structure/presentation separation. It also makes AI parsing harder — utility classes like `text-lg font-bold mt-4` carry no semantic meaning.

**Evidence.** Pandoc, mdBook, Sphinx, Hugo, Jekyll, Docusaurus, and MkDocs all output distinct file structures, but the documentation-focused tools (mdBook, Sphinx, MkDocs, Docusaurus) converge on: a configuration/manifest file defining reading order, a generated TOC/sidebar, prev/next navigation derived from reading order, a search index, and clean separation of theme from content via template systems. The W3C Web Publications specification was published as a Note (not Recommendation) due to "lack of practical business cases," but the manifest format itself succeeded as a W3C Recommendation — confirming that the manifest concept is sound even if the full "web publication" vision didn't gain traction.

---

## 3. Paragraph-level provenance with W3C Web Annotation selectors is the right default

**Recommended: Paragraph-level provenance using `id` attributes for fragment navigation plus `data-*` attributes for source coordinates, with a W3C Web Annotation JSON-LD sidecar manifest.** GROBID — the leading scholarly PDF extraction tool — operates natively at paragraph granularity, producing `@coords` attributes encoding `page,x,y,w,h` bounding boxes on each extracted `<p>`, `<head>`, `<figure>`, and `<ref>` element. This matches the sweet spot: precise enough to "jump to the right paragraph" while avoiding the storage overhead and fragility of word-level tracking.

Each HTML block should carry these **mandatory attributes**:

- `id="block-{content_hash[:12]}"` — content-derived, stable across re-extraction
- `data-source-file="document.pdf"` — source artifact path or URI
- `data-source-page="5"` — 1-indexed page number
- `data-source-bbox="72,150,540,200"` — bounding box in PDF coordinate units

**Recommended additional fields** include `data-source-hash` (SHA-256 of the source file for integrity verification), `data-confidence` (extraction confidence score 0–1), and `data-extraction-method` (tool and version, e.g., `grobid-0.8.1`).

The W3C Web Annotation Data Model (W3C Recommendation, February 2017) defines **nine selector types** for identifying targets in documents. The critical ones for this use case are **TextQuoteSelector** (stores exact text with prefix/suffix context for fuzzy matching), **CssSelector** (`#block-id`), and **FragmentSelector** (wraps `#page=5` or `#xywh=72,150,468,50`). Hypothesis — the most widely deployed open annotation system — uses a **three-selector strategy** per annotation: TextQuoteSelector (primary, most robust), TextPositionSelector (fast lookup), and RangeSelector (DOM hint). This redundancy ensures anchors survive DOM changes.

**The sidecar manifest should use W3C Web Annotation JSON-LD**, with one `AnnotationCollection` per converted document and one `Annotation` per HTML block. Each annotation's `body` points to the source PDF via a FragmentSelector (`page=5`) refined by a coordinate selector (`xywh=72,150,468,50`), and the `target` points to the HTML element via CssSelector. Dublin Core metadata at the collection level provides `dc:title`, `dc:creator`, `dc:date`, `dc:identifier`, and `dc:source`.

For click-to-source deep linking, **`document.pdf#page=N`** is universally supported by PDF viewers. For coordinate-level positioning, PDF.js supports `viewer.html?file=document.pdf#page=N&zoom=auto,X,Y`. Named destinations (`#nameddest=section3`) are the most stable deep links but require the PDF to contain them.

**Runner-up: Sentence-level provenance.** Choose this when individual claims need provenance (fact-checking, RAG citation). GROBID supports optional sentence segmentation via the `segmentSentences` parameter, yielding `<s>` elements within paragraphs. The CiTO ontology explicitly envisions marking up "to the level of the paragraph, the sentence or even the individual word." Generate sentence-level provenance lazily or on demand rather than as the default.

**Avoid: Block-level-only provenance (section/div granularity).** This is too coarse — clicking a section-level citation can only land on a page, not a specific paragraph. Also avoid **span/word-level provenance as the default** — GROBID's underlying layout token model tracks individual tokens, but exporting this granularity creates massive storage overhead and rarely provides actionable benefit over paragraph-level.

**Evidence.** JATS XML (ANSI/NISO Z39.96) models scholarly articles at paragraph granularity with `@id` attributes on every structural element. TEI P5 (used by GROBID output) provides `@xml:id` on any element with `<facsimile>` elements encoding page dimensions. IIIF's coordinate-based selectors on Canvas URIs are directly analogous to PDF coordinate references — a "Canvas" abstraction over PDF pages enables identical patterns. Dublin Core defines 15 core elements (all optional), but for provenance the essential fields are `dc:title`, `dc:creator`, `dc:date`, `dc:identifier`, and `dc:source`. CrossRef requires title, at least one author surname, publication date, DOI, and resolution URL for DOI registration — establishing the practical minimum for citation metadata.

---

## 4. A private package registry with contract tests prevents silent breakage

**Recommended: Internal/private package registry (PyPI via devpi, npm via Verdaccio, or GitHub Packages) with consumer-driven contract tests.** A private registry gives you **immutable published versions** (cannot overwrite a released version), standard tooling integration (pip, npm, cargo), lock file support for reproducibility, and audit trails. JFrog Artifactory is the enterprise standard; GitHub Packages integrates directly with GitHub permissions; devpi is the standard self-hosted Python registry.

Pair the registry with a **multi-layer testing strategy**:

- **Golden file/snapshot tests** in the consumer repo capturing the library's output format — any format change causes explicit test failure
- **Schema validation** via JSON Schema or typed interfaces defining the structural contract
- **Breaking change detection** in the library's CI using **Griffe** (Python) or **API Extractor** (TypeScript), which can compare two versions and enumerate removed members, parameter changes, and type modifications
- **Automated dependency update PRs** via Renovate or Dependabot, running the consumer's full test suite against each proposed upgrade

For release discipline, enforce **Conventional Commits** with commitlint and automate versioning with **semantic-release** (fully automated) or **Changesets** (developer-driven, native monorepo support). A study of 100,000+ jar files in Maven Central found that **~1/3 of all releases introduce at least one breaking change, and this rate is identical for minor and major releases** — meaning version numbers alone are unreliable. Automated breaking-change detection in CI is essential, not optional.

**Runner-up: Tagged git releases with commit-hash pinning.** This works when registry infrastructure is too heavy for the team's current scale. Lock files can pin the resolved commit hash for reproducibility. However, **git tags can be moved, force-pushed, or deleted** — a tag-pinned dependency can be silently replaced with different content. Research presented at NDC Oslo 2025 demonstrated live supply-chain attacks exploiting mutable git tags in Terraform modules. If using this approach, always verify commit hashes in lock files.

**Avoid: Git submodules.** Despite clean separation in theory, submodules are notorious for developer experience friction — requiring `git submodule init`, `git submodule update`, `--recurse-submodules`, and separate lifecycle commands. Desynchronization between parent and submodule is a common source of "empty directory" bugs, and the approach is confusing for newcomers. Also avoid **vendoring as the primary delivery mechanism** — while it provides total independence from registries, it creates stale code (manual effort to pull updates), merge conflicts when updating, and loss of upstream commit history. Vendoring is appropriate as a fallback or for supply-chain security auditing, not as the primary consumption model.

**Evidence.** Pact contract testing has proven adoption at **Microsoft ISE** (published guidance noting Java Pact is more mature than Python), **Postman** (consumer-driven contracts as "one of the biggest drivers in conquering our dependency hell"), and **Deliveroo** (Protobuf-based event streaming contracts). The Creative Commons project switched from CalVer to SemVer after discovering that CalVer set false expectations — large year-change numbers implied significant updates even when changes were trivial. For libraries consumed as dependencies, **SemVer is the correct choice** because the tooling ecosystem (package managers, dependency resolvers, update bots) is built around it.

---

## 5. Extract one complete module first, using the strangler fig pattern

**Recommended: Seam-based minimum viable extraction of one complete module, then gradual strangler fig expansion.** Michael Feathers defines a seam as "a place where you can alter behavior in your program without editing in that place." The smallest viable extraction that proves the boundary includes:

1. **One self-contained module** with its own tests (choose the most frequently used, most stable, smallest-to-extract piece)
2. **A clean API boundary** (interface or abstraction layer) that codex-forge calls through
3. **Both implementations running simultaneously** — old in-place code and new extracted library
4. **A toggle to route between them**, verifying the same test suite passes against both
5. **Verification complete** → remove the old implementation

This follows the **Branch by Abstraction** pattern (named by Stacy Curl, popularized by Fowler): create an abstraction capturing the interaction, move all callers to use it, build the new implementation behind it, run both in parallel, switch, then remove the old. ThoughtWorks' "Go" CD tool migrated from iBatis to Hibernate this way — the repository layer served as the abstraction, with a rule: "Never add an iBatis query — even if easier. Fail the build when a new one is added."

For test fixtures during the split, **copy, don't move**. The Jupyter Big Split established this precedent: the migration process copies files rather than moving them, ensuring both old and new systems continue working. Create a transitional utility package (like Jupyter's `ipython_genutils`, explicitly labeled "this package shouldn't exist") with an **explicit sunset date and deprecation warnings**. Keep golden files self-contained per module — each extracted component carries its own test fixtures rather than creating cross-repo dependencies.

**Code classification for extraction** follows a clear taxonomy. Code that migrates as-is: pure functions, stateless utilities, modules with well-defined interfaces that haven't changed recently. Code needing refactoring: tangled dependencies, hard-coded R&D configuration, missing error handling, global state. Code that stays behind: experiment-specific orchestration, visualization notebooks, parameter sweeps, code with unstable APIs still undergoing rapid iteration.

**Runner-up: Anti-Corruption Layer (ACL) pattern from Domain-Driven Design.** When R&D code carries assumptions, naming conventions, or data structures that shouldn't leak into the production library's design, implement a façade/adapter translating between the R&D "language" and the library's clean API. This is complementary to the strangler fig approach and should be used together when the R&D repo's domain model differs significantly from the production library's target API.

**Avoid: Big-bang rewrite or "announce deprecation without a ready replacement."** Angular's AngularJS→Angular 2 rewrite is the canonical cautionary tale. The 2014 announcement of a non-backward-compatible rewrite created a **two-year gap** where developers couldn't choose AngularJS (deprecated) or Angular 2 (not stable). As Angular team member Stephen Fluin admitted: "You couldn't choose AngularJS because it was deprecated. You couldn't choose Angular because it wasn't stable. So people chose React." The community felt betrayed, and the mass exodus to React permanently shifted the framework landscape. The `ngUpgrade` hybrid tool came too late — incremental migration tooling must exist from day one.

**Evidence.** React's extraction from Facebook's internal tools was triggered by the **Instagram acquisition** — a second consumer in a foreign codebase forced decoupling. Pete Hunt described it as "Facebook internally open-sourcing React to Instagram." The need to serve two different callers proved the boundary was real. PyTorch's extraction from Facebook Research followed a different path: decoupling the Python frontend from the C++/CUDA backend, then open-sourcing from day one to accelerate community adoption. PyTorch eventually **merged with Caffe2** (Facebook's production ML framework) rather than maintaining parallel implementations — consolidating rather than splitting. The Jupyter split created **134+ repositories** from one monolithic IPython codebase, but maintained backward compatibility through import shims so all IPython 3 code continued working on IPython 4.

The most important lesson across all these case studies: **have a second consumer to force decoupling**. If the code can serve two different callers through a clean interface, it is properly extracted. Dossier is the first consumer; the extraction is proven when a hypothetical second consumer could adopt doc-web without knowing anything about Dossier's internals.

---

## Conclusion

These five decisions form a coherent system. The standalone repo (§1) creates the Published Interface that the JSON manifest output contract (§2) and provenance sidecar (§3) make concrete. The private registry with contract tests (§4) enforces that contract across releases. And the seam-based extraction (§5) provides the migration path from R&D repo to that standalone library.

Three insights cut across all five decisions. First, **boundary clarity enables parallel AI agent work** — agents operating against a versioned contract cannot accidentally couple implementation details across the boundary. Second, **standards convergence is real**: EPUB, W3C Publication Manifest, Readium WebPub, and every documentation tool agree that reading order, navigation structure, and metadata belong in a machine-readable manifest, while visual rendering is the theme's problem. Third, **the extraction is not a one-time event but a graduated process** — the CNCF Sandbox→Incubating→Graduated maturity model, applied to an internal library, provides the right pacing: define the boundary now, extract with pre-release versions, stabilize through production use in Dossier, then declare v1.0 after sufficient soak time.