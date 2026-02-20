/**
 * Basic crop quality validation prompt.
 * Simple pass/fail check for crop quality.
 */

const { buildMessages } = require("./_image-helpers");

const PROMPT_TEXT = `This is a cropped illustration extracted from a scanned book page. Evaluate whether the crop is good quality.

Return JSON: {"verdict": "pass" or "fail", "reason": "brief explanation"}

FAIL if ANY of these:
- The crop contains readable body text or captions that are NOT part of the image itself (e.g. italic captions below a photo, paragraph text, page numbers)
- More than 10% of the crop area is blank/white space with no image content
- The image subject appears obviously cut off at an edge (e.g. people missing half their body, objects clearly truncated)

PASS if:
- The crop tightly contains a photograph, illustration, drawing, logo, seal, plaque, or other graphic
- Text that is PART of the image (engraved on plaques, printed on logos, written on signs) is fine
- Minor white padding around the edges is acceptable

Return ONLY valid JSON, no other text.`;

module.exports = function (context) {
  const { vars, provider } = context;
  return buildMessages(PROMPT_TEXT, vars.image, provider?.id || "");
};
