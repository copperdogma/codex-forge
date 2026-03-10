const fs = require('fs');
const path = require('path');

module.exports = async function({ vars, provider }) {
  let imagePaths = [];
  if (vars.image_list) {
    imagePaths = vars.image_list.split(',').map(p => p.trim());
  } else if (vars.image_path) {
    imagePaths = [vars.image_path];
  }

  const systemPrompt = `You are an OCR engine for scanned book pages.

Return ONLY minimal HTML that preserves text and basic structure.

Allowed tags (only):
- Structural: <h1>, <h2>, <h3>, <p>, <dl>, <dt>, <dd>, <br>
- Emphasis: <strong>, <em>
- Lists: <ol>, <ul>, <li>
- Tables: <table>, <thead>, <tbody>, <tr>, <th>, <td>, <caption>
- Navigation: <a href="#123"> (use for explicit navigation choices like 'turn to 123')
- Running head / page number: <p class="running-head">, <p class="page-number">
- Images: <img alt="..." data-count="N"> (placeholder only, no src; N = number of distinct illustrations if multiple on page, default 1)
- Metadata: <meta name="ocr-metadata" data-ocr-quality="0.0-1.0" data-ocr-integrity="0.0-1.0" data-continuation-risk="0.0-1.0">

Rules:
- Preserve exact wording, punctuation, and numbers.
- Reflow paragraphs (no hard line breaks within a paragraph).
- Keep running heads and page numbers if present (use the classed <p> tags above).
- Tables must be represented as a single <table> with headers/rows (no splitting).
- If multiple images are provided, they are sequential pages of the SAME table. Output a SINGLE unified <table>.

Also include a single metadata tag as the FIRST line:
<meta name="ocr-metadata" data-ocr-quality="0.0-1.0" data-ocr-integrity="0.0-1.0" data-continuation-risk="0.0-1.0">

Output ONLY HTML, no Markdown, no code fences, no extra commentary.

Recipe hints:
This is a genealogy book.
Genealogy tables use a specific 6-column layout:
NAME | BORN | MARRIED | SPOUSE | BOY | GIRL | DIED

CRITICAL TABLE RULES:
1. Preserve the table structure exactly. Do not merge columns.
2. BOY and GIRL are separate columns. Do not merge them into "Children".
3. Dates often appear in the wrong column (e.g. death date in spouse column). Move them to the correct column if obvious, otherwise transcribe as seen.
4. Remarriages often appear on a second row with just MARRIED/SPOUSE populated.
5. Continuation lines (e.g. long spouse names) should be merged into the same cell if possible, or kept as a second row if ambiguous.`;

  const userText = 'Return HTML only. FIRST line MUST be: <meta name="ocr-metadata" data-ocr-quality="0.0-1.0" data-ocr-integrity="0.0-1.0" data-continuation-risk="0.0-1.0">';

  if (provider.id.startsWith('google')) {
    const parts = [
      { text: systemPrompt + "\n\n" + userText }
    ];
    for (const imgPath of imagePaths) {
      const resolvedPath = path.resolve(__dirname, imgPath);
      if (fs.existsSync(resolvedPath)) {
        const base64Image = fs.readFileSync(resolvedPath).toString('base64');
        parts.push({
          inlineData: {
            mimeType: 'image/jpeg',
            data: base64Image
          }
        });
      }
    }
    return JSON.stringify([
      {
        role: 'user',
        parts: parts
      }
    ]);
  }

  // OpenAI / Default
  const userContent = [
    { type: 'text', text: userText }
  ];

  for (const imgPath of imagePaths) {
    const resolvedPath = path.resolve(__dirname, imgPath);
    if (fs.existsSync(resolvedPath)) {
      const base64Image = fs.readFileSync(resolvedPath).toString('base64');
      userContent.push({
        type: 'image_url',
        image_url: { url: `data:image/jpeg;base64,${base64Image}` }
      });
    }
  }

  return JSON.stringify([
    { role: 'system', content: systemPrompt },
    { role: 'user', content: userContent }
  ]);
};
