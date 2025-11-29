"""
Element-aware portionizer for Unstructured elements.

This module works directly with elements instead of converting to pages.
It detects section boundaries using regex on element text, then groups
elements into portions. Much more accurate than page-based approaches.
"""

import argparse
import re
from typing import List, Dict, Set, Optional
from collections import defaultdict

from modules.common.utils import read_jsonl, save_jsonl

ANCHOR_RE = re.compile(r"^\s*(\d{1,4})\b")


def is_likely_gameplay_section(section_id: str, text: str, text_after_anchor: str) -> bool:
    """
    Filter false positives:
    - Section 0 is usually a false positive
    - Very short text after anchor with period (likely numbered list item)
    - Sections in range 1-400 are likely gameplay (vs rules 1-7)
    """
    # Section 0 is almost always false positive
    if section_id == "0":
        return False
    
    # Filter numbered list items from rules (e.g., "3. If your Attack Strength...")
    # These have period after number and short text
    if text_after_anchor.startswith(".") and len(text_after_anchor.strip()) < 20:
        # But check if section number is in typical gameplay range
        try:
            sid_num = int(section_id)
            if sid_num <= 7:  # Rules sections are typically 1-7
                return False
        except ValueError:
            pass
    
    # Sections in range 1-400 are likely gameplay sections
    try:
        sid_num = int(section_id)
        if 1 <= sid_num <= 400:
            # Even if text seems short, if it's in gameplay range, trust it
            # (the element might just be the section header)
            return True
    except ValueError:
        pass
    
    # For other cases, need some text content
    if len(text_after_anchor.strip()) < 5:
        return False
    
    return True


def detect_sections_from_elements(elements: List[Dict]) -> Dict[str, Dict]:
    """
    Detect sections from elements by finding numeric anchors in element text.
    
    Filters false positives (section 0, very short text, etc.).
    Returns dict mapping section_id to element info.
    """
    sections = {}
    
    # Sort elements by sequence/page for processing
    def sort_key(elem):
        page = elem.get("metadata", {}).get("page_number", 1)
        seq = elem.get("_codex", {}).get("sequence")
        if seq is not None:
            return (page, seq)
        coords = elem.get("metadata", {}).get("coordinates", {})
        points = coords.get("points", [])
        if points:
            ys = [p[1] for p in points]
            return (page, min(ys))
        return (page, 0)
    
    sorted_elements = sorted(elements, key=sort_key)
    
    for elem in sorted_elements:
        elem_type = elem.get("type")
        text = elem.get("text", "").strip()
        
        # Skip headers/footers/page breaks
        if elem_type in ("Header", "Footer", "PageBreak"):
            continue
        
        # Skip empty text
        if not text:
            continue
        
        # Look for section number at start of element text
        match = ANCHOR_RE.match(text)
        if match:
            section_id = match.group(1)
            text_after_anchor = text[len(match.group(0)):].strip()
            
            # Filter false positives
            if not is_likely_gameplay_section(section_id, text, text_after_anchor):
                continue
            
            # Use first occurrence of each section_id
            if section_id not in sections:
                sections[section_id] = {
                    "section_id": section_id,
                    "start_element_id": elem.get("id"),
                    "start_page": elem.get("metadata", {}).get("page_number", 1),
                    "start_sequence": elem.get("_codex", {}).get("sequence"),
                    "detection_method": "element_text_anchor",
                    "text_preview": text[:80],
                }
    
    return sections


def create_portions_from_sections(
    sections: Dict[str, Dict],
    elements: List[Dict]
) -> List[Dict]:
    """
    Create portion hypotheses from detected sections.
    
    Assigns page spans ensuring no overlaps. When multiple sections start on the
    same page, assigns each a single-page span to avoid conflicts in resolve stage.
    """
    # Build element lookup and page mapping
    element_map = {elem.get("id"): elem for elem in elements}
    
    # Sort sections by start page/sequence
    sorted_sections = sorted(
        sections.items(),
        key=lambda x: (
            x[1]["start_page"],
            x[1].get("start_sequence", 0)
        )
    )
    
    # Find max page for last section
    max_page = max(
        elem.get("metadata", {}).get("page_number", 1)
        for elem in elements
    ) if elements else 1
    
    portions = []
    
    # Track which pages have sections starting on them
    sections_by_page = {}
    for section_id, section_info in sorted_sections:
        page = section_info["start_page"]
        if page not in sections_by_page:
            sections_by_page[page] = []
        sections_by_page[page].append((section_id, section_info))
    
    for idx, (section_id, section_info) in enumerate(sorted_sections):
        start_page = section_info["start_page"]
        
        # Count how many sections start on this page
        same_page_sections = sections_by_page[start_page]
        section_index_on_page = next(i for i, (sid, _) in enumerate(same_page_sections) if sid == section_id)
        
        # Strategy: For sections starting on same page, assign single-page spans
        # This prevents overlaps while still capturing the section content
        if len(same_page_sections) > 1:
            # Multiple sections on same page - give each its own single-page span
            end_page = start_page
        else:
            # Only section on this page - can span to next section
            if idx + 1 < len(sorted_sections):
                next_section = sorted_sections[idx + 1][1]
                next_start_page = next_section["start_page"]
                
                # If next section starts on next page or later, this section can span
                if next_start_page > start_page:
                    end_page = next_start_page - 1
                else:
                    # Next section is on same page - single page span
                    end_page = start_page
            else:
                # Last section - spans to document end
                end_page = max_page
        
        # Ensure end >= start
        if end_page < start_page:
            end_page = start_page
        
        # Determine source pages
        source_pages = list(range(start_page, end_page + 1))
        
        portions.append({
            "schema_version": "portion_hyp_v1",
            "portion_id": section_id,
            "page_start": start_page,
            "page_end": end_page,
            "title": None,
            "type": "section",
            "confidence": 0.85,  # High confidence - regex-based detection is reliable
            "notes": f"element-based detection: {section_info['detection_method']}",
            "source_window": source_pages[:1] if source_pages else [start_page],  # First page as window
            "source_pages": source_pages,
            "continuation_of": None,
            "continuation_confidence": None,
        })
    
    return portions


def main():
    parser = argparse.ArgumentParser(
        description="Element-aware portionizer that works directly with Unstructured elements."
    )
    parser.add_argument("--pages", required=True, help="Path to elements.jsonl")
    parser.add_argument("--out", required=True, help="Output portion hypotheses JSONL")
    parser.add_argument("--state-file", help="ignored")
    parser.add_argument("--progress-file", help="ignored")
    parser.add_argument("--run-id", help="ignored")
    args = parser.parse_args()
    
    # Load elements
    raw_data = list(read_jsonl(args.pages))
    
    # Detect format
    first = raw_data[0] if raw_data else {}
    is_elements = "type" in first and "metadata" in first
    
    if not is_elements:
        raise SystemExit("Error: Input must be elements.jsonl format")
    
    elements = raw_data
    
    print(f"Loaded {len(elements)} elements")
    
    # Detect sections from elements
    sections = detect_sections_from_elements(elements)
    print(f"Detected {len(sections)} sections from elements")
    
    # Create portions
    portions = create_portions_from_sections(sections, elements)
    print(f"Created {len(portions)} portion hypotheses")
    
    # Save output
    save_jsonl(args.out, portions)
    print(f"Wrote {len(portions)} portions → {args.out}")


if __name__ == "__main__":
    main()

