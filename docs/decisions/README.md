# ADRs

Architecture Decision Records live here.

## Naming

Use one directory per ADR:

```text
docs/decisions/adr-NNN-short-name/
```

Inside each ADR directory:

```text
adr.md
research/research-prompt.md
research/final-synthesis.md
```

## Statuses

- `PENDING`
- `RESEARCHING`
- `DISCUSSING`
- `ACCEPTED`
- `REJECTED`
- `DEFERRED`
- `SUPERSEDED`

## Usage

- Create a new ADR with `/create-adr`
- Follow `docs/runbooks/adr-creation.md` for lifecycle and integration
- Use `docs/runbooks/deep-research.md` when an ADR needs multi-provider external research
- Use `/align` after major ADR decisions or implementation outcomes to surface downstream doc, story, build-map, and eval impacts
- Cross-link ADRs from stories via `Decision Refs` when they affect implementation
