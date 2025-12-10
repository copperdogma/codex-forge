#!/usr/bin/env python3
"""
Reduce elements.jsonl into a compact per-page summary for macro classification
(frontmatter/gameplay/endmatter) suitable for a single LLM call.
"""

import argparse
import json
from pathlib import Path

from modules.common.utils import read_jsonl, save_json


def summarize_page(lines, page, max_lines=10, max_len=120):
    snippets = []
    numeric_flags = 0
    for ln in lines[:max_lines]:
        text = ln.get("text", "")
        if not text:
            continue
        if text.strip().isdigit():
            numeric_flags += 1
        if len(text) > max_len:
            text = text[:max_len] + "…"
        snippets.append(text)
    return {
        "page": page,
        "snippet_lines": snippets,
        "line_count": len(lines),
        "numeric_lines": numeric_flags,
    }


def main():
    ap = argparse.ArgumentParser(description="Reduce elements.jsonl to per-page macro summaries")
    ap.add_argument("--elements", required=True, help="elements.jsonl path")
    ap.add_argument("--out", required=True, help="macro_reduced.json")
    ap.add_argument("--max-lines", type=int, default=10)
    ap.add_argument("--max-len", type=int, default=120)
    args = ap.parse_args()

    pages = {}
    for row in read_jsonl(args.elements):
        pg = row.get("metadata", {}).get("page_number") or row.get("metadata", {}).get("page") or 0
        pages.setdefault(pg, []).append(row)

    summaries = []
    for pg in sorted(pages):
        summaries.append(summarize_page(pages[pg], pg, args.max_lines, args.max_len))

    save_json(args.out, {"schema_version": "macro_reduced_v1", "pages": summaries})
    print(f"Wrote {len(summaries)} page summaries -> {args.out}")


if __name__ == "__main__":
    main()
