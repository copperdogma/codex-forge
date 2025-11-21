# Story: Portionization with priors & overlaps

**Status**: Done

---

## Acceptance Criteria
- Sliding-window LLM emits spans with type/title/confidence/continuation hints
- Accepts priors to mark continuations
- Uses clean_text/raw_text fallback; multimodal images
- Append-only hypotheses JSONL

## Tasks
- [ ] Add prior ingestion
- [ ] Window/stride CLI
- [ ] Continuation fields
- [ ] Range filtering & append

## Notes
- 

## Work Log
- 20251121-0002 — Portionize supports priors, continuation hints, window/stride, range filtering, multimodal, append-only hypotheses
- Pending