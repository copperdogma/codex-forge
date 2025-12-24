#!/usr/bin/env python3
"""
Extract section text from HTML blocks using section boundaries.
Outputs enriched_portion_v1 with raw_text suitable for downstream choice extraction.
"""
import argparse
import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from modules.common.utils import read_jsonl, save_jsonl, ProgressLogger


TEXT_BLOCKS = {"p", "li", "dd", "dt", "td", "th"}
STRUCTURAL_TAGS = {"table", "thead", "tbody", "tr", "ol", "ul", "dl"}

# Generic endmatter patterns (not book-specific)
ENDMATTER_RUNNING_HEAD_PATTERNS = [
    r"more\s+fighting\s+fantasy",
    r"also\s+(?:available|in)",  # Matches "also available" or "also in"
    r"coming\s+soon",
    r"further\s+adventures?",
]

def _is_endmatter_running_head(block: Dict[str, Any]) -> bool:
    """Detect running heads that indicate endmatter (series ads, book lists)."""
    if block.get("block_type") != "p":
        return False
    cls = (block.get("attrs") or {}).get("class")
    if cls != "running-head":
        return False
    text = (block.get("text") or "").strip().lower()
    for pattern in ENDMATTER_RUNNING_HEAD_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


def _is_book_title_header(block: Dict[str, Any]) -> bool:
    """Detect headers that look like book titles (numbered list format)."""
    block_type = block.get("block_type")
    if block_type not in {"h1", "h2"}:
        return False
    text = (block.get("text") or "").strip()
    # Pattern: "N. BOOK TITLE" where N is a number (typically 1-50 for book lists)
    # Must be all caps or title case to distinguish from gameplay sections
    if re.match(r"^\d{1,2}\.\s+[A-Z][A-Z\s\-:]+$", text):
        return True
    return False


def _is_author_name_line(block: Dict[str, Any]) -> bool:
    """Detect author name patterns (typically follow book titles)."""
    if block.get("block_type") != "p":
        return False
    text = (block.get("text") or "").strip()
    # Pattern: "Firstname Lastname" or "Name and Name" or "By Name"
    # Typically short lines with proper case (not all caps, not lowercase)
    if not text or len(text) > 60:  # Author names are typically short
        return False
    # Check for author-like patterns
    if re.match(r"^(?:By\s+)?[A-Z][a-z]+(?:\s+(?:and\s+)?[A-Z][a-z]+)+$", text):
        return True
    return False


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


def _section_sort_key(section_id: str) -> Tuple[int, Any]:
    if section_id.lower() == "background":
        return (0, 0)
    if section_id.isdigit():
        return (1, int(section_id))
    return (2, section_id)


def build_elements(pages: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, int], Dict[int, str]]:
    elements: List[Dict[str, Any]] = []
    id_to_index: Dict[str, int] = {}
    page_to_image: Dict[int, str] = {}

    for page in pages:
        page_number = _coerce_int(page.get("page_number"))
        if page_number is None:
            continue
        image = page.get("image")
        if image:
            page_to_image[page_number] = image
        blocks = page.get("blocks") or []
        for block in blocks:
            order = block.get("order") or 0
            element_id = f"p{page_number:03d}-b{order}"
            elem = {
                "element_id": element_id,
                "page_number": page_number,
                "original_page_number": page.get("original_page_number"),
                "spread_side": page.get("spread_side"),
                "block_type": block.get("block_type"),
                "text": block.get("text") or "",
                "attrs": block.get("attrs"),
                "order": order,
            }
            id_to_index[element_id] = len(elements)
            elements.append(elem)

    elements.sort(key=lambda e: (e["page_number"], e["order"]))
    id_to_index = {e["element_id"]: idx for idx, e in enumerate(elements)}
    return elements, id_to_index, page_to_image


def _skip_block(block: Dict[str, Any], skip_running_heads: bool, skip_page_numbers: bool, skip_endmatter: bool = False) -> bool:
    block_type = block.get("block_type")
    if not block_type:
        return True
    if block_type.startswith("/"):
        return False

    # Generic endmatter filtering (applies to all FF books)
    if skip_endmatter:
        if _is_endmatter_running_head(block):
            return True
        if _is_book_title_header(block):
            return True
        if _is_author_name_line(block):
            return True

    if block_type in {"h1", "h2"}:
        return True
    if block_type == "img":
        return True
    if block_type == "p":
        cls = (block.get("attrs") or {}).get("class")
        if skip_running_heads and cls == "running-head":
            return True
        if skip_page_numbers and cls == "page-number":
            return True
        text = (block.get("text") or "").strip()
        order_val = _coerce_int(block.get("order"))
        if skip_running_heads and order_val == 1 and re.match(r"^\d{1,3}[-–]\d{1,3}$", text):
            return True
    return False


def _assemble_text(span: List[Dict[str, Any]], skip_running_heads: bool, skip_page_numbers: bool, skip_endmatter: bool = False) -> str:
    parts: List[str] = []
    for b in span:
        if _skip_block(b, skip_running_heads, skip_page_numbers, skip_endmatter):
            continue
        if b.get("block_type") not in TEXT_BLOCKS:
            continue
        text = (b.get("text") or "").strip()
        if not text:
            continue
        parts.append(text)
    raw = "\n".join(parts).strip()
    raw = re.sub(r"\n{3,}", "\n\n", raw)
    return raw


def _format_attrs(block: Dict[str, Any]) -> str:
    attrs = block.get("attrs") or {}
    if not attrs:
        return ""
    if "class" in attrs and attrs["class"]:
        return f' class="{attrs["class"]}"'
    return ""


def _assemble_html(span: List[Dict[str, Any]], skip_running_heads: bool, skip_page_numbers: bool, skip_endmatter: bool = False) -> str:
    parts: List[str] = []
    for b in span:
        block_type = b.get("block_type")
        if not block_type:
            continue
        text = (b.get("text") or "").strip()

        # Apply endmatter filtering first (most specific)
        if skip_endmatter:
            if _is_endmatter_running_head(b):
                continue
            if _is_book_title_header(b):
                continue
            if _is_author_name_line(b):
                continue

        # Apply legacy running head/page number filtering
        if (skip_running_heads or skip_page_numbers) and block_type == "p":
            cls = (b.get("attrs") or {}).get("class")
            if skip_running_heads and cls == "running-head":
                continue
            if skip_page_numbers and cls == "page-number":
                continue
            order_val = _coerce_int(b.get("order"))
            if skip_running_heads and order_val == 1 and re.match(r"^\d{1,3}[-–]\d{1,3}$", text):
                continue

        if block_type.startswith("/"):
            parts.append(f"</{block_type[1:]}>")
            continue

        if block_type in STRUCTURAL_TAGS:
            attrs = _format_attrs(b)
            parts.append(f"<{block_type}{attrs}>")
            if text:
                parts.append(text)
            continue

        if block_type in {"caption", "th", "td"}:
            attrs = _format_attrs(b)
            parts.append(f"<{block_type}{attrs}>")
            if text:
                parts.append(text)
            continue

        if block_type == "img":
            alt = (b.get("attrs") or {}).get("alt") or text
            parts.append(f"<img alt=\"{alt}\">")
            continue

        if block_type in {"p", "li", "dd", "dt", "h1", "h2"}:
            attrs = _format_attrs(b)
            parts.append(f"<{block_type}{attrs}>")
            if text:
                parts.append(text)
            continue

    return "\n".join(parts).strip()


def load_boundaries(path: str) -> List[Dict[str, Any]]:
    return [row for row in read_jsonl(path)]


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract section text from HTML blocks.")
    parser.add_argument("--pages", help="page_html_blocks_v1 JSONL path")
    parser.add_argument("--inputs", nargs="*", help="Driver-provided inputs")
    parser.add_argument("--boundaries", help="section boundaries JSONL path")
    parser.add_argument("--out", required=True, help="Output JSONL path")
    parser.add_argument("--skip-running-heads", dest="skip_running_heads", action="store_true")
    parser.add_argument("--skip_running_heads", dest="skip_running_heads", action="store_true")
    parser.add_argument("--keep-running-heads", dest="skip_running_heads", action="store_false")
    parser.add_argument("--keep_running_heads", dest="skip_running_heads", action="store_false")
    parser.set_defaults(skip_running_heads=True)
    parser.add_argument("--skip-page-numbers", dest="skip_page_numbers", action="store_true")
    parser.add_argument("--skip_page_numbers", dest="skip_page_numbers", action="store_true")
    parser.add_argument("--keep-page-numbers", dest="skip_page_numbers", action="store_false")
    parser.add_argument("--keep_page_numbers", dest="skip_page_numbers", action="store_false")
    parser.set_defaults(skip_page_numbers=True)
    parser.add_argument("--skip-endmatter", dest="skip_endmatter", action="store_true", help="Filter out endmatter patterns (book ads, titles, author names)")
    parser.add_argument("--skip_endmatter", dest="skip_endmatter", action="store_true")
    parser.add_argument("--keep-endmatter", dest="skip_endmatter", action="store_false")
    parser.add_argument("--keep_endmatter", dest="skip_endmatter", action="store_false")
    parser.set_defaults(skip_endmatter=True)
    parser.add_argument("--min-section", dest="min_section", type=int, default=None)
    parser.add_argument("--min_section", dest="min_section", type=int, default=None)
    parser.add_argument("--max-section", dest="max_section", type=int, default=None)
    parser.add_argument("--max_section", dest="max_section", type=int, default=None)
    parser.add_argument("--emit-raw-text", dest="emit_raw_text", action="store_true")
    parser.add_argument("--emit_raw_text", dest="emit_raw_text", action="store_true")
    parser.add_argument("--drop-raw-text", dest="emit_raw_text", action="store_false")
    parser.add_argument("--drop_raw_text", dest="emit_raw_text", action="store_false")
    parser.set_defaults(emit_raw_text=False)
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

    boundaries_path = args.boundaries
    if not boundaries_path:
        raise SystemExit("Missing --boundaries")
    if not os.path.isabs(boundaries_path):
        boundaries_path = os.path.abspath(boundaries_path)
    if not os.path.exists(boundaries_path):
        raise SystemExit(f"Boundaries file not found: {boundaries_path}")

    pages = list(read_jsonl(pages_path))
    boundaries = load_boundaries(boundaries_path)

    elements, id_to_index, page_to_image = build_elements(pages)
    if not elements:
        raise SystemExit("No HTML blocks found to extract")

    boundaries_sorted = sorted(boundaries, key=lambda b: _section_sort_key(str(b.get("section_id") or "")))

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    logger.log(
        "portionize",
        "running",
        current=0,
        total=len(boundaries_sorted),
        message="Extracting HTML sections",
        artifact=args.out,
        module_id="portionize_html_extract_v1",
        schema_version="enriched_portion_v1",
    )

    out_rows: List[Dict[str, Any]] = []
    skipped = 0
    for idx, b in enumerate(boundaries_sorted, start=1):
        section_id = b.get("section_id")
        start_id = b.get("start_element_id")
        if not start_id or start_id not in id_to_index:
            skipped += 1
            continue
        start_idx = id_to_index[start_id]
        end_id = b.get("end_element_id")
        end_idx = id_to_index.get(end_id, len(elements)) if end_id else len(elements)

        span = elements[start_idx:end_idx]
        raw_text = _assemble_text(span, args.skip_running_heads, args.skip_page_numbers, args.skip_endmatter) if args.emit_raw_text else ""

        page_numbers = [e["page_number"] for e in span if e.get("page_number") is not None]
        if page_numbers:
            page_start = min(page_numbers)
            page_end = max(page_numbers)
        else:
            page_start = _coerce_int(b.get("start_page")) or 0
            page_end = _coerce_int(b.get("end_page")) or page_start

        page_start_original = None
        page_end_original = None
        original_numbers = [e.get("original_page_number") for e in span if e.get("original_page_number") is not None]
        if original_numbers:
            page_start_original = min(original_numbers)
            page_end_original = max(original_numbers)

        source_images = []
        for pn in range(page_start, page_end + 1):
            img = page_to_image.get(pn)
            if img and img not in source_images:
                source_images.append(img)

        raw_html = _assemble_html(span, False, False, args.skip_endmatter)
        out_rows.append({
            "schema_version": "enriched_portion_v1",
            "module_id": "portionize_html_extract_v1",
            "run_id": args.run_id,
            "portion_id": str(section_id),
            "section_id": str(section_id),
            "page_start": page_start,
            "page_end": page_end,
            "page_start_original": page_start_original,
            "page_end_original": page_end_original,
            "confidence": b.get("confidence", 0.0),
            "raw_text": raw_text,
            "raw_html": raw_html,
            "element_ids": [e["element_id"] for e in span],
            "source_images": source_images,
            "macro_section": b.get("macro_section"),
        })

        logger.log(
            "portionize",
            "running",
            current=idx,
            total=len(boundaries_sorted),
            message=f"Extracted section {section_id}",
            artifact=args.out,
            module_id="portionize_html_extract_v1",
            schema_version="enriched_portion_v1",
        )

    save_jsonl(args.out, out_rows)
    summary_msg = f"Extracted {len(out_rows)} sections (skipped {skipped} of {len(boundaries_sorted)} boundaries)"
    logger.log(
        "portionize_html",
        "done",
        current=len(out_rows),
        total=len(out_rows),
        message=summary_msg,
        artifact=args.out,
        module_id="portionize_html_extract_v1",
        schema_version="enriched_portion_v1",
        extra={"summary_metrics": {"portions_created_count": len(out_rows), "sections_extracted_count": len(out_rows), "boundaries_skipped": skipped, "boundaries_total": len(boundaries_sorted)}},
    )
    print(f"[summary] portionize_html_extract_v1: {summary_msg}")


if __name__ == "__main__":
    main()
