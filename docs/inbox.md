# Codex Forge Inbox

This file captures ideas, insights, and potential architectural improvements discovered during development and manual tasks.

## Untriaged

- Row-structured fallback experiment for hard table pages: if the current HTML-first targeted rescue starts struggling again on reviewed genealogy-table pages, try a bounded experiment where the model emits row-oriented CSV/JSON with stable row ids first, then render HTML deterministically and compare row recall, ordering, and column fidelity against the current rescue path. Revisit trigger: repeated reviewed failures on Roseanna/Emilie-style pages or unstable model drift that the current acceptance checks cannot reliably control.
