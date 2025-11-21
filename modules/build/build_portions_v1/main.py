import argparse
import json
import sys
import pathlib
from typing import Dict, List

repo_root = pathlib.Path(__file__).resolve().parents[3]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from utils import read_jsonl, save_json


def load_pages(path: str) -> Dict[int, Dict]:
    pages = {}
    for p in read_jsonl(path):
        pages[p["page"]] = p
    return pages


def main():
    parser = argparse.ArgumentParser(description="Assemble resolved portions into a traceable JSON (raw text concat).")
    parser.add_argument("--pages", required=True, help="pages_raw.jsonl")
    parser.add_argument("--portions", required=True, help="portions_resolved.jsonl")
    parser.add_argument("--out", required=True, help="output JSON file")
    args = parser.parse_args()

    pages = load_pages(args.pages)
    portions = list(read_jsonl(args.portions))

    assembled = {}
    for p in portions:
        span_pages = [i for i in range(p["page_start"], p["page_end"] + 1)]
        texts = []
        images = []
        for i in span_pages:
            page = pages.get(i)
            if not page:
                continue
            page_text = page.get("clean_text") or page.get("text") or page.get("raw_text") or ""
            texts.append(f"[PAGE {i}]\n{page_text}")
            if page.get("image"):
                images.append(page["image"])
        assembled[p["portion_id"]] = {
            "portion_id": p["portion_id"],
            "page_start": p["page_start"],
            "page_end": p["page_end"],
            "title": p.get("title"),
            "type": p.get("type"),
            "confidence": p.get("confidence", 0),
            "orig_portion_id": p.get("orig_portion_id"),
            "source_images": images,
            "raw_text": "\n\n".join(texts),
        }

    save_json(args.out, assembled)
    print(f"Wrote {len(assembled)} portions → {args.out}")


if __name__ == "__main__":
    main()
