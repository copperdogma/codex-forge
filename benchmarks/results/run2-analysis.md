# Image Crop Extraction Eval — Run 2 Analysis

**Date**: 2026-02-16
**Config**: 12 models × 3 prompts × 13 images = 468 API calls
**Duration**: ~22 minutes
**Overall**: 223 passed, 245 failed, 0 errors (47.65%)

## Overall Leaderboard (by average score)

| Rank | Model          | Best Prompt     | Avg Score | Pass Rate |
|------|----------------|-----------------|-----------|-----------|
| 1    | Gemini 3 Pro   | baseline        | 0.856     | 77%       |
| 2    | Gemini 3 Pro   | two-step        | 0.798     | 69%       |
| 3    | Gemini 2.5 Pro | baseline        | 0.793     | 77%       |
| 4    | Gemini 3 Flash | baseline        | 0.746     | 69%       |
| 5    | GPT-5.2        | strict-exclude  | 0.740     | 62%       |
| 6    | Claude Opus 4.6| strict-exclude  | 0.726     | 62%       |

## Model Rankings (avg across all prompts)

| Model              | Avg Score | Avg Pass Rate |
|--------------------|-----------|---------------|
| Gemini 3 Pro       | 0.785     | 69%           |
| Claude Opus 4.6    | 0.704     | 62%           |
| GPT-5.2            | 0.700     | 56%           |
| GPT-4.1 Mini       | 0.643     | 46%           |
| Claude Sonnet 4.5  | 0.627     | 54%           |
| GPT-5 Mini         | 0.625     | 54%           |
| GPT-5              | 0.594     | 38%           |
| Gemini 2.5 Pro     | 0.593     | 51%           |
| GPT-5.1            | 0.589     | 38%           |
| Gemini 2.5 Flash   | 0.582     | 44%           |
| Gemini 3 Flash     | 0.569     | 44%           |
| GPT-4.1            | 0.507     | 15%           |

## Image Difficulty

| Image    | Description                   | Pass Rate | Avg Score |
|----------|-------------------------------|-----------|-----------|
| Image126 | Memorial (cairn + plaque)     | 83%       | 0.748     |
| Image020 | Ranch (aerial + house)        | 78%       | 0.793     |
| Image121 | Reunion (group + 2 ovals)     | 72%       | 0.739     |
| Image008 | Introduction (couple)         | 69%       | 0.749     |
| Image003 | Credits (covered wagon)       | 67%       | 0.676     |
| Image124 | Illustration (ox-cart)        | 64%       | 0.738     |
| Image037 | Chapter (seated + oval)       | 42%       | 0.666     |
| Image013 | Chapter (portrait in text)    | 42%       | 0.589     |
| Image000 | Cover (full page)             | 36%       | 0.624     |
| Image059 | Chapter (couple + woman)      | 31%       | 0.625     |
| Image021 | Chapter (couple in text)      | 33%       | 0.577     |
| Image001 | Title page (decorative)       | 3%        | 0.215     |
| Image011 | Certificate (logo + seal)     | 0%        | 0.406     |

## Key Findings

1. **Gemini 3 Pro is the clear winner** — dominates all other models, especially with the
   baseline prompt. Scores >0.95 on 10 of 13 images.

2. **The baseline prompt is best for Gemini** — simpler instructions produce better results.
   The strict-exclude prompt actually hurts Gemini performance significantly.

3. **strict-exclude helps OpenAI and Claude** — GPT-5.2 and Claude Opus 4.6 both perform
   best with the strict-exclude prompt (more detailed rules about what to exclude).

4. **Claude Opus 4.6 is the most consistent** — identical 62% pass rate across all three
   prompts. Not the highest scorer but very reliable.

5. **Hard images** — Image011 (certificate) and Image001 (title page) are universally
   difficult. These may need specialized handling or different prompt strategies.

6. **Cost/speed vs quality trade-off**: Gemini 3 Flash at 0.746 with baseline is a strong
   budget option (presumably cheaper than Gemini 3 Pro).

## Recommendation

**Primary choice**: Gemini 3 Pro with baseline prompt
- Best overall score (0.856)
- Near-perfect on most images (>0.95 on 10/13)
- Only struggles with: full-page covers, decorative title pages, and certificate pages

**Fallback**: Consider a two-pass approach:
1. Primary: Gemini 3 Pro + baseline for most pages
2. Special handling for cover pages and certificate pages (which all models struggle with)
