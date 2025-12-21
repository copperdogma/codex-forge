#!/usr/bin/env python3
"""
Detect section boundaries from HTML block streams.

Legacy review notes (carry-overs from detect_boundaries_code_first_v1):
- Filter to gameplay pages using coarse_segments (avoid frontmatter false positives).
- Prefer true section headers with body text following (drop header-only spans).
- Deduplicate same section_id by picking the candidate with strongest follow-text score.
- Maintain sequential ordering and emit end_element_id as next header.
"""
import argparse
import json
import os
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from modules.common.utils import read_jsonl, save_jsonl, ProgressLogger
from modules.common.macro_section import macro_section_for_page


def _coerce_int(val: Any) -> Optional[int]:
    if isinstance(val, int):
        return val
    if val is None:
        return None
    digits = ""
    for ch in str(val):
        if ch.isdigit():
            digits += ch
        else:
            break
    if digits:
        return int(digits)
    return None


def _alpha_ratio(text: str) -> float:
    if not text:
        return 0.0
    letters = sum(1 for c in text if c.isalpha())
    return letters / max(1, len(text))


def _block_is_body_text(block: Dict[str, Any]) -> bool:
    block_type = block.get("block_type")
    if block_type in {"p", "li", "dd", "dt", "td", "th"}:
        text = (block.get("text") or "").strip()
        return len(text) >= 10 and _alpha_ratio(text) >= 0.3
    return False


def load_coarse_segments(path: Optional[str]) -> Optional[Dict[str, Any]]:
    if not path:
        return None
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def filter_pages_to_gameplay(pages: List[Dict[str, Any]], coarse: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not coarse:
        return pages
    gameplay = coarse.get("gameplay_pages") or []
    if not gameplay or len(gameplay) != 2:
        return pages
    start, end = gameplay
    start_num = _coerce_int(start)
    end_num = _coerce_int(end)
    if start_num is None or end_num is None:
        return pages
    return [p for p in pages if start_num <= _coerce_int(p.get("page_number")) <= end_num]


def build_candidates(pages: List[Dict[str, Any]], min_section: int, max_section: int,
                     require_text_between: bool) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []

    for page in pages:
        page_number = _coerce_int(page.get("page_number"))
        if page_number is None:
            continue
        spread_side = page.get("spread_side")
        blocks = page.get("blocks") or []

        # Build local list of header indices for this page
        header_indices = []
        for idx, block in enumerate(blocks):
            if block.get("block_type") != "h2":
                continue
            text = (block.get("text") or "").strip()
            if not text.isdigit():
                continue
            section_num = int(text)
            if not (min_section <= section_num <= max_section):
                continue
            header_indices.append((idx, section_num))

        for pos, section_num in header_indices:
            # score: look ahead for body text until next header
            next_header_pos = None
            for idx, _sec in header_indices:
                if idx > pos:
                    next_header_pos = idx
                    break
            span_blocks = blocks[pos + 1: next_header_pos] if next_header_pos else blocks[pos + 1:]
            follow_text_score = 0
            has_body_text = False
            for b in span_blocks:
                if b.get("block_type") == "h2":
                    break
                if _block_is_body_text(b):
                    has_body_text = True
                    follow_text_score += min(200, len((b.get("text") or "")))
            if require_text_between and not has_body_text:
                continue

            element_id = f"p{page_number:03d}-b{blocks[pos].get('order')}"
            candidates.append({
                "section_id": str(section_num),
                "start_element_id": element_id,
                "start_page": page_number,
                "start_line_idx": blocks[pos].get("order"),
                "start_element_metadata": {
                    "spread_side": spread_side,
                    "block_type": "h2",
                },
                "confidence": 0.95,
                "method": "code_filter",
                "source": "html_h2",
                "follow_text_score": follow_text_score,
            })

    return candidates


def dedupe_candidates(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_section: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for c in candidates:
        by_section[c["section_id"]].append(c)

    deduped: List[Dict[str, Any]] = []
    for section_id, items in by_section.items():
        if len(items) == 1:
            deduped.append(items[0])
            continue
        items.sort(key=lambda x: (x.get("follow_text_score", 0),
                                  -(_coerce_int(x.get("start_page")) or 0),
                                  -(x.get("start_line_idx") or 0)))
        deduped.append(items[-1])
    return deduped


def apply_macro_section(boundaries: List[Dict[str, Any]], coarse: Optional[Dict[str, Any]]) -> None:
    if not coarse:
        return
    for b in boundaries:
        page = b.get("start_page")
        b["macro_section"] = macro_section_for_page(page, coarse)


def build_boundaries(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    candidates.sort(key=lambda b: int(b["section_id"]))
    for idx, b in enumerate(candidates):
        nxt = candidates[idx + 1] if idx + 1 < len(candidates) else None
        if nxt:
            b["end_element_id"] = nxt.get("start_element_id")
            b["end_page"] = nxt.get("start_page")
    return candidates


def main() -> None:
    parser = argparse.ArgumentParser(description="Detect section boundaries from HTML blocks.", allow_abbrev=False)
    parser.add_argument("--pages", help="page_html_blocks_v1 JSONL path")
    parser.add_argument("--inputs", nargs="*", help="Driver-provided inputs")
    parser.add_argument("--out", required=True, help="Output JSONL for section boundaries")
    parser.add_argument("--coarse-segments", dest="coarse_segments", help="coarse_segments.json path")
    parser.add_argument("--min-section", dest="min_section", type=int, default=1)
    parser.add_argument("--min_section", dest="min_section", type=int, default=1)
    parser.add_argument("--max-section", dest="max_section", type=int, default=400)
    parser.add_argument("--max_section", dest="max_section", type=int, default=400)
    parser.add_argument("--require-text-between", dest="require_text_between", action="store_true")
    parser.add_argument("--require_text_between", dest="require_text_between", action="store_true")
    parser.add_argument("--allow-empty-between", dest="require_text_between", action="store_false")
    parser.add_argument("--allow_empty_between", dest="require_text_between", action="store_false")
    parser.set_defaults(require_text_between=True)
    parser.add_argument("--progress-file")
    parser.add_argument("--state-file")
    parser.add_argument("--run-id")
    args = parser.parse_args()

    pages_path = args.pages or (args.inputs[0] if args.inputs else None)
    if not pages_path:
        parser.error("Missing --pages (or --inputs) input")
    if not os.path.isabs(pages_path):
        pages_path = os.path.abspath(pages_path)
    if not os.path.exists(pages_path):
        raise SystemExit(f"Blocks file not found: {pages_path}")

    coarse = load_coarse_segments(args.coarse_segments)
    pages = list(read_jsonl(pages_path))

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    logger.log(
        "portionize",
        "running",
        current=0,
        total=len(pages),
        message="Detecting HTML section boundaries",
        artifact=args.out,
        module_id="detect_boundaries_html_v1",
        schema_version="section_boundary_v1",
    )

    pages = filter_pages_to_gameplay(pages, coarse)
    candidates = build_candidates(pages, args.min_section, args.max_section, args.require_text_between)
    deduped = dedupe_candidates(candidates)
    boundaries = build_boundaries(deduped)
    apply_macro_section(boundaries, coarse)

    save_jsonl(args.out, boundaries)
    logger.log(
        "portionize",
        "done",
        current=len(boundaries),
        total=len(boundaries),
        message=f"Detected {len(boundaries)} section boundaries",
        artifact=args.out,
        module_id="detect_boundaries_html_v1",
        schema_version="section_boundary_v1",
    )


if __name__ == "__main__":
    main()
