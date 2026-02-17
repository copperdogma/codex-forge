/**
 * Dummy prompt for layout models (Florence-2, Surya).
 * These models don't use text prompts — the provider scripts
 * extract the image from context.vars and run fixed inference.
 * This prompt just passes through the image variable.
 */

module.exports = function (context) {
  return [
    {
      role: "user",
      content: [{ type: "text", text: "Detect figure regions." }],
    },
  ];
};
