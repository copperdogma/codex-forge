/**
 * Caption-focused crop validation prompt.
 * Primary concern: does the crop include external page captions/text?
 * Secondary: is there excessive blank space?
 * Deliberately ignores photographic composition issues.
 */

const { buildMessages } = require("./_image-helpers");

const PROMPT_TEXT = `This cropped image was extracted from a scanned book page. Your ONLY job is to check for two specific problems.

Return JSON: {"verdict": "pass" or "fail", "has_page_text": true or false, "excessive_blank": true or false, "reason": "brief explanation"}

CHECK 1 — PAGE TEXT (has_page_text):
Does the crop contain text that came from the BOOK PAGE rather than from within the image itself?
- Page captions (italic text describing a photo, usually below it)
- Body paragraph text from the page
- Headers or subheaders from the page
- Page numbers (large/prominent ones, not faint corner numbers)
These are crop errors — the text should have been excluded.

NOT page text (these are fine):
- Text engraved on plaques, monuments, signs, or gravestones
- Text printed on logos, seals, or certificates
- Handwritten text on old photographs (names, dates, annotations)
- Text visible on signs, banners, or documents within a photograph
- Faint, tiny page numbers at the very corner/edge

CHECK 2 — EXCESSIVE BLANK (excessive_blank):
Is more than 40% of the crop completely empty white space with zero image content?
This does NOT include:
- White backgrounds in drawings or sketches
- Sky or light backgrounds in photographs
- White corners around oval/round portrait photos
- Normal photo borders or margins

FAIL if has_page_text is true OR excessive_blank is true.
PASS otherwise. When uncertain, PASS.

Return ONLY valid JSON.`;

module.exports = function (context) {
  const { vars, provider } = context;
  return buildMessages(PROMPT_TEXT, vars.image, provider?.id || "");
};
