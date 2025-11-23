import argparse
import os
import sys
import re
from typing import List, Dict, Any

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from modules.common.utils import read_jsonl, append_jsonl, ensure_dir  # noqa: E402
from schemas import EnrichedPortion  # noqa: E402

SECTION_RE = re.compile(r"^\s*(\d{1,4})\b")
TARGET_RE = re.compile(r"\b(?:turn|go)\s+to\s+(\d{1,4})\b", re.IGNORECASE)


def load_pages(path: str) -> Dict[int, Dict]:
    return {p["page"]: p for p in read_jsonl(path)}


def extract_text(portion: Dict, pages: Dict[int, Dict], max_chars: int) -> str:
    parts = []
    for page in range(portion["page_start"], portion["page_end"] + 1):
        pg = pages.get(page)
        if not pg:
            continue
        txt = pg.get("clean_text") or pg.get("raw_text") or pg.get("text") or ""
        parts.append(txt)
    blob = "\n".join(parts)
    if len(blob) > max_chars:
        blob = blob[:max_chars]
    return blob


def detect_section_id(text: str) -> str:
    m = SECTION_RE.match(text or "")
    return m.group(1) if m else None


def detect_targets(text: str) -> List[str]:
    return list({m.group(1) for m in TARGET_RE.finditer(text or "")})


def main():
    parser = argparse.ArgumentParser(description="Add section_id and targets heuristically to portions.")
    parser.add_argument("--pages", required=True, help="pages_clean JSONL")
    parser.add_argument("--portions", required=True, help="resolved_portion JSONL")
    parser.add_argument("--out", required=True, help="Output enriched_portion JSONL")
    parser.add_argument("--max_chars", type=int, default=2000)
    parser.add_argument("--state-file", help="ignored")
    parser.add_argument("--progress-file", help="ignored")
    parser.add_argument("--run-id", help="Run identifier for stamping")
    args = parser.parse_args()

    pages = load_pages(args.pages)
    ensure_dir(os.path.dirname(args.out) or ".")

    for portion in read_jsonl(args.portions):
        raw_text = extract_text(portion, pages, args.max_chars)
        section_id = detect_section_id(raw_text)
        targets = detect_targets(raw_text)
        enriched = EnrichedPortion(
            portion_id=portion["portion_id"],
            section_id=section_id,
            page_start=portion["page_start"],
            page_end=portion["page_end"],
            title=portion.get("title"),
            type=portion.get("type"),
            confidence=portion.get("confidence", 0.0),
            source_images=portion.get("source_images") or [],
            raw_text=raw_text,
            choices=portion.get("choices") or [],
            combat=portion.get("combat"),
            test_luck=portion.get("test_luck"),
            item_effects=portion.get("item_effects") or [],
            targets=targets,
            module_id="section_enrich_v1",
            run_id=args.run_id,
        )
        append_jsonl(args.out, enriched.dict())
    print(f"Enriched sections → {args.out}")


if __name__ == "__main__":
    main()
