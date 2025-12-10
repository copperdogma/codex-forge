You are summarizing the structure of a Fighting Fantasy gamebook.
Input: a JSON object with `pages`, where each entry has:
- page: page number (integer)
- snippet_lines: up to N short lines of text from that page
- line_count: total lines on the page
- numeric_lines: count of standalone numeric-looking lines

Task:
- Identify contiguous page ranges for:
  - frontmatter
  - gameplay_sections (the numbered gameplay content)
  - endmatter (appendix/back matter)
- If a region is absent, set it to null.
- Assume gameplay starts where the numbered sections begin; frontmatter precedes it; endmatter follows.

Output JSON:
{
  "frontmatter_pages": [start_page, end_page] or null,
  "gameplay_pages": [start_page, end_page] or null,
  "endmatter_pages": [start_page, end_page] or null,
  "notes": "brief rationale, citing distinguishing lines"
}
