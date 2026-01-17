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
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from modules.common.utils import read_jsonl, save_jsonl, ProgressLogger
from modules.common.macro_section import macro_section_for_page


_DUPLICATE_SIMILARITY_THRESHOLD = 0.9


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


def _normalize_body_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def _body_text_from_blocks(blocks: List[Dict[str, Any]]) -> str:
    if not blocks:
        return ""
    parts: List[str] = []
    for block in blocks:
        if _block_is_body_text(block):
            parts.append(block.get("text") or "")
    body = _normalize_body_text(" ".join(parts))
    if len(body) > 800:
        body = body[:800]
    return body


def _text_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    # Lightweight similarity: token overlap ratio (Jaccard).
    a_tokens = set(a.split())
    b_tokens = set(b.split())
    if not a_tokens or not b_tokens:
        return 0.0
    inter = len(a_tokens & b_tokens)
    union = len(a_tokens | b_tokens)
    return inter / max(1, union)


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
                     require_text_between: bool, include_background: bool) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []

    for page in pages:
        page_number = _coerce_int(page.get("page_number"))
        if page_number is None:
            continue
        spread_side = page.get("spread_side")
        blocks = page.get("blocks") or []

        # Optional: detect BACKGROUND as a special, unnumbered gameplay header
        if include_background:
            for idx, block in enumerate(blocks):
                block_type = block.get("block_type")
                text = (block.get("text") or "").strip()
                
                # Check if this is BACKGROUND header
                # The actual BACKGROUND on page 27 appears as a p block with class="running-head" (OCR artifact)
                # Since pages are already filtered to gameplay pages (27+), any "BACKGROUND" here is the real header
                is_background_header = False
                if text.lower() == "background":
                    # Accept h1 or h2 headers
                    if block_type == "h1" or block_type == "h2":
                        is_background_header = True
                    # Also accept p blocks if they're early in page (first 5 blocks)
                    # Even if they have running-head class - on gameplay pages, this is the actual section header
                    elif block_type == "p" and idx < 5:  # Early in page
                        # Exclude if it's part of a TOC entry (TOC entries have page numbers like "BACKGROUND24")
                        # Standalone "BACKGROUND" (1-2 words) on gameplay pages is the real header
                        if len(text.split()) <= 2 and not text.isdigit():
                            is_background_header = True
                
                if not is_background_header:
                    continue
                
                # score body text until next header
                span_blocks = blocks[idx + 1:]
                follow_text_score = 0
                has_body_text = False
                for b in span_blocks:
                    if b.get("block_type") in {"h1", "h2"}:
                        break
                    if _block_is_body_text(b):
                        has_body_text = True
                        follow_text_score += min(200, len((b.get("text") or "")))
                if require_text_between and not has_body_text:
                    continue
                element_id = f"p{page_number:03d}-b{blocks[idx].get('order')}"
                candidates.append({
                    "section_id": "background",
                    "start_element_id": element_id,
                    "start_page": page_number,
                    "start_line_idx": blocks[idx].get("order"),
                    "start_element_metadata": {
                        "spread_side": spread_side,
                        "block_type": block_type,
                    },
                    "confidence": 0.9,
                    "method": "code_filter",
                    "source": f"html_{block_type}_background",
                    "follow_text_score": follow_text_score,
                })
                break

        # If BACKGROUND is missing and this page is early, check for narrative content
        # We'll defer BACKGROUND creation until after we've seen all pages,
        # so we can ensure it comes before the first numeric section

        # Build local list of numeric header indices for this page (dedupe same-number repeats per page)
        header_indices = []
        seen_section_nums = set()
        for idx, block in enumerate(blocks):
            if block.get("block_type") != "h2":
                continue
            text = (block.get("text") or "").strip()
            if not text.isdigit():
                continue
            section_num = int(text)
            if not (min_section <= section_num <= max_section):
                continue
            if section_num in seen_section_nums:
                continue
            seen_section_nums.add(section_num)
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

            body_text = _body_text_from_blocks(span_blocks)
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
                "body_text": body_text,
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
        max_score = max(i.get("follow_text_score", 0) for i in items)
        # Prefer the earliest plausible header if it has comparable body text.
        candidates_top = [
            i for i in items
            if i.get("follow_text_score", 0) >= (max_score - 50)
        ]
        candidates_top.sort(key=lambda x: (
            _coerce_int(x.get("start_page")) or 0,
            _coerce_int(x.get("start_line_idx")) or 0,
            -x.get("follow_text_score", 0),
        ))
        deduped.append(candidates_top[0])
    return deduped


def _build_duplicate_report(candidates: List[Dict[str, Any]], deduped: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_section: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for c in candidates:
        by_section[c["section_id"]].append(c)
    chosen_map = {c.get("section_id"): c for c in deduped}
    duplicates: List[Dict[str, Any]] = []
    for section_id, items in by_section.items():
        if len(items) <= 1:
            continue
        chosen = chosen_map.get(section_id)
        items_sorted = sorted(items, key=lambda x: (
            _coerce_int(x.get("start_page")) or 0,
            _coerce_int(x.get("start_line_idx")) or 0,
        ))
        chosen_idx = None
        for idx, item in enumerate(items_sorted):
            if chosen and item.get("start_element_id") == chosen.get("start_element_id"):
                chosen_idx = idx
                break
        max_score = max(i.get("follow_text_score", 0) for i in items)
        similarity = None
        chosen_body = _normalize_body_text(chosen.get("body_text") or "") if chosen else ""
        if chosen_body:
            scores = []
            for item in items_sorted:
                other_body = _normalize_body_text(item.get("body_text") or "")
                if other_body:
                    scores.append(_text_similarity(chosen_body, other_body))
            if scores:
                similarity = max(scores)
        likely_duplicate_scan = bool(similarity is not None and similarity >= _DUPLICATE_SIMILARITY_THRESHOLD)
        duplicates.append({
            "section_id": section_id,
            "candidate_count": len(items),
            "chosen_start_page": chosen.get("start_page") if chosen else None,
            "chosen_start_line": chosen.get("start_line_idx") if chosen else None,
            "chosen_follow_text_score": chosen.get("follow_text_score") if chosen else None,
            "chosen_index_in_sorted": chosen_idx,
            "max_follow_text_score": max_score,
            "text_similarity": similarity,
            "likely_duplicate_scan": likely_duplicate_scan,
            "candidates": [
                {
                    "start_page": i.get("start_page"),
                    "start_line_idx": i.get("start_line_idx"),
                    "start_element_id": i.get("start_element_id"),
                    "follow_text_score": i.get("follow_text_score"),
                    "body_text_len": len(_normalize_body_text(i.get("body_text") or "")),
                }
                for i in items_sorted
            ],
        })
    return duplicates


def _write_duplicate_report(out_path: str, duplicates: List[Dict[str, Any]]) -> Optional[str]:
    out_dir = os.path.dirname(out_path)
    report_path = os.path.join(out_dir, "duplicate_headers.json")
    if not duplicates:
        if os.path.exists(report_path):
            os.remove(report_path)
        return None
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({
            "schema_version": "duplicate_header_report_v1",
            "duplicate_headers": duplicates,
        }, f, indent=2)
    return report_path


def apply_macro_section(boundaries: List[Dict[str, Any]], coarse: Optional[Dict[str, Any]]) -> None:
    if not coarse:
        return
    for b in boundaries:
        page = b.get("start_page")
        b["macro_section"] = macro_section_for_page(page, coarse)


def _section_sort_key(section_id: str) -> Tuple[int, Any]:
    if section_id.lower() == "background":
        return (0, 0)
    if section_id.isdigit():
        return (1, int(section_id))
    return (2, section_id)

def _doc_order_key(boundary: Dict[str, Any]) -> Tuple[int, int, Tuple[int, Any]]:
    start_page = _coerce_int(boundary.get("start_page")) or 0
    start_line = _coerce_int(boundary.get("start_line_idx")) or 0
    return (start_page, start_line, _section_sort_key(str(boundary.get("section_id") or "")))

def build_boundaries(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # Compute spans in document order to avoid inverted boundaries when headers are out-of-order.
    ordered = sorted(candidates, key=_doc_order_key)
    for idx, b in enumerate(ordered):
        nxt = ordered[idx + 1] if idx + 1 < len(ordered) else None
        if nxt:
            b["end_element_id"] = nxt.get("start_element_id")
            b["end_page"] = nxt.get("start_page")
    # Return deterministically sorted by section id for stable outputs.
    return sorted(ordered, key=lambda b: _section_sort_key(str(b["section_id"])))


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
    parser.add_argument("--include-background", dest="include_background", action="store_true")
    parser.add_argument("--include_background", dest="include_background", action="store_true")
    parser.add_argument("--skip-background", dest="include_background", action="store_false")
    parser.add_argument("--skip_background", dest="include_background", action="store_false")
    parser.set_defaults(include_background=True)
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

    # If BACKGROUND is requested but missing, try to infer it from narrative content before section 1
    if args.include_background:
        # First, check if BACKGROUND already exists in candidates
        # If not, we'll create it from narrative content before the first numeric section
        pass  # Logic moved to build_candidates to check during page iteration

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
    candidates = build_candidates(pages, args.min_section, args.max_section, args.require_text_between, args.include_background)
    
    # If BACKGROUND is requested but missing, try to find it by looking for the explicit "BACKGROUND" header
    # on the first gameplay page (coarse segmentation should have filtered to gameplay pages only)
    if args.include_background:
        background_candidates = [c for c in candidates if str(c.get("section_id", "")).lower() == "background"]
        if not background_candidates and pages:
            # Find the first gameplay page and look for explicit "BACKGROUND" header (h1 or h2)
            first_gameplay_page = None
            for page in pages:
                page_num = _coerce_int(page.get("page_number"))
                if page_num is not None:
                    first_gameplay_page = page
                    break
            
            if first_gameplay_page:
                page_number = _coerce_int(first_gameplay_page.get("page_number"))
                blocks = first_gameplay_page.get("blocks", [])
                
                # Look for explicit "BACKGROUND" header (h1, h2, or p block early in page)
                # On gameplay pages, even p blocks with running-head class are valid (OCR artifact)
                for idx, block in enumerate(blocks[:10]):  # Check first 10 blocks
                    block_type = block.get("block_type")
                    text = (block.get("text") or "").strip()
                    
                    # Accept h1, h2, or p blocks (early in page) with exact text "BACKGROUND"
                    if text.lower() == "background":
                        if block_type == "h1" or block_type == "h2":
                            # Found explicit BACKGROUND header - create candidate
                            spread_side = first_gameplay_page.get("spread_side")
                            element_id = f"p{page_number:03d}-b{block.get('order')}"
                            candidates.insert(0, {  # Insert at beginning so it comes before section 1
                                "section_id": "background",
                                "start_element_id": element_id,
                                "start_page": page_number,
                                "start_line_idx": block.get("order"),
                                "start_element_metadata": {
                                    "spread_side": spread_side,
                                    "block_type": block_type,
                                },
                                "confidence": 0.9,
                                "method": "code_filter",
                                "source": f"html_{block_type}_background",
                                "follow_text_score": 0,  # Will be calculated in build_boundaries
                            })
                            break
                        elif block_type == "p" and idx < 5:  # Early p block on gameplay page
                            # On gameplay pages, standalone "BACKGROUND" p block is the header
                            # (even if it has running-head class - that's an OCR artifact)
                            if len(text.split()) <= 2:  # Standalone, not part of TOC entry
                                spread_side = first_gameplay_page.get("spread_side")
                                element_id = f"p{page_number:03d}-b{block.get('order')}"
                                candidates.insert(0, {  # Insert at beginning so it comes before section 1
                                    "section_id": "background",
                                    "start_element_id": element_id,
                                    "start_page": page_number,
                                    "start_line_idx": block.get("order"),
                                    "start_element_metadata": {
                                        "spread_side": spread_side,
                                        "block_type": block_type,
                                    },
                                    "confidence": 0.9,
                                    "method": "code_filter",
                                    "source": f"html_{block_type}_background",
                                    "follow_text_score": 0,  # Will be calculated in build_boundaries
                                })
                                break
    
    deduped = dedupe_candidates(candidates)
    boundaries = build_boundaries(deduped)
    duplicates = _build_duplicate_report(candidates, deduped)
    duplicate_report_path = _write_duplicate_report(args.out, duplicates)
    ordering_violations = []
    for b in boundaries:
        start_page = _coerce_int(b.get("start_page"))
        end_page = _coerce_int(b.get("end_page"))
        if start_page is not None and end_page is not None and end_page < start_page:
            ordering_violations.append({
                "section_id": b.get("section_id"),
                "start_page": start_page,
                "end_page": end_page,
                "start_element_id": b.get("start_element_id"),
                "end_element_id": b.get("end_element_id"),
            })
    apply_macro_section(boundaries, coarse)

    save_jsonl(args.out, boundaries)
    summary_msg = (
        f"Boundaries: {len(boundaries)} (candidates {len(candidates)}, deduped {len(deduped)})"
    )
    if ordering_violations:
        summary_msg += f"; ordering_violations {len(ordering_violations)}"
    if duplicates:
        summary_msg += f"; duplicate_headers {len(duplicates)}"
    logger.log(
        "detect_boundaries_html",
        "done",
        current=len(boundaries),
        total=len(boundaries),
        message=summary_msg,
        artifact=args.out,
        module_id="detect_boundaries_html_v1",
        schema_version="section_boundary_v1",
        extra={"summary_metrics": {
            "boundaries_detected_count": len(boundaries),
            "candidates_count": len(candidates),
            "deduped_count": len(deduped),
            "duplicate_headers_count": len(duplicates),
            "duplicate_headers_report": duplicate_report_path,
        }},
    )
    print(f"[summary] detect_boundaries_html_v1: {summary_msg}")


if __name__ == "__main__":
    main()
