# Story 130: Book Website Template Module

**Status**: In Progress

---
**Depends On**: story-129 (HTML output polish — needs clean, semantic base HTML as input)

## Goal
Create a pipeline module that transforms the polished chapter HTML (from Story 129) into an elegant, minimal **static website** — a "website form of a book" that can be opened locally or hosted anywhere.

The output is a **generic starting point**, not a finished bespoke site. The user can then take the generated site and tweak styling, layout, or branding to taste — those customizations live outside the pipeline.

## Design Philosophy
- **Opinionated but minimal**: Ship a single tasteful design, not a theme system. Good typography, clean layout, readable on any device.
- **Static files only**: HTML + CSS + images. No build step, no bundler, no server required. Open `index.html` in a browser and it works.
- **Content untouched**: The module wraps and arranges content from Story 129's output — it does not modify text, tables, or images.
- **Forkable output**: The generated site should be easy to understand and modify. Clean CSS with variables, obvious file structure, no minification. A developer (or an LLM) should be able to tweak it in minutes.
- **Pipeline module**: Runs as a stage in the recipe, takes chapter HTML + manifest as input, emits a complete static site as output. Generic — works for any book.

## What It Produces
```
output/site/
├── index.html          # Landing page (book title, cover image, chapter list)
├── toc.html            # Full table of contents with page ranges
├── chapters/
│   ├── 001.html        # Chapter pages (content wrapped in site template)
│   ├── 002.html
│   └── ...
├── images/             # Copied from pipeline output
│   ├── cover.jpg
│   └── ...
├── css/
│   └── style.css       # Single stylesheet with CSS custom properties
└── pages/              # Frontmatter / non-chapter pages (if any)
    ├── dedication.html
    └── ...
```

## Acceptance Criteria
- [ ] **Pipeline module exists**: A new module (e.g., `build_book_site_v1`) that takes chapter HTML + manifest and emits a static site.
- [ ] **Landing page**: `index.html` with book title, cover image (if available), short description, and links to TOC / first chapter.
- [ ] **Table of contents**: Navigable chapter list with titles and printed page ranges.
- [ ] **Chapter pages**: Each chapter wrapped in the site template with consistent header, footer, and navigation.
- [ ] **Chapter navigation**: Prev / next links on every chapter page. TOC link always accessible.
- [ ] **Responsive design**: Readable on desktop, tablet, and phone viewports without horizontal scrolling.
- [ ] **Good typography**: Comfortable reading font, appropriate line-height and measure (max ~70ch), well-styled headings.
- [ ] **Table styling**: Genealogy tables are readable with clear borders, header distinction, and reasonable column widths. Tables scroll horizontally on narrow viewports rather than breaking layout.
- [ ] **Image presentation**: Photos displayed at appropriate size, clickable to view full resolution. Captions styled distinctly.
- [ ] **CSS custom properties**: Colors, fonts, and spacing defined as variables at the top of the stylesheet so the user can restyle by changing a few lines.
- [ ] **Self-contained**: The `output/site/` directory works when copied to any location or hosted on any static file server. No external CDN dependencies.
- [ ] **No JavaScript required**: Core reading experience works without JS. JS is allowed only for progressive enhancements (e.g., smooth scroll, image lightbox) that degrade gracefully.
- [ ] **Generic**: Module accepts book title, author, cover image path, and description from recipe config. Works for any book, not just Onward.
- [ ] **Wired into Onward recipe**: Added as the final stage in `recipe-onward-images-html-mvp.yaml`.

## Approach
1. **Template system**: Simple string-based HTML templates (Python f-strings or `string.Template`) in the module. No Jinja2 or template engine dependency needed for this scope.
2. **Single CSS file**: One `style.css` with CSS custom properties for theming. Well-commented sections (reset, typography, layout, tables, images, navigation, responsive).
3. **Content injection**: Read each chapter HTML file from Story 129's output, extract the `<article>` body, wrap it in the site template with header/nav/footer.
4. **Asset copying**: Copy images from the chapter HTML `images/` directory into the site's `images/` directory.
5. **Manifest-driven**: Use the chapters manifest to generate TOC, navigation links, and page metadata.

## Non-Negotiables
- **No build tools**: The module outputs final HTML/CSS directly. No npm, webpack, Sass, or any post-processing step.
- **No external dependencies**: No Google Fonts CDN, no Bootstrap, no framework. System font stack + hand-written CSS.
- **No content modification**: Tables, text, and images are passed through exactly as they come from the pipeline.
- **Forkable**: Someone should be able to copy `output/site/`, open `css/style.css`, change the font and colors, and have a custom-branded book site in 5 minutes.

## Tasks
- [ ] Design the site template (HTML structure for landing, TOC, and chapter pages)
- [ ] Write `style.css` with CSS custom properties (typography, layout, tables, images, responsive)
- [ ] Implement `build_book_site_v1` module (manifest input → static site output)
- [ ] Generate landing page with book metadata from config
- [ ] Generate TOC page from chapter manifest
- [ ] Wrap each chapter in site template with prev/next navigation
- [ ] Copy and link images correctly
- [ ] Handle frontmatter / non-chapter pages
- [ ] Test on desktop browser (Chrome/Safari)
- [ ] Test on mobile viewport (responsive layout, table horizontal scroll)
- [ ] Test self-contained: copy `output/site/` to `/tmp`, open — everything works
- [ ] Wire module into Onward recipe as final stage
- [ ] Document config parameters (book title, author, cover image, description)

## Open Questions
- Should the landing page include a book description/blurb, or just title + cover + chapter links?
- Should there be a search feature (client-side JS search across chapters)?
- Should image lightbox (click to enlarge) be included, or is that a downstream customization?

## Plan

### Exploration Findings

**Input structure**: `build_chapter_html_v1` produces `chapters_manifest.jsonl` with rows containing `chapter_index`, `title`, `page_start`, `page_end`, `file` (absolute path to HTML), `kind` ("chapter" or "page"). Each HTML file is a full HTML5 document with embedded CSS, `<article>` body, `<nav>` elements. Images in sibling `images/` directory.

**Content extraction**: Each chapter HTML wraps content in `<article>`. The new module extracts `article.decode_contents()` via BeautifulSoup to get the inner HTML, discarding the existing CSS/nav/document wrapper.

**Module placement**: `modules/build/build_book_site_v1/module.yaml` + `main.py`. Driver auto-discovers via `module.yaml` scan. Use `transform` stage type in recipe (not `build`, which requires `pages` + `portions` inputs).

**Recipe wiring**: Append to `recipe-onward-images-html-mvp.yaml` as final stage with `inputs: {chapters: build_chapters}` and params for `book_title`, `book_author`, `book_description`, `cover_image`.

**Output location**: `<module_dir>/site/` — keeps output under the run's artifact tree for proper provenance tracking.

**Image handling**: Copy from `build_chapter_html_v1`'s `images/` dir into `site/images/`. Resolve source dir from any manifest row's `file` path → `Path(row["file"]).parent / "images"`.

**CSS approach**: Single `css/style.css` with CSS custom properties at the top. Well-commented sections. System font stack. The chapter HTML already has good semantic structure (`<figure>`, `<figcaption>`, `<table>` with `scope`), so the site CSS just needs to style those elements.

**No schema changes needed**: No formal schema in `schemas.py` for this output — manifest is self-describing JSONL.

### Eval-First Approach

**Eval type**: Pytest structural tests (deterministic HTML generation, not AI quality).
**Baseline**: Module doesn't exist yet — baseline is 0/N.
**Approach**: Single approach (Python string templates + BeautifulSoup extraction). No AI comparison needed — this is pure orchestration/plumbing.

### Implementation Plan

#### T1: Create module skeleton (`module.yaml` + `main.py`)
- **New files**: `modules/build/build_book_site_v1/module.yaml`, `modules/build/build_book_site_v1/main.py`
- **module.yaml**: stage=transform (for recipe), params: book_title, book_author, book_description, cover_image
- **main.py**: argparse CLI accepting `--chapters <manifest.jsonl> --out <site_manifest.jsonl>` + param flags
- **Done when**: Module is discoverable by driver and accepts CLI args

#### T2: Write `css/style.css` content
- **Where**: CSS constant string in `main.py` (written to `site/css/style.css` at runtime)
- **Sections**: Reset, CSS custom properties (colors, fonts, spacing), typography, layout, navigation (header/footer), tables, figures/images, responsive breakpoints, print
- **Key properties**: `--font-body`, `--font-serif`, `--color-bg`, `--color-text`, `--color-accent`, `--max-width`, `--line-height`
- **Done when**: CSS renders a readable, responsive book site

#### T3: Design HTML templates (landing, TOC, chapter)
- **Where**: Python string templates in `main.py` (f-strings or `string.Template`)
- **Landing (`index.html`)**: Book title, cover image (if available), description, link to TOC and first chapter
- **TOC (`toc.html`)**: Chapter list with titles and page ranges
- **Chapter (`chapters/NNN.html`)**: Site header, extracted `<article>` content, prev/next nav, site footer
- **Done when**: Templates produce valid HTML5 with linked CSS

#### T4: Implement content extraction and chapter wrapping
- **Logic**: Read `chapters_manifest.jsonl`, parse each HTML file with BeautifulSoup, extract `<article>` inner HTML, wrap in chapter template with nav links
- **Navigation**: Prev/next links computed from ordered chapter list. TOC link always present.
- **Chapters vs pages**: Both `kind="chapter"` and `kind="page"` get wrapped. Chapters go to `chapters/NNN.html`, pages go to `pages/NNN.html`.
- **Done when**: All chapter/page files generated with correct nav links

#### T5: Generate landing page and TOC
- **Landing**: Book title from `--book-title`, cover image from `--cover-image` (optional), description from `--book-description`, links to TOC and first chapter
- **TOC**: Generated from manifest — chapter titles with page ranges, links to chapter files
- **Done when**: `index.html` and `toc.html` exist with correct content

#### T6: Copy images
- **Logic**: Find source `images/` dir from manifest, copy all images to `site/images/`
- **HTML fixup**: Update `<img src="images/...">` paths in extracted content to point to `../images/...` (chapters are in `chapters/` subdir)
- **Done when**: All images accessible from chapter pages

#### T7: Handle frontmatter / non-chapter pages
- **Logic**: Manifest rows with `kind="page"` go to `pages/NNN.html`
- **Navigation**: Same prev/next pattern as chapters
- **Done when**: Frontmatter pages rendered in `pages/` directory

#### T8: Wire into Onward recipe
- **File**: `configs/recipes/recipe-onward-images-html-mvp.yaml`
- **Change**: Append new stage after `build_chapters`
- **Done when**: Recipe includes `build_book_site_v1` as final stage

#### T9: Write pytest tests
- **File**: `tests/test_build_book_site.py`
- **Tests**: HTML5 structure, CSS file exists, responsive meta tag, navigation links, TOC content, image paths, self-contained (no external URLs), CSS custom properties present
- **Done when**: Tests pass, lint clean

#### T10: Integration test via driver.py
- **Run**: `python driver.py --recipe recipe-onward-images-html-mvp.yaml --start-from build_site`
- **Verify**: `output/runs/<run_id>/<ordinal>_build_book_site_v1/site/` exists with correct structure
- **Done when**: Site files generated in run output directory

#### T11: Self-contained copy test
- **Test**: Copy `site/` to `/tmp/test-site/`, open `index.html` — everything works
- **Done when**: No broken links, images, or CSS

#### T12: Extensive browser visual testing (chrome automation)
Multi-pass browser evaluation using chrome automation tools. Each page type tested at multiple viewports. GIF recordings of key interactions for evidence.

**Pass 1 — Landing page evaluation (desktop 1280px)**:
- Open `index.html` in Chrome
- Evaluate: visual hierarchy, typography, whitespace, cover image display
- Check: links to TOC and first chapter work
- Record GIF of landing page

**Pass 2 — TOC page evaluation (desktop)**:
- Navigate to `toc.html`
- Evaluate: chapter list readability, page range display, link styling
- Click through to a chapter — verify navigation works

**Pass 3 — Chapter page evaluation (desktop)**:
- Open a text-heavy chapter (prose readability)
- Evaluate: line length (~70ch measure), line-height, heading hierarchy, paragraph spacing
- Open a table-heavy chapter (genealogy tables)
- Evaluate: table borders, header distinction, column alignment, cell padding
- Open a chapter with images
- Evaluate: figure display, caption styling, image sizing, alt text presence
- Check prev/next navigation on multiple chapters
- Record GIF of chapter navigation flow

**Pass 4 — Mobile viewport testing (375px width)**:
- Resize to iPhone viewport (375x812)
- Test landing page: readable, no horizontal scroll, touch-friendly links
- Test TOC: items not cramped, tappable
- Test chapter with tables: horizontal scroll on table (not page), table still readable
- Test chapter with images: images scale to viewport, no overflow
- Test navigation: prev/next links usable on mobile
- Record GIF of mobile experience

**Pass 5 — Tablet viewport testing (768px width)**:
- Resize to iPad viewport (768x1024)
- Verify intermediate layout works — not too wide, not too cramped
- Test tables and images at this breakpoint

**Pass 6 — Typography and elegance audit**:
- Read a full chapter as a reader would — is it comfortable?
- Check: font choice feels "book-like", not "web-app-like"
- Check: headings have clear hierarchy without being oversized
- Check: sufficient contrast (text vs background)
- Check: links are distinguishable but not garish
- Check: navigation is unobtrusive — doesn't distract from reading
- Check: figures/captions feel integrated, not bolted on
- Check: tables feel like reference material, not spreadsheets

**Pass 7 — Edge cases and stress testing**:
- Frontmatter pages (short content) — doesn't look broken with minimal content
- Very long chapter — no layout issues at length
- Chapter with multiple consecutive images — stacking looks good
- Chapter with wide tables — horizontal scroll works, doesn't break page

**Pass 8 — Cross-page consistency**:
- Navigate through 5+ pages — consistent look and feel throughout
- Header/footer/nav identical on every page
- No CSS glitches on any page type

**Defect loop**: After each pass, if visual issues found:
1. Document the issue (screenshot/GIF + description)
2. Fix the CSS or template
3. Re-generate the site
4. Re-test the specific issue
5. Repeat until the page looks right

- **Done when**: All 8 passes completed with no outstanding visual issues. GIF evidence recorded for key flows.

#### T13: Document config parameters
- **Where**: module.yaml notes + story work log
- **Done when**: All params documented

### Impact Analysis
- **Downstream**: None — this is the terminal stage
- **Upstream**: Read-only dependency on `build_chapter_html_v1` output
- **Risk**: Low — additive module, no changes to existing code
- **Schema**: No changes to `schemas.py`
- **Tests**: No existing tests affected

### Open Questions Resolution
- **Landing page description**: Include it — configurable via `--book-description` param, optional
- **Search feature**: No — downstream customization (story says "No JS required")
- **Image lightbox**: No — JS progressive enhancement, not in scope for MVP

## Work Log
