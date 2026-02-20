# Story 130: Book Website Template Module

**Status**: To Do

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

## Work Log
