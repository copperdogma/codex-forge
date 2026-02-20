/**
 * Strict no-text crop validation prompt.
 * Zero tolerance for non-integral text in crops.
 */

const { buildMessages } = require("./_image-helpers");

const PROMPT_TEXT = `This cropped region was extracted from a scanned book page. It should contain ONLY a photograph, illustration, or graphic element.

Evaluate the crop and return JSON:
{
  "verdict": "pass" or "fail",
  "has_external_text": true or false,
  "blank_pct": estimated percentage of crop area that is blank/white (0-100),
  "is_complete": true or false,
  "reason": "brief explanation"
}

Definitions:
- "external text" = captions, body text, page numbers, or credit lines that are NOT part of the image content itself. Text engraved on plaques, printed on logos, or visible on signs within a photo is NOT external text.
- "blank" = large white/empty regions with no image content (beyond normal photo borders)
- "complete" = the image subject is not obviously cut off (no people missing body parts, no objects truncated)

FAIL if:
- has_external_text is true (readable captions or body text in the crop)
- blank_pct exceeds 15%
- is_complete is false

PASS only if this is a tight, clean crop of visual content with no external text.

Return ONLY valid JSON.`;

module.exports = function (context) {
  const { vars, provider } = context;
  return buildMessages(PROMPT_TEXT, vars.image, provider?.id || "");
};
