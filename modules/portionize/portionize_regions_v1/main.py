import argparse
import json
import os
import re
from typing import List, Dict, Any

from openai import OpenAI

from modules.common.utils import ProgressLogger, read_jsonl, ensure_dir, save_json

SYSTEM_PROMPT = """You split Fighting Fantasy books into coarse regions.
Expected regions: frontmatter, rules (including character sheet), game, backmatter. Return tight page boundaries.
Input: short snippets per page (first lines only), already cleaned of page-number artifacts.
Return JSON only: {"regions": [{"type": "frontmatter|rules|game|backmatter", "start_page": int, "end_page": int, "confidence": 0-1}]}
Rules:
- Never overlap; keep order.
- If unsure, omit rather than guess.
- Prefer precise starts (first page where region clearly begins).
"""


def window_pages(pages: List[Dict[str, Any]], start_idx: int, size: int) -> List[Dict[str, Any]]:
    return pages[start_idx:start_idx + size]


PAGE_RE = re.compile(r"^\s*\d{1,3}[–-]\d{1,3}\s*")


def clean_snippet(text: str) -> str:
    # Drop leading page-number artifacts and duplicate footer fragments
    text = PAGE_RE.sub("", text)
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    # keep only first 3 lines
    lines = lines[:3]
    snippet = " ".join(lines)
    return snippet[:300]


def format_window(batch: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    content = []
    for p in batch:
        snippet = clean_snippet(p.get("clean_text") or p.get("raw_text") or "")
        content.append({"type": "text", "text": f"[PAGE {p['page']}] {snippet}"})
    return content


def call_llm(client: OpenAI, model: str, batch: List[Dict[str, Any]]):
    content = format_window(batch)
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
        response_format={"type": "json_object"},
    )
    try:
        return json.loads(resp.choices[0].message.content)
    except Exception:
        return {"regions": []}


def merge_regions(regions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    regions = [r for r in regions if r.get("start_page") is not None and r.get("end_page") is not None]
    regions.sort(key=lambda r: (-r.get("confidence", 0), r["start_page"], r["end_page"]))
    kept = []
    for r in regions:
        conflict = False
        for k in kept:
            if not (r["end_page"] < k["start_page"] or r["start_page"] > k["end_page"]):
                conflict = True
                break
        if not conflict:
            kept.append(r)
    kept.sort(key=lambda r: r["start_page"])
    return kept


def main():
    parser = argparse.ArgumentParser(description="Coarse region detector (frontmatter/rules/game/backmatter) over pagelines.")
    parser.add_argument("--pages", required=True, help="pages_clean.jsonl")
    parser.add_argument("--out", required=True, help="regions.json")
    parser.add_argument("--window", type=int, default=6)
    parser.add_argument("--stride", type=int, default=4)
    parser.add_argument("--model", default="gpt-5-nano")
    parser.add_argument("--progress-file")
    parser.add_argument("--state-file")
    parser.add_argument("--run-id")
    parser.add_argument("--skip-ai", action="store_true", help="Bypass region LLM and load stub regions.json")
    parser.add_argument("--stub", help="Stub regions.json to use when --skip-ai")
    args = parser.parse_args()

    if args.skip_ai:
        if not args.stub:
            raise SystemExit("--skip-ai set but no --stub provided for portionize_regions_v1")
        ensure_dir(os.path.dirname(args.out) or ".")
        data = json.load(open(args.stub, "r", encoding="utf-8"))
        save_json(args.out, data)
        print(f"[skip-ai] portionize_regions_v1 copied stub → {args.out}")
        return

    pages = list(read_jsonl(args.pages))
    pages.sort(key=lambda p: p.get("page", 0))
    windows = []
    i = 0
    while i < len(pages):
        windows.append((i, window_pages(pages, i, args.window)))
        i += args.stride

    client = OpenAI()
    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    ensure_dir(os.path.dirname(args.out) or ".")

    all_regions = []
    for idx, (start_idx, batch) in enumerate(windows, start=1):
        res = call_llm(client, args.model, batch)
        regs = res.get("regions", []) if isinstance(res, dict) else []
        all_regions.extend(regs)
        logger.log("portionize", "running", current=idx, total=len(windows),
                   message=f"window {idx}/{len(windows)} pages {batch[0]['page']}-{batch[-1]['page']}",
                   artifact=args.out, module_id="portionize_regions_v1")

    merged = merge_regions(all_regions)
    save_json(args.out, {"regions": merged, "model": args.model})
    logger.log("portionize", "done", current=len(windows), total=len(windows),
               message=f"regions: {len(merged)}", artifact=args.out,
               module_id="portionize_regions_v1")
    print(f"Saved regions {len(merged)} → {args.out}")


if __name__ == "__main__":
    main()
