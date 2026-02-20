# Story 129: Onward HTML Output Polish

**Status**: To Do

---
**Depends On**: story-128 (table fidelity verification — tables must be correct before polishing)
**Blocks**: story-130 (book website template)

## Goal
Transform the Onward pipeline's HTML output from bare fragments into proper, well-structured HTML5 documents — a solid base that any downstream tool (website template, ebook converter, static site generator) can trivially consume.

The output should be **clean, semantic, and self-contained** — something you can open in a browser and read comfortably with zero additional tooling.

## Current State
The `build_chapter_html_v1` module produces:
- **Bare HTML fragments** — no `<!DOCTYPE>`, no `<html>`, `<head>`, or `<body>` tags
- **No CSS** — renders in browser defaults (Times New Roman, no table borders, etc.)
- **Minimal navigation** — just an "Index" back-link at the top of each chapter
- **No semantic structure** — everything is `<p>` tags, no `<article>`, `<nav>`, `<figure>`
- **No metadata** — no charset, viewport, title, or author
- **Tables are structurally valid** but lack captions, scope attributes, and visual styling
- **Images have alt text** and correct relative paths, but no `<figure>`/`<figcaption>` wrapper

## Acceptance Criteria
- [ ] **Valid HTML5**: Every output file has `<!DOCTYPE html>`, `<html lang="en">`, `<head>` (charset, viewport, title), and `<body>`.
- [ ] **Embedded CSS**: A clean, minimal stylesheet is included (inline or linked) that makes the output readable in any browser. Typography, table borders/padding, responsive images, max-width container.
- [ ] **Semantic structure**: Chapters wrapped in `<article>`, navigation in `<nav>`, images in `<figure>` with `<figcaption>` where captions exist.
- [ ] **Chapter navigation**: Each chapter has prev/next links in addition to the index back-link.
- [ ] **Table accessibility**: `<th>` elements have `scope` attributes. Tables have a visual distinction (borders, alternating rows, or similar).
- [ ] **Index page is useful**: Shows book title, chapter list with page ranges, and links. Not just a bare `<ul>`.
- [ ] **Print-friendly**: Output looks reasonable when printed or saved as PDF (no broken tables, images sized appropriately).
- [ ] **Generic module**: The build module improvements work for any book, not just Onward. Book title and metadata come from recipe/config parameters.
- [ ] **Self-contained**: The `output/html/` directory can be copied anywhere and opened directly — no external dependencies.

## Approach
Modify `build_chapter_html_v1` (or create a `build_chapter_html_v2` if changes are too extensive) to emit proper HTML5 documents. Keep it simple:

1. **HTML5 wrapper**: Add document structure to every emitted file.
2. **Embedded `<style>` block**: A minimal, tasteful CSS reset + book-reading styles. No external CSS file needed (keeps output self-contained).
3. **Semantic upgrades**: Wrap content in `<article>`, images in `<figure>`, navigation in `<nav>`.
4. **Navigation**: Generate prev/next links from the chapter manifest.
5. **Index enhancement**: Add book title (from config), chapter list with printed page ranges.
6. **Table styling**: CSS for borders, padding, header distinction. Add `scope` to `<th>` in the BeautifulSoup post-processing.
7. **Responsive basics**: Viewport meta, `max-width` container, `img { max-width: 100% }`.

## Non-Negotiables
- **No JavaScript**: Pure HTML + CSS. The output is a static document, not an app.
- **No external dependencies**: No CDN fonts, no framework CSS, no build tools. Everything is inline or relative.
- **No content changes**: This story is purely structural/presentational. Text, tables, and images remain exactly as they are from the pipeline.
- **Generic**: All improvements must be parameterized (book title, author, etc.) and work for any book processed by the pipeline.

## Tasks
- [ ] Add HTML5 document wrapper (doctype, html, head, body) to chapter and index output
- [ ] Design and embed a minimal CSS stylesheet (typography, tables, images, layout)
- [ ] Add `<meta charset>`, `<meta viewport>`, and `<title>` to every page
- [ ] Wrap chapter content in `<article>`, images in `<figure>`
- [ ] Add `<nav>` with prev/next chapter links
- [ ] Enhance index page (book title, chapter list with page ranges)
- [ ] Add `scope` attributes to table header cells
- [ ] Add CSS table styling (borders, padding, header distinction)
- [ ] Make images responsive (`max-width: 100%`, `height: auto`)
- [ ] Test: open output in browser, verify readability on desktop and mobile viewport
- [ ] Test: print to PDF, verify tables and images render cleanly
- [ ] Verify output is fully self-contained (copy `output/html/` to `/tmp`, open — everything works)

## Work Log
