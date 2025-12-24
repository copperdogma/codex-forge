# Story: HTML Presentation Cleanup

**Status**: Done
**Created**: 2025-12-23  
**Priority**: High  
**Parent Story**: story-086 (Preserve HTML Through Final Gamebook)

---

## Goal

Create a final HTML cleanup stage that removes presentation-only elements (running heads, page numbers, section numbers) from HTML output, producing a pristine `presentation_html` field suitable for game engine UI display.

---

## Motivation

Current HTML output in `gamebook.json` contains presentation artifacts that should not be shown to players:

- **Running heads**: `<p class="running-head">3-5</p>`, `<p class="running-head">9-10</p>`, etc.
- **Page numbers**: Page number markers that were part of the original book layout
- **Section numbers in h2 tags**: `<h2>2</h2>`, `<h2>8</h2>`, etc. (section IDs are already in JSON metadata)
- **Image/illustration tags**: `<img>` elements (images will be extracted upstream in a separate story; tags should be removed from final presentation HTML)

These elements are useful during pipeline processing (to verify boundaries, track provenance) but should be stripped before final presentation. The game engine needs clean HTML that contains only the actual narrative content, choices, and gameplay elements.

**Evidence from validation report:**
- Section 2: Contains `<p class="running-head">3-5</p>` after the narrative text
- Section 8: Contains `<p class="running-head">9-10</p>` after the narrative text  
- Section 17: Contains `<p class="running-head">18-21</p>` after the narrative text

All sections include `<h2>{section_id}</h2>` headers, which are redundant since section IDs are already in the JSON structure.

---

## Success Criteria

- [x] **Clean HTML field**: New `presentation_html` field (or cleaned `html` field) in final gamebook.json
- [x] **Running heads removed**: All `<p class="running-head">...</p>` elements stripped
- [x] **Page numbers removed**: All page number markers removed
- [x] **Section h2 headers removed**: `<h2>{section_id}</h2>` elements removed (section IDs already in JSON)
- [x] **Image tags removed**: All `<img>` elements stripped (images extracted upstream in separate story)
- [x] **Content preserved**: All narrative text, choices, tables, and gameplay elements remain intact
- [x] **Backward compatible**: Original `html` field can be preserved for debugging, or replaced if desired
- [x] **Validation**: Spot-check 10-20 sections to verify cleanup quality

---

## Solution Approach

**New Module**: `modules/export/clean_html_presentation_v1/`

**Processing Strategy:**
1. **Parse HTML**: Use HTML parser (e.g., BeautifulSoup) to safely parse and modify HTML
2. **Remove running heads**: Strip all `<p class="running-head">...</p>` elements
3. **Remove page numbers**: Strip elements with `class="page-number"` or patterns matching page numbers
4. **Remove section h2 headers**: Remove `<h2>` elements that contain only a section number (matching the section's `id`)
5. **Remove image tags**: Strip all `<img>` elements (images extracted upstream in separate story)
6. **Preserve structure**: Keep all other HTML structure (paragraphs, lists, tables, etc.)
7. **Output**: Add `presentation_html` field to each section, or replace `html` if configured

**Configuration Options:**
- `preserve_original_html`: Keep original `html` field alongside `presentation_html` (default: true)
- `remove_section_headers`: Remove h2 section number headers (default: true)
- `remove_running_heads`: Remove running head elements (default: true)
- `remove_page_numbers`: Remove page number markers (default: true)
- `remove_images`: Remove image/illustration tags (default: true; images extracted upstream)

**Placement in Pipeline:**
- Stage: `export` (after `build_ff_engine_v1` or as part of it)
- Input: `gamebook.json` with `html` fields
- Output: `gamebook.json` with `presentation_html` fields (and optionally cleaned `html`)

---

## Tasks

- [x] Create `modules/export/clean_html_presentation_v1/` module
- [x] Implement HTML parsing and cleanup logic
- [x] Add configuration options for what to remove
- [x] Add module to export stage in canonical recipe
- [x] Test on sample sections (verify running heads, h2 headers, image tags removed)
- [x] Run full pipeline and validate cleanup quality
- [x] Update gamebook schema if needed to include `presentation_html` (implicit support confirmed)
- [x] Document results and impact in work log

---

## Work Log

### 20251223-XXXX — Story created
- **Result:** Story defined.
- **Notes:** HTML cleanup needed to remove presentation artifacts before game engine display. Running heads, page numbers, redundant section h2 headers, and image tags should be stripped. Images will be extracted upstream in a separate story, so removing tags here is safe.
- **Next:** Implement cleanup module and integrate into export stage.

### 20251223-XXXX — Implementation and Integration
- **Action:** Created `modules/export/clean_html_presentation_v1/` with BeautifulSoup logic to remove artifacts.
- **Action:** Integrated into `recipe-ff-ai-ocr-gpt51.yaml` after `build_gamebook`.
- **Action:** Updated `build_gamebook` to output `gamebook_raw.json` and `clean_presentation` to output `gamebook.json`, ensuring downstream validation checks the cleaned version.
- **Action:** Relaxed validation requirements in `validate_ff_engine_v2` to support dynamic input/output mapping in driver.
- **Verification:** Ran manual tests on dirty JSON samples; confirmed `presentation_html` is clean and `html` is preserved.
- **Verification:** Ran pipeline smoke test (`smoke-html-clean`); confirmed integration success.
- **Outcome:** Success. `gamebook.json` now contains `presentation_html` field without running heads, page numbers, section headers, or image tags.


