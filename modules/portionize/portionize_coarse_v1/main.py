import argparse
import json
import os
from typing import List, Dict

from openai import OpenAI
from tqdm import tqdm

from modules.common.utils import read_jsonl, append_jsonl, ensure_dir, ProgressLogger, log_llm_usage
from modules.common.macro_section import macro_section_for_page
from schemas import PortionHypothesis

SYSTEM_PROMPT = """You are a coarse-grained book segmenter.
Input: a larger ordered batch of pages (text + optional images) and optional locked portions that touch them.
Goals:
- Prefer long spans (chapters/acts/sections) rather than fine-grained fragments.
- Merge adjacent pages into a single portion when they clearly belong together.
- Indicate continuation_of when a span obviously continues an earlier portion from the provided priors.
- If a span starts/ends mid-page, still report page_start/page_end and mention this in notes.
Output JSON: { "portions": [ { "portion_id": str|null, "page_start": int, "page_end": int, "title": str|null, "type": str|null, "confidence": float (0-1), "notes": str|null, "continuation_of": str|null, "continuation_confidence": float|null } ] }
Return only the JSON."""


def window_iter(pages: List[Dict], window: int, stride: int):
    n = len(pages)
    i = 0
    while i < n:
        batch = pages[i:i + window]
        yield batch
        i += stride


def call_llm(client: OpenAI, model: str, batch: List[Dict], priors: List[Dict]) -> List[Dict]:
    content = []
    for p in batch:
        page_text = p.get("clean_text") or p.get("text") or p.get("raw_text") or ""
        content.append({"type": "text", "text": f"[PAGE {p['page']}]\n{page_text}"})
        if p.get("image_b64"):
            content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{p['image_b64']}"}})
    if priors:
        prior_txt = json.dumps(priors, ensure_ascii=False)
        content.append({"type": "text", "text": "Prior locked portions near these pages:\n" + prior_txt})
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content}
        ],
        response_format={"type": "json_object"}
    )
    usage = getattr(completion, "usage", None)
    pt = getattr(usage, "prompt_tokens", None)
    ct = getattr(usage, "completion_tokens", None)
    if pt is None or ct is None:
        pt = pt or 0
        ct = ct or 0
    log_llm_usage(
        model=model,
        prompt_tokens=pt,
        completion_tokens=ct,
        request_ms=None,
    )
    payload = json.loads(completion.choices[0].message.content)
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for k in ("portions", "spans", "data"):
            if k in payload and isinstance(payload[k], list):
                return payload[k]
    return []


def main():
    parser = argparse.ArgumentParser(description="Coarse large-window portion hypotheses generator.")
    parser.add_argument("--pages", required=True, help="Path to pages_raw.jsonl or pages_clean.jsonl.")
    parser.add_argument("--out", required=True, help="Path to window_hypotheses_coarse.jsonl (append).")
    parser.add_argument("--window", type=int, default=16)
    parser.add_argument("--stride", type=int, default=6)
    parser.add_argument("--pstart", type=int, help="First page to include (1-based).")
    parser.add_argument("--pend", type=int, help="Last page to include (inclusive).")
    parser.add_argument("--model", default="gpt-4.1-mini")
    parser.add_argument("--boost_model", default="gpt-5", help="Optional higher-tier model for retries on empty/low-confidence outputs.")
    parser.add_argument("--prior", help="Optional portions_locked_normalized.jsonl to give prior spans for continuation hints.")
    parser.add_argument("--progress-file", help="Path to pipeline_events.jsonl")
    parser.add_argument("--state-file", help="Path to pipeline_state.json")
    parser.add_argument("--run-id", help="Run identifier for logging")
    parser.add_argument("--coarse-segments", "--coarse_segments", dest="coarse_segments",
                        help="Optional coarse_segments.json or merged_segments.json for macro_section tagging")
    args = parser.parse_args()

    pages = list(read_jsonl(args.pages))
    if args.pstart or args.pend:
        ps = args.pstart or pages[0]["page"]
        pe = args.pend or pages[-1]["page"]
        pages = [p for p in pages if ps <= p["page"] <= pe]
    if not pages:
        raise SystemExit("No pages to process after applying range filter.")

    from base64 import b64encode
    for p in pages:
        if "image" in p and p["image"] and os.path.exists(p["image"]):
            if "image_b64" not in p:
                with open(p["image"], "rb") as f:
                    p["image_b64"] = b64encode(f.read()).decode("utf-8")

    client = OpenAI()
    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    out_dir = os.path.dirname(args.out)
    if out_dir:
        ensure_dir(out_dir)

    min_page = pages[0]["page"]
    max_page = pages[-1]["page"]

    coarse_segments = None
    if args.coarse_segments:
        try:
            with open(args.coarse_segments, "r", encoding="utf-8") as f:
                coarse_segments = json.load(f)
        except Exception:
            coarse_segments = None

    priors_all = []
    if args.prior:
        priors_all = list(read_jsonl(args.prior))

    windows = list(window_iter(pages, args.window, args.stride))
    total = len(windows)
    for idx, batch in enumerate(tqdm(windows, desc="Coarse windows"), start=1):
        try:
            batch_pages = set([p["page"] for p in batch])
            priors = [p for p in priors_all if (p.get("page_start") and p.get("page_end") and
                                                (set(range(p["page_start"], p["page_end"] + 1)) & batch_pages))]

            spans = call_llm(client, args.model, batch, priors)
            if not spans and args.boost_model:
                spans = call_llm(client, args.boost_model, batch, priors)

            page_nums = [p["page"] for p in batch]
            for span in spans:
                if span["page_start"] < min_page or span["page_end"] > max_page:
                    continue
                hypo = PortionHypothesis(
                    portion_id=span.get("portion_id"),
                    page_start=span["page_start"],
                    page_end=span["page_end"],
                    title=span.get("title"),
                    type=span.get("type"),
                    confidence=span.get("confidence", 0.45),
                    notes=span.get("notes"),
                    continuation_of=span.get("continuation_of"),
                    continuation_confidence=span.get("continuation_confidence"),
                    source_window=page_nums,
                    source_pages=list(range(span["page_start"], span["page_end"] + 1)),
                    macro_section=macro_section_for_page(span["page_start"], coarse_segments),
                    source=["coarse"],
                )
                append_jsonl(args.out, hypo.dict())
            logger.log("portionize", "running", current=idx, total=total,
                       message=f"Coarse window {idx}/{total} pages {min(batch_pages)}-{max(batch_pages)}",
                       artifact=args.out, module_id="portionize_coarse_v1")
        except Exception as e:
            append_jsonl(args.out, {"error": str(e), "batch_pages": [p["page"] for p in batch]})
            logger.log("portionize", "running", current=idx, total=total,
                       message=f"Error on window {idx}: {e}", artifact=args.out, module_id="portionize_coarse_v1")

    logger.log("portionize", "done", current=total, total=total,
               message="Coarse portionize complete", artifact=args.out, module_id="portionize_coarse_v1")


if __name__ == "__main__":
    main()
