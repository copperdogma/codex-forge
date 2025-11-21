# Story: Page cleaning module (multimodal)

**Status**: Done

---

## Acceptance Criteria
- LLM cleaning produces clean_text + confidence per page
- Falls back to raw_text if needed
- Supports image embedding and boost model when confidence low

## Tasks
- [ ] Add clean_pages.py
- [ ] Wire min_conf/boost flags
- [ ] Ensure image base64 inclusion
- [ ] Persist cleaned pages to JSONL

## Notes
- 

## Work Log
- 20251121-0001 — Added clean_pages.py (multimodal), min_conf + boost model, b64 images, produces pages_clean.jsonl
- Pending