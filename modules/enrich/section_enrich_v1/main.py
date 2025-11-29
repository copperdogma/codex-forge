import argparse
import os
import re
from typing import List, Dict, Any
from collections import defaultdict

from modules.common.utils import read_jsonl, append_jsonl, ensure_dir
from schemas import EnrichedPortion

SECTION_RE = re.compile(r"^\s*(\d{1,4})\b")
TARGET_RE = re.compile(r"\b(?:turn|go)\s+to\s+(\d{1,4})\b", re.IGNORECASE)


def elements_to_pages_dict(elements: List[Dict]) -> Dict[int, Dict]:
    """Convert elements.jsonl to page-based dict."""
    pages_dict = defaultdict(list)
    for elem in elements:
        page_num = elem.get("metadata", {}).get("page_number", 1)
        pages_dict[page_num].append(elem)

    # Sort and concatenate
    def sort_key(elem):
        sequence = elem.get("_codex", {}).get("sequence")
        if sequence is not None:
            return (0, sequence)
        coords = elem.get("metadata", {}).get("coordinates", {})
        points = coords.get("points", [])
        if points:
            ys = [p[1] for p in points]
            xs = [p[0] for p in points]
            return (1, min(ys), min(xs))
        return (2, 0)

    pages = {}
    for page_num in sorted(pages_dict.keys()):
        page_elements = sorted(pages_dict[page_num], key=sort_key)
        content_elements = [
            e for e in page_elements
            if e.get("type") not in ("Header", "Footer", "PageBreak")
        ]
        text_parts = [e.get("text", "").strip() for e in content_elements if e.get("text", "").strip()]
        page_text = "\n\n".join(text_parts)
        pages[page_num] = {
            "page": page_num,
            "text": page_text,
            "clean_text": page_text,
            "raw_text": page_text,
        }
    return pages


def load_pages(path: str) -> Dict[int, Dict]:
    """Load pages from elements.jsonl or legacy pages format."""
    raw_data = list(read_jsonl(path))
    if not raw_data:
        return {}

    # Detect format
    first = raw_data[0]
    is_elements = "type" in first and "metadata" in first

    if is_elements:
        return elements_to_pages_dict(raw_data)
    else:
        return {p["page"]: p for p in raw_data}


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
    parser.add_argument("--pages", required=True, help="elements.jsonl or legacy pages_clean JSONL")
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
        # If portion_id looks like a normalized section ID (S001, S002, etc.), extract number
        # Or if it's already numeric, use it directly
        portion_id = portion.get("portion_id")
        section_id = detect_section_id(raw_text)
        
        # Try to extract numeric ID from portion_id
        if not section_id and portion_id:
            # Check if it's normalized format like "S001" or "S123"
            import re
            norm_match = re.match(r'^S(\d+)$', str(portion_id).strip())
            if norm_match:
                section_id = norm_match.group(1)
            # Or if it's already numeric
            elif str(portion_id).strip().isdigit():
                section_id = str(portion_id).strip()
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
