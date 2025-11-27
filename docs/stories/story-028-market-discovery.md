# Story: Market Discovery for codex-forge

**Status**: In Progress

---

## Acceptance Criteria
- Surface at least four active communities or channels where document/OCR/LLM pipeline users congregate.
- Capture evidence of recent (≤12 months) interest or pain points that align with codex-forge capabilities.
- Propose concrete posting angles and next steps for outreach (what to share, where, and why it’s relevant).
- Log research sources and decisions in the work log.

## Tasks
- [x] Scan public forums and discussion hubs for adjacent projects and active threads.
- [x] Summarize signals of interest/pain that codex-forge can address.
- [ ] Draft tailored outreach posts (per channel) and get review.
- [ ] Pilot one post and collect engagement/feedback metrics.

## Findings (Nov 2025 scan)
- **DIYBookScanner forum** remains active with thousands of posts and recent activity (Aug–Sep 2025); software and R&D sections discuss OCR tooling and layout detection, suggesting a niche of power users who already scan books and need better pipelines. citeturn0search0
- **Reddit /r/deeplearning + /r/computervision** hosted April 2025 threads showcasing open-source OCR pipelines that emit structured Markdown/JSON for ML datasets; commenters requested features like vector extraction and gave positive feedback, indicating appetite for end-to-end, LLM-enhanced pipelines. citeturn1reddit12turn1reddit13
- **Reddit /r/ObsidianMD** July 2025 thread asks how to integrate Docling into personal knowledge workflows (RAG, Markdown export), showing demand from PKM users for cleaner structured outputs and automation hooks. citeturn1reddit20
- **Reddit /r/RAG** July 2025 thread reports long runtimes and quality issues when using Docling across formats, highlighting pain points (speed, image OCR quality) that codex-forge’s modular stages could address. citeturn1reddit18
- **Docling momentum**: the January 2025 Docling toolkit paper notes it hit ~10k GitHub stars and trended globally in Nov 2024, evidencing broad interest in open document-conversion stacks—an adjacent audience likely receptive to alternative pipelines. citeturn0academia14

## Where to Post + Angles
- **DIYBookScanner forum (Software / R&D)** — Frame as “end-to-end LLM-driven post-processing for DIY scans” with a short demo JSONL artifact and recipe; invite testers with messy page layouts.
- **Reddit /r/computervision and /r/deeplearning** — Position as a modular research pipeline for generating structured datasets (tables/math/layout) from scanned books; emphasize replaceable modules and validator; share a reproducible recipe.
- **Reddit /r/ObsidianMD** — Offer a how-to ingest PDFs→clean Markdown/JSON for vaults; include a minimal script wrapping `driver.py` + DocTags-to-Markdown converter.
- **Reddit /r/RAG** — Post a “faster-than-Docling for scans” benchmark note with profiling data; invite contributors to test on GPU/CPU and share traces.
- **Hacker News (Show HN)** — Once a polished recipe + sample run exists, post a Show HN highlighting modularity, JSONL artifacts, and validator; link to demo outputs (no binary assets).

## Immediate Next Steps
1) Produce a small public sample run (e.g., 10 pages from `input/06 deathtrap dungeon.pdf`) with artifacts in a temp share; redact content if needed.  
2) Draft channel-specific blurbs (100–150 words each) reusing the same artifact links.  
3) Time posts to avoid overlap; start with DIYBookScanner (highest relevance) then Reddit, then HN.

## Work Log
### 20251126-1200 — Community scan and opportunity mapping
- **Result:** Collected five active channels (DIYBookScanner, three Reddit niches, Docling momentum) with concrete pain/interest signals; mapped posting angles. No outreach launched yet.
- **Next:** Prepare demo artifact + tailored blurbs; schedule first post on DIYBookScanner forum.
