# Runbook: Deep Research for ADRs

Multi-provider AI research process for architecture decisions and other hard-to-reverse technical choices.

Use this when an ADR or decision spike needs evidence that goes beyond repo-local context.

## When To Use

- an ADR is `PENDING` or `RESEARCHING` and needs external evidence;
- a story needs a genuine option comparison, not just local code inspection;
- the topic is AI-heavy or fast-moving enough that training-data recall is not trustworthy;
- the team needs a reconciled recommendation across multiple providers, not one model's opinion.

Do not use this for routine repo exploration. Use `/scout` or normal code inspection first.

## Prerequisites

- `deep-research` CLI installed and configured
- provider credentials available for the automated providers you plan to run
- a stand-alone research prompt written in the ADR's `research/research-prompt.md`
- a clear question with enough context that another model can reason without extra repo history

## Provider Matrix

| Provider | Deep research path | Recommended use |
|---|---|---|
| OpenAI | Automated via `deep-research run --mode deep --provider openai` | Always include for current API/model research and general synthesis quality |
| Google (Gemini) | Automated via `deep-research run --mode deep --provider google` | Always include for long-context search-grounded research |
| Anthropic (Claude / Opus) | Manual via the Claude app | Use manual deep research and paste the result into `opus-research-stub.md` |
| xAI (Grok) | Manual via the Grok app | Use manual deep research and paste the result into `xai-research-stub.md` |

Why manual for Anthropic and xAI: the app experiences can do search-grounded deep research that is not equivalent to a plain API call. If the API path is only a standard LLM call, do not treat it as a deep-research substitute.

## Research Folder Convention

Use the ADR-local `research/` folder:

```text
docs/decisions/adr-NNN-name/
  adr.md
  research/
    research-prompt.md
    openai-research-report.md
    gemini-research-report.md
    opus-research-stub.md
    xai-research-stub.md
    final-synthesis.md
```

Optional generated helper files such as `synthesis-prompt.md` are fine, but the six files above are the stable convention.

## Process

### 1. Write the research prompt

The research prompt is the main quality lever. It should stand on its own and be reusable across providers.

Strong prompts:

- state the exact repo and architectural context;
- break research into numbered questions;
- specify the output shape you want back;
- include important constraints, legacy decisions, and existing vendor relationships;
- ask for evidence, not vibes;
- include a date anchor such as "as of 2026-03-15" for any fast-moving AI or API topic.

When relevant, explicitly require:

- a canonical benchmark or common yardstick;
- feature compatibility matrices, not just quality/cost rankings;
- API constraints and limits;
- identification of recent entrants or releases from the last 1-3 months.

### 2. Create the manual-provider stubs first

Create the two manual handoff files in the ADR's `research/` directory before running automated providers:

- `opus-research-stub.md`
- `xai-research-stub.md`

If you use the `deep-research stub` helper and it emits provider-default file names, rename them into this repo's convention before continuing.

Always create both manual stubs when you expect Anthropic and xAI input. Do not wait until after OpenAI and Gemini finish.

### 3. Run automated providers separately

From the ADR's `research/` directory:

```bash
deep-research run --mode deep --provider openai
deep-research run --mode deep --provider google
```

Run providers one at a time. Passing multiple `--provider` flags in a single invocation has previously dropped providers silently.

Rename or capture the resulting reports into:

- `openai-research-report.md`
- `gemini-research-report.md`

Keep the repo naming stable even if the CLI uses a different default.

### 4. Fill the manual-provider stubs

Paste the Claude / Opus and xAI / Grok deep-research outputs into:

- `opus-research-stub.md`
- `xai-research-stub.md`

Preserve enough source citations or concrete claims that later synthesis can audit the reasoning.

### 5. Run synthesis

The synthesis step reconciles all provider reports into one direction.

Use the `research/` folder contents as inputs and save the result to `final-synthesis.md`.

The synthesis should:

1. grade each source report for evidence quality and specificity;
2. extract the core claims by topic;
3. identify agreements vs disagreements;
4. resolve contradictions with explicit reasoning, not majority vote;
5. separate high-confidence findings from open questions;
6. produce one concrete recommendation plus clear fallback cases;
7. flag benchmark mismatches, stale evidence, and hidden API constraints.

### 6. Discuss and decide

Research is input, not the decision.

After synthesis:

- update `adr.md` with a real `Research Summary`;
- move the ADR status forward (`RESEARCHING` or `DISCUSSING` as appropriate);
- capture human corrections and judgment in `Discussion`;
- record final choices in `Decisions`;
- if the direction materially changes stories, specs, build-map guidance, or guardrails, run `/align`.

## Recency Rules for AI Topics

Any research involving models, APIs, pricing, or vendor capabilities must explicitly bias toward recency.

- Anchor the prompt with the current date.
- Tell the model to prioritize official provider sources and very recent benchmarks.
- Treat information older than roughly three months as potentially stale unless the topic is stable.
- Ask the synthesis to call out stale claims explicitly.
- Ask providers to identify recent releases or new entrants.

## Guardrails

- Do not confuse plain API reasoning with search-grounded deep research.
- Keep provider runs separate for reliability and auditability.
- Keep prompts in the repo. They are decision evidence.
- Do not accept a synthesis that only aggregates opinions without reconciling conflicts.
- If the reports disagree because they used different benchmarks or incompatible assumptions, call that out instead of pretending the disagreement is resolved.

## Practical Notes

- OpenAI and Gemini are the default automated pair.
- Claude / Opus and xAI are manual but high-value cross-checks.
- If the prompt grows beyond roughly 150 lines, it is probably over-scoped. Split the research round.
- After the ADR direction stabilizes, distill recurring process lessons into a runbook, skill, or `AGENTS.md` update so future sessions do not rediscover them from scratch.
