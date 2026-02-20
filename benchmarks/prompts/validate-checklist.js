/**
 * Checklist-based crop validation prompt.
 * Structured scoring on multiple criteria.
 */

const { buildMessages } = require("./_image-helpers");

const PROMPT_TEXT = `Evaluate this cropped illustration from a scanned book page on four criteria. Score each 0-10.

1. COMPLETENESS (0-10): Is the image subject complete?
   - 10 = fully contained, nothing cut off
   - 5 = minor edge cropping but subject recognizable
   - 0 = major content obviously missing or truncated

2. TEXT_FREE (0-10): Is the crop free of EXTERNAL text?
   - 10 = no external text at all
   - 7 = text engraved/printed as part of the image (plaques, logos, signs) is acceptable
   - 3 = some caption or body text visible
   - 0 = significant body text or captions in the crop

3. TIGHTNESS (0-10): Is the crop tight around the content?
   - 10 = minimal padding, well-framed
   - 5 = some extra white space but acceptable
   - 0 = excessive blank/white areas (>25% of crop is empty)

4. CONTENT (0-10): Does this contain actual image content?
   - 10 = clear photograph, illustration, or graphic
   - 5 = image present but very small or low quality
   - 0 = mostly blank or text, not really an image

Return JSON:
{
  "completeness": 0-10,
  "text_free": 0-10,
  "tightness": 0-10,
  "content": 0-10,
  "verdict": "pass" or "fail",
  "reason": "brief explanation"
}

FAIL if any score is 3 or below. PASS if all scores are 5 or above.
If scores are mixed (some 4, rest above 5), use your judgment.

Return ONLY valid JSON.`;

module.exports = function (context) {
  const { vars, provider } = context;
  return buildMessages(PROMPT_TEXT, vars.image, provider?.id || "");
};
