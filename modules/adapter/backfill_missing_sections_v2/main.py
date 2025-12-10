import argparse
import json
import re
from typing import Dict, List, Optional

from modules.common.utils import read_jsonl, save_jsonl, ProgressLogger


def load_elements(path: str) -> List[Dict]:
    return list(read_jsonl(path))


def load_boundaries(path: str) -> List[Dict]:
    return list(read_jsonl(path))


def extract_page_from_element_id(element_id: str) -> Optional[int]:
    """Extract page number from element ID like '095L-0028' -> 95, '049R-0023' -> 49."""
    if not element_id:
        return None
    # Match pattern like "095L" or "049R" at start
    match = re.match(r"(\d{3})([LR]?)", element_id)
    if match:
        return int(match.group(1))
    return None


def get_page_from_element(element: Dict) -> Optional[int]:
    """Get page number from element (from metadata or extracted from ID)."""
    # Try metadata first
    page = element.get("page") or element.get("metadata", {}).get("page_number")
    if page:
        return int(page) if isinstance(page, (int, str)) and str(page).isdigit() else None
    # Fall back to extracting from ID
    return extract_page_from_element_id(element.get("id", ""))


def is_sentence_ending(text: str) -> bool:
    """Check if text ends with sentence punctuation."""
    if not text:
        return True
    text = text.strip()
    return text.endswith('.') or text.endswith('!') or text.endswith('?') or text.endswith(':')


def starts_new_sentence(text: str) -> bool:
    """Check if text starts with a capital letter (new sentence)."""
    if not text:
        return True
    text = text.strip()
    return text and text[0].isupper()


def validate_context(elem: Dict, all_elements: List[Dict], page: int) -> bool:
    """Validate that a candidate number is standalone (not embedded in sentence)."""
    page_elements = [e for e in all_elements if get_page_from_element(e) == page]
    page_elements.sort(key=lambda e: e.get("id", ""))
    
    try:
        current_idx = next(i for i, e in enumerate(page_elements) if e.get("id") == elem.get("id"))
    except StopIteration:
        return True
    
    prev_elem = page_elements[current_idx - 1] if current_idx > 0 else None
    prev_text = (prev_elem.get("text") or "").strip() if prev_elem else ""
    
    next_elem = page_elements[current_idx + 1] if current_idx < len(page_elements) - 1 else None
    next_text = (next_elem.get("text") or "").strip() if next_elem else ""
    
    prev_valid = is_sentence_ending(prev_text) or not prev_text
    next_valid = starts_new_sentence(next_text) or not next_text
    
    if prev_valid and next_valid:
        return True
    
    if not prev_valid and not next_valid:
        return False
    
    return True  # Be lenient for edge cases


def find_element_ids_for_number(elements: List[Dict], number: str, 
                                min_page: Optional[int] = None, 
                                max_page: Optional[int] = None,
                                validate_context_flag: bool = True) -> List[str]:
    """Return element ids whose text contains the target number (exact or normalized).
    
    If min_page/max_page are provided, only return matches on pages within that range.
    If validate_context_flag is True, only return matches that are standalone (not embedded in sentences).
    """
    hits = []
    target = number.strip()
    for el in elements:
        txt = str(el.get("text", ""))
        if not txt:
            continue
        stripped = txt.strip()
        
        # Check page ordering if bounds provided
        if min_page is not None or max_page is not None:
            page = get_page_from_element(el)
            if page is not None:
                if min_page is not None and page < min_page:
                    continue  # Too early
                if max_page is not None and page > max_page:
                    continue  # Too late
        
        # Check exact match first (highest confidence)
        if stripped == target:
            hits.append((el.get("id"), "exact"))
            continue
        # normalize: remove non-digits and compare
        digits = "".join(ch for ch in stripped if ch.isdigit())
        if digits == target:
            # Only add if it's a short standalone number (likely a header, not embedded)
            if len(stripped) <= 5 and stripped.count(" ") <= 1:
                hits.append((el.get("id"), "normalized"))
            continue
        # Pattern match: extract any short digit groups within text
        # But only if it's a standalone element (not part of longer text)
        groups = [g for g in re.findall(r"\d{1,3}", stripped)]
        if target in groups and len(stripped) <= 5:
            hits.append((el.get("id"), "pattern"))
    
    # Apply context validation if enabled
    if validate_context_flag and hits:
        valid_hits = []
        for hit_id, match_type in hits:
            hit_elem = next((e for e in elements if e.get("id") == hit_id), None)
            if hit_elem:
                page = get_page_from_element(hit_elem)
                if page:
                    # Only validate context for exact matches (most reliable)
                    # Pattern matches are already filtered by length/space checks
                    if match_type == "exact" and not validate_context(hit_elem, elements, page):
                        continue  # Reject embedded exact matches
                valid_hits.append(hit_id)
        return valid_hits
    
    # Return just the IDs
    return [hit_id for hit_id, _ in hits]


def build_boundary(section_id: str, start_id: str, end_id: Optional[str]) -> Dict:
    return {
        "schema_version": "section_boundary_v1",
        "module_id": "backfill_missing_sections_v2",
        "section_id": section_id,
        "start_element_id": start_id,
        "end_element_id": end_id,
        "confidence": 0.4,
        "evidence": "digit-only element match in elements_core",
    }


def main():
    parser = argparse.ArgumentParser(description="Backfill missing section boundaries using elements_core digit hits.")
    parser.add_argument("--boundaries", required=True, help="Input section_boundaries.jsonl")
    parser.add_argument("--elements", required=True, help="Input elements_core.jsonl")
    parser.add_argument("--out", required=True, help="Output boundaries JSONL with backfilled entries")
    parser.add_argument("--expected-range-start", type=int, default=1)
    parser.add_argument("--expected-range-end", type=int, default=400)
    parser.add_argument("--target-ids", help="Optional comma-separated list or file path of specific missing section ids to backfill")
    parser.add_argument("--progress-file", help="Path to pipeline_events.jsonl")
    parser.add_argument("--state-file", help="Path to pipeline_state.json")
    parser.add_argument("--run-id", help="Run identifier for logging")
    args = parser.parse_args()

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)

    boundaries = load_boundaries(args.boundaries)
    elements = load_elements(args.elements)

    existing_ids = {b.get("section_id") for b in boundaries if b.get("section_id")}

    # derive missing set
    if args.target_ids:
        if "," in args.target_ids or args.target_ids.strip().isdigit():
            targets = [t.strip() for t in args.target_ids.split(",") if t.strip()]
        else:
            # treat as file path
            with open(args.target_ids, "r", encoding="utf-8") as f:
                targets = [ln.strip() for ln in f if ln.strip()]
        expected = set(targets)
    else:
        expected = {str(i) for i in range(args.expected_range_start, args.expected_range_end + 1)}

    missing = sorted(list(expected - existing_ids), key=lambda x: int(x))

    # Precompute element hits for missing numbers
    hits: Dict[str, List[str]] = {}
    for num in missing:
        ids = find_element_ids_for_number(elements, num)
        if ids:
            hits[num] = ids

    # Build quick lookup for next boundary start per section ordering
    numeric_sorted = sorted([b for b in boundaries if str(b.get("section_id", "")).isdigit()], key=lambda b: int(b["section_id"]))
    next_start_map: Dict[str, Optional[str]] = {}
    for idx, b in enumerate(numeric_sorted):
        next_id = numeric_sorted[idx + 1]["start_element_id"] if idx + 1 < len(numeric_sorted) else None
        next_start_map[b["section_id"]] = next_id
    
    # Build page range map: for each missing section, find the page range it should be in
    # (between immediately previous and next detected sections)
    element_by_id = {el.get("id"): el for el in elements}
    page_range_map: Dict[str, Tuple[Optional[int], Optional[int]]] = {}
    for num in missing:
        num_int = int(num)
        # Find immediately previous section (largest section_id < num_int)
        prev_page = None
        for b in reversed(numeric_sorted):
            if int(b["section_id"]) < num_int:
                prev_elem = element_by_id.get(b.get("start_element_id"))
                if prev_elem:
                    prev_page = get_page_from_element(prev_elem)
                break
        # Find immediately next section (smallest section_id > num_int)
        next_page = None
        for b in numeric_sorted:
            if int(b["section_id"]) > num_int:
                next_elem = element_by_id.get(b.get("start_element_id"))
                if next_elem:
                    next_page = get_page_from_element(next_elem)
                break
        page_range_map[num] = (prev_page, next_page)

    added: List[Dict] = []
    for num, ids in hits.items():
        # Filter by page ordering: only accept matches within expected page range
        prev_page, next_page = page_range_map.get(num, (None, None))
        valid_ids = []
        for elem_id in ids:
            elem = element_by_id.get(elem_id)
            if not elem:
                continue
            page = get_page_from_element(elem)
            if page is None:
                continue  # Can't validate without page
            # Check if page is in valid range
            if prev_page is not None and page < prev_page:
                continue  # Too early - reject
            if next_page is not None and page > next_page:
                continue  # Too late - reject
            valid_ids.append(elem_id)
        
        if not valid_ids:
            # No valid matches after page ordering check
            continue
        
        start_id = valid_ids[0]  # Use first valid match
        # find next existing boundary after this number
        next_after = None
        for b in numeric_sorted:
            if int(b["section_id"]) > int(num):
                next_after = b["start_element_id"]
                break
        boundary = build_boundary(num, start_id, next_after)
        added.append(boundary)

    all_boundaries = boundaries + added
    all_boundaries_sorted = sorted(all_boundaries, key=lambda b: int(b.get("section_id", 999999)))

    save_jsonl(args.out, all_boundaries_sorted)

    still_missing = len(missing) - len(added)
    logger.log("adapter", "done", current=len(all_boundaries_sorted), total=len(all_boundaries_sorted),
               message=f"Added {len(added)} boundaries; {still_missing} still missing", artifact=args.out,
               module_id="backfill_missing_sections_v2", schema_version="section_boundary_v1")

    print(f"Added {len(added)} boundaries; {still_missing} still missing → {args.out}")


if __name__ == "__main__":
    main()
