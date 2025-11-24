import argparse
import json
from typing import Dict, List

from modules.common.utils import read_jsonl, save_json, ProgressLogger


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
    parser.add_argument("--progress-file", help="Path to pipeline_events.jsonl")
    parser.add_argument("--state-file", help="Path to pipeline_state.json")
    parser.add_argument("--run-id", help="Run identifier for logging")
    args = parser.parse_args()

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    pages = load_pages(args.pages)
    portions = list(read_jsonl(args.portions))

    logger.log("build", "running", current=0, total=len(portions),
               message="Assembling portions", artifact=args.out)
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
            "continuation_of": p.get("continuation_of"),
            "continuation_confidence": p.get("continuation_confidence"),
            "source_images": images,
            "raw_text": "\n\n".join(texts),
        }

    save_json(args.out, assembled)
    logger.log("build", "done", current=len(portions), total=len(portions),
               message=f"Build complete ({len(assembled)} portions)", artifact=args.out)
    print(f"Wrote {len(assembled)} portions → {args.out}")


if __name__ == "__main__":
    main()
