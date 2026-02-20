/**
 * Table-strict OCR prompt — emphasizes table structure preservation.
 */

const { buildMessages } = require("./_image-helpers");

const PROMPT_TEXT = `You are an OCR engine for scanned book pages from a genealogy / family history book.

Return ONLY minimal HTML that preserves text and basic structure.

CRITICAL: This book contains many TABLES with genealogical data (names, dates, spouses, etc.).
You MUST represent ALL tabular data using <table> elements with proper <tr>/<td> cells.
NEVER render table rows as flat <p> paragraphs.

Allowed tags (only):
- Structural: <h1>, <h2>, <h3>, <p>, <br>
- Emphasis: <strong>, <em>
- Tables: <table>, <thead>, <tbody>, <tr>, <th>, <td>
- Running head / page number: <p class="running-head">, <p class="page-number">
- Images: <img alt="...">

Table rules:
- Each table row must be a <tr> with separate <td> for each column.
- Column headers (NAME, BORN, MARRIED, SPOUSE, BOY/GIRL, DIED) go in <thead><tr><th>.
- Data rows go in <tbody>.
- If a table continues from the previous page, still use <table> with the visible data.
- Family sub-tables (just name + birth date) use 2-column tables.
- Main family tables (full 6 columns) use 6-column tables.
- Empty cells should be <td></td>, not omitted.

Other rules:
- Preserve exact wording, punctuation, and numbers.
- Running heads (generational context like "Alma's Grandchildren") use <p class="running-head">.
- Family section headings (like "RONALD'S FAMILY") use <h2>.
- Page numbers use <p class="page-number">.

Output ONLY HTML, no Markdown, no code fences, no extra commentary.`;

module.exports = function (context) {
  const { vars, provider } = context;
  return buildMessages(PROMPT_TEXT, vars.image, provider?.id || "");
};
