#!/usr/bin/env python3
"""
Deterministic gameplay header detector for Fighting Fantasy:
- Uses elements.jsonl (full elements, not reduced) and macro_sections.json hint.
- Within main_content range (from macro_sections), finds elements whose text is a standalone integer 1-400.
- Emits section_boundaries.jsonl (start_element_id; end inferred downstream).
"""

import argparse
import json
import os
import re
from itertools import product
from typing import Dict, List

from modules.common.utils import read_jsonl, save_jsonl, ensure_dir, ProgressLogger
from schemas import SectionBoundary


def load_macro_hint(path: str):
    if not path or not os.path.exists(path):
        return None
    try:
        return json.load(open(path))
    except Exception:
        return None


CHAR_OPTIONS = {
    # digit-like letters
    "o": ["0"], "O": ["0"],
    "l": ["1", "8"], "I": ["1"], "i": ["1"],
    "b": ["6", "8"], "B": ["8"],
    "g": ["9"], "q": ["9"],
    "s": ["5", "8"], "S": ["5", "8"],
    "z": ["2"],
    # punctuation/noise that should drop out
    ":": ["", "1", "2"], ".": [""], "'": [""], "`": [""], '"': [""],
    "-": [""], "–": [""], "—": [""],
    "%": ["", "2"],  # rare OCR swap for a 2
}


def expand_candidates(token: str, max_combos: int = 32) -> List[int]:
    """
    Generate plausible numeric ids from a short token containing digits/punct/OCR-misread letters.
    Returns unique integers within plausible length (1-3 digits).
    """
    options: List[List[str]] = []
    for ch in token:
        if ch.isdigit():
            options.append([ch])
        elif ch in CHAR_OPTIONS:
            options.append(CHAR_OPTIONS[ch])
        elif ch.isspace():
            continue
        else:
            return []
        # quick guard against explosion
        combo_est = 1
        for opt in options:
            combo_est *= len(opt)
        if combo_est > max_combos:
            return []

    combos = set()
    for parts in product(*options) if options else []:
        num_str = "".join(parts)
        if not num_str or len(num_str) > 3:
            continue
        if num_str.startswith("0"):
            continue
        combos.add(int(num_str))
    return sorted(combos)


def is_sentence_ending(text: str) -> bool:
    """Check if text ends with sentence punctuation."""
    if not text:
        return True  # Empty is considered sentence boundary
    text = text.strip()
    return text.endswith('.') or text.endswith('!') or text.endswith('?') or text.endswith(':')


def starts_new_sentence(text: str) -> bool:
    """Check if text starts with a capital letter (new sentence)."""
    if not text:
        return True  # Empty is considered sentence boundary
    text = text.strip()
    return text and text[0].isupper()


def validate_context(elem: Dict, all_elements: List[Dict], page: int) -> bool:
    """
    Validate that a candidate number is standalone (not embedded in sentence).
    Returns True if valid (standalone), False if embedded.
    """
    # Group elements by page and sort by element ID to get order
    page_elements = [e for e in all_elements 
                     if (e.get("metadata", {}).get("page_number") or e.get("page")) == page]
    page_elements.sort(key=lambda e: e.get("id", ""))
    
    # Find current element index
    try:
        current_idx = next(i for i, e in enumerate(page_elements) if e.get("id") == elem.get("id"))
    except StopIteration:
        return True  # Can't validate, allow it
    
    # Get previous element
    prev_elem = page_elements[current_idx - 1] if current_idx > 0 else None
    prev_text = (prev_elem.get("text") or "").strip() if prev_elem else ""
    
    # Get next element
    next_elem = page_elements[current_idx + 1] if current_idx < len(page_elements) - 1 else None
    next_text = (next_elem.get("text") or "").strip() if next_elem else ""
    
    # Validate: previous should end sentence OR be empty, next should start sentence OR be empty
    prev_valid = is_sentence_ending(prev_text) or not prev_text
    next_valid = starts_new_sentence(next_text) or not next_text
    
    # If both are valid, it's standalone
    if prev_valid and next_valid:
        return True
    
    # If previous doesn't end sentence AND next doesn't start sentence, it's embedded
    if not prev_valid and not next_valid:
        return False
    
    # Edge case: if one is valid but other isn't, be lenient (might be OCR corruption)
    # But if both are invalid, definitely reject
    return True  # Be lenient for edge cases


def check_centering(elem: Dict, pagelines_data: Dict, page: int) -> bool:
    """
    Check if element is centered using bbox data from pagelines.
    Uses RELATIVE centering: calculates centerpoint relative to average centerpoint
    of all text lines on the page. This handles skewed pages or offset bbox coordinates.
    Returns True if centered (relative to text body), False otherwise.
    """
    # Try to find pagelines data for this page
    page_data = None
    for p_data in pagelines_data.values():
        if p_data.get("page") == page:
            page_data = p_data
            break
    
    if not page_data:
        return False  # Can't check without bbox data
    
    # Get element ID to match with Apple Vision lines
    elem_id = elem.get("id", "")
    if not elem_id:
        return False
    
    # Get Apple Vision lines with bbox
    apple_lines = page_data.get("engines_raw", {}).get("apple_lines", [])
    if not apple_lines:
        return False
    
    # Find matching line by text (fuzzy match for OCR differences)
    elem_text = (elem.get("text") or "").strip()
    matching_line = None
    best_match = None
    best_score = 0
    
    for line_obj in apple_lines:
        line_text = str(line_obj.get("text", "")).strip()
        # Exact match
        if line_text == elem_text:
            matching_line = line_obj
            break
        # Fuzzy match: check if normalized versions match
        from difflib import SequenceMatcher
        score = SequenceMatcher(None, elem_text.lower(), line_text.lower()).ratio()
        if score > best_score and score > 0.8:  # 80% similarity threshold
            best_score = score
            best_match = line_obj
    
    if not matching_line:
        matching_line = best_match
    
    if not matching_line or "bbox" not in matching_line:
        return False
    
    bbox = matching_line.get("bbox", [])
    if len(bbox) < 4:
        return False
    
    x0, y0, x1, y1 = bbox[0], bbox[1], bbox[2], bbox[3]
    candidate_x_center = (x0 + x1) / 2.0
    
    # Calculate average centerpoint of ALL text lines on the page (relative centering)
    all_centers = []
    for line_obj in apple_lines:
        if "bbox" not in line_obj:
            continue
        line_bbox = line_obj.get("bbox", [])
        if len(line_bbox) >= 4:
            line_x0, line_x1 = line_bbox[0], line_bbox[2]
            line_center = (line_x0 + line_x1) / 2.0
            all_centers.append(line_center)
    
    if not all_centers:
        return False
    
    # Calculate average centerpoint (this is the "text body centerline")
    avg_center = sum(all_centers) / len(all_centers)
    
    # Calculate standard deviation to determine tolerance
    import statistics
    if len(all_centers) > 1:
        std_dev = statistics.stdev(all_centers)
        # Use 2x std_dev as tolerance (covers ~95% of normal distribution)
        tolerance = max(0.02, std_dev * 2)  # Minimum 2% tolerance
    else:
        tolerance = 0.05  # Default 5% tolerance
    
    # Check if candidate is centered relative to average centerline
    # Headers should be within tolerance of the average center
    offset = abs(candidate_x_center - avg_center)
    is_centered = offset <= tolerance
    
    return is_centered


def load_pagelines_for_centering(pagelines_path: str) -> Dict:
    """
    Load pagelines data to access bbox information for centering detection.
    Returns dict mapping page number to page data.
    """
    pagelines_by_page = {}
    if not pagelines_path or not os.path.exists(pagelines_path):
        return pagelines_by_page
    
    try:
        with open(pagelines_path, "r", encoding="utf-8") as f:
            for line in f:
                page_data = json.loads(line)
                page_num = page_data.get("page")
                if page_num:
                    pagelines_by_page[page_num] = page_data
    except Exception:
        pass
    
    return pagelines_by_page


def main():
    parser = argparse.ArgumentParser(description="Detect gameplay section headers by numeric-only lines.")
    parser.add_argument("--pages", required=True, help="elements.jsonl (intake output)")
    parser.add_argument("--pages-core", dest="pages_core", help="Optional elements_core.jsonl for additional candidates")
    parser.add_argument("--macro", required=False, help="macro_sections.json from macro_locate_ff_v1")
    parser.add_argument("--pagelines", help="Optional pagelines_final.jsonl for centering detection")
    parser.add_argument("--out", required=True, help="Output section_boundaries.jsonl")
    parser.add_argument("--min_id", type=int, default=1)
    parser.add_argument("--max_id", type=int, default=400)
    parser.add_argument("--use-centering", action="store_true", help="Use bbox-based centering detection (requires --pagelines)")
    parser.add_argument("--progress-file")
    parser.add_argument("--state-file")
    parser.add_argument("--run-id")
    args = parser.parse_args()

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    logger.log("portionize", "running", current=0, total=1,
               message="Scanning numeric headers", module_id="detect_gameplay_numbers_v1", artifact=args.out)

    macro_hint = load_macro_hint(args.macro)
    main_start_page = None
    if macro_hint:
        for sec in macro_hint.get("sections", []):
            if sec.get("section_name") == "main_content":
                main_start_page = sec.get("page")
    # Accept all pages if hint missing

    range_re = re.compile(r"\d+\s*[-–]\s*\d+")
    boundaries: List[Dict] = []
    seen_ids = set()
    count = 0
    page_files = [args.pages]
    if args.pages_core and os.path.exists(args.pages_core):
        page_files.append(args.pages_core)
    
    # Load all elements first for context validation
    all_elements: List[Dict] = []
    for page_file in page_files:
        all_elements.extend(list(read_jsonl(page_file)))
    
    # Load pagelines data for centering detection if requested
    pagelines_data = {}
    if args.use_centering and args.pagelines:
        pagelines_data = load_pagelines_for_centering(args.pagelines)
        if pagelines_data:
            logger.log("portionize", "running", current=5, total=100,
                       message=f"Loaded bbox data from {len(pagelines_data)} pages for centering detection",
                       module_id="detect_gameplay_numbers_v1", artifact=args.out)
    
    # Process elements with context validation and optional centering check
    for elem in all_elements:
        text = (elem.get("text") or "").strip()
        if not text:
            continue
        if text.lower().startswith("turn to"):
            continue  # navigation text, not a header
        if range_re.search(text):
            continue  # page header like "171-172"
        if text.count(" ") > 1 or len(text) > 12:
            continue
        token = "".join(text.split())  # drop internal spaces
        candidates = expand_candidates(token)
        if not candidates:
            continue
        page = elem.get("metadata", {}).get("page_number") or elem.get("page")
        for sid in candidates:
            if sid < args.min_id or sid > args.max_id:
                continue
            if main_start_page and page and page < main_start_page:
                continue  # skip frontmatter
            if sid in seen_ids:
                continue  # keep first occurrence
            
            # Context validation: check if number is standalone (not embedded in sentence)
            if not validate_context(elem, all_elements, page):
                continue  # Reject embedded numbers
            
            # Centering check: if enabled and bbox data available, verify header is centered
            is_centered = False
            confidence = 0.7
            evidence_parts = [f"numeric-or-OCR-glitch line page={page} text='{text[:40]}'"]
            
            if args.use_centering and pagelines_data:
                is_centered = check_centering(elem, pagelines_data, page)
                if is_centered:
                    confidence = 0.9  # Higher confidence for centered headers
                    evidence_parts.append("centered")
                # Don't reject non-centered - centering is a boost, not a requirement
                # (some headers might be slightly off-center due to OCR bbox errors)
            
            boundary = SectionBoundary(
                section_id=str(sid),
                start_element_id=elem["id"],
                end_element_id=None,
                confidence=confidence,
                evidence="; ".join(evidence_parts),
                module_id="detect_gameplay_numbers_v1",
                run_id=args.run_id,
            )
            boundaries.append(boundary.model_dump(exclude_none=True))
            seen_ids.add(sid)
            count += 1

    # sort by section_id then confidence
    boundaries.sort(key=lambda b: int(b["section_id"]))

    ensure_dir(os.path.dirname(args.out) or ".")
    save_jsonl(args.out, boundaries)
    logger.log("portionize", "done", current=count, total=count,
               message=f"Detected {count} numeric headers", module_id="detect_gameplay_numbers_v1",
               artifact=args.out, schema_version="section_boundary_v1")
    print(f"[detect_gameplay_numbers] wrote {len(boundaries)} boundaries → {args.out}")


if __name__ == "__main__":
    main()
