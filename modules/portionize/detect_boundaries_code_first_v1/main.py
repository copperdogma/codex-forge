#!/usr/bin/env python3
"""
Code-first section boundary detection with targeted AI escalation.

Follows AGENTS.md pattern: code → validate → targeted escalate → validate

IMPORTANT: This module now requires coarse_segments.json as input.
Elements are filtered to ONLY gameplay pages (excludes frontmatter/endmatter)
before boundary detection. This eliminates false positives from frontmatter.
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Optional, Any

from modules.common.utils import read_jsonl, save_jsonl, save_json, ensure_dir, ProgressLogger
from modules.common.macro_section import macro_section_for_page, page_num_from_element_id
from modules.common.escalation_cache import EscalationCache


def _resolve_images_dir(run_root: Path, explicit: Optional[str]) -> Path:
    """
    Resolve the images directory for vision escalation.

    Historically, page images may live either at:
    - <run_root>/images
    - <run_root>/<module_dir>/images (e.g., 01_extract_ocr_ensemble_v1/images)

    EscalationCache expects filenames like page-027L.png / page-027R.png.
    """
    if explicit:
        return Path(explicit)

    # Most direct: run_root/images
    direct = run_root / "images"
    if direct.exists():
        return direct

    # Otherwise: search for a sibling module images dir containing page-*.png
    best_dir: Optional[Path] = None
    best_count = 0
    try:
        for candidate in run_root.glob("*/images"):
            if not candidate.is_dir():
                continue
            # Prefer directories that actually look like rendered page images.
            count = len(list(candidate.glob("page-*.png")))
            if count > best_count:
                best_count = count
                best_dir = candidate
    except Exception:
        best_dir = None

    if best_dir:
        return best_dir

    # Fallback (will likely fail later, but error will be explicit).
    return direct


def filter_elements_to_gameplay(elements: List[Dict], gameplay_pages: List) -> List[Dict]:
    """
    Filter elements to ONLY those in the gameplay page range.

    Args:
        elements: All elements from elements_core_typed.jsonl
        gameplay_pages: [start_page, end_page] from coarse_segments.json
                       Can be integers (12, 110) or strings ("012L", "111L")

    Returns:
        Elements within gameplay range only (excludes frontmatter and endmatter)
    """
    import re

    def parse_page_id(elem):
        """Extract page identifier from element (handles both integer page and L/R splits)."""
        # First try to get from element ID (e.g., "111L-0000" -> "111L")
        elem_id = elem.get('id', '')
        if '-' in elem_id:
            return elem_id.split('-')[0]
        # Fallback to page field (integer)
        page = elem.get('page')
        return str(page) if page is not None else None

    def page_in_range(page_id, start, end):
        """Check if page_id is within [start, end] range (handles string page IDs)."""
        if page_id is None:
            return False

        # Extract numeric portions for comparison
        def extract_num_and_suffix(pid):
            """Extract (number, suffix) from page ID. E.g., "111L" -> (111, "L"), 12 -> (12, "")"""
            pid_str = str(pid)
            match = re.match(r'^(\d+)([LR]?)$', pid_str)
            if match:
                return (int(match.group(1)), match.group(2) or '')
            return None

        page_parts = extract_num_and_suffix(page_id)
        start_parts = extract_num_and_suffix(start)
        end_parts = extract_num_and_suffix(end)

        if not all([page_parts, start_parts, end_parts]):
            return False

        page_num, page_suffix = page_parts
        start_num, start_suffix = start_parts
        end_num, end_suffix = end_parts

        # Compare: (number, suffix) tuple comparison works naturally
        # "111L" < "111R" because ("L" < "R")
        # "012L" < "111L" because (12 < 111)
        return (page_num, page_suffix) >= (start_num, start_suffix) and \
               (page_num, page_suffix) <= (end_num, end_suffix)

    start_page, end_page = gameplay_pages
    filtered = []
    for elem in elements:
        page_id = parse_page_id(elem)
        if page_in_range(page_id, start_page, end_page):
            filtered.append(elem)

    return filtered


def filter_section_headers(elements: List[Dict], min_section: int, max_section: int,
                           gameplay_pages: Optional[List] = None) -> List[Dict]:
    """
    Code-first: Filter elements for Section-header with valid numbers.
    This is FREE, instant, and deterministic.

    CRITICAL: Applies multi-stage validation to eliminate false positives:
    1. Content type filtering (Section-header classification)
    2. Range validation (min_section to max_section)
    3. Page-level clustering with expected range selection (eliminate outliers on same page)
    4. Multi-page duplicate resolution (choose best instance)
    5. Sequential validation (enforce ordering)

    Args:
        elements: Elements to filter (pre-filtered to gameplay pages)
        min_section: Minimum section number
        max_section: Maximum section number
        gameplay_pages: [start, end] page range from coarse_segments (enables smart clustering)
"""
    candidates = []

    # Build a quick index so we can score candidates by their immediate context in reading order.
    # This is critical when the same section number appears multiple times on a page
    # (e.g., running headers, cross-refs, noise). We prefer the occurrence that is
    # followed by real body text rather than another header.
    element_index_by_id = {}
    for idx, e in enumerate(elements):
        eid = e.get("id") or e.get("element_id")
        if eid:
            element_index_by_id[eid] = idx

    def _alpha_ratio(s: str) -> float:
        if not s:
            return 0.0
        letters = sum(1 for c in s if c.isalpha())
        return letters / max(1, len(s))

    def _follow_text_score(elem_idx: int, page: Optional[int]) -> int:
        """
        Score how likely this element is a true section start by looking ahead
        for substantial alphabetic text on the same page.
        """
        if elem_idx is None:
            return 0
        score = 0
        for j in range(1, 7):
            k = elem_idx + j
            if k >= len(elements):
                break
            nxt = elements[k]
            if page is not None and nxt.get("page") != page:
                break
            if nxt.get("content_type") == "Section-header":
                break
            txt = (nxt.get("text") or "").strip()
            if len(txt) >= 20 and _alpha_ratio(txt) >= 0.5:
                score += min(200, len(txt))
        return score

    for elem in elements:
        # Check if marked as Section-header by content_type classifier
        # NOTE: This is a SIGNAL, not a guarantee - we validate further below
        if elem.get('content_type') != 'Section-header':
            continue
        
        # Extract section number from content_subtype
        subtype = elem.get('content_subtype') or {}
        section_num = subtype.get('number') if isinstance(subtype, dict) else None
        
        if section_num is None:
            continue
        
        # Validate range
        if not (min_section <= section_num <= max_section):
            continue
        
        # VALIDATION: Content type classification is a SIGNAL, not a guarantee
        # Additional checks to filter false positives (e.g., page numbers misclassified as headers)
        page = elem.get('page')
        if page is not None:
            # Check layout position if available (bottom of page = likely page number footer)
            layout = elem.get('layout') or {}
            if isinstance(layout, dict):
                y = layout.get('y')
                if y is not None and y >= 0.92:
                    # At bottom of page (y >= 0.92) - likely a page number footer, not a section header
                    continue
        
        # Create boundary record (allow duplicates for now, will filter in validation)
        # Use 'id' field (element schema uses 'id', not 'element_id')
        element_id = elem.get('id') or elem.get('element_id')
        elem_idx = element_index_by_id.get(element_id) if element_id else None
        candidates.append({
            'section_id': str(section_num),
            'start_element_id': element_id,
            'start_page': page,
            'start_line_idx': elem.get('line_idx'),
            'seq_idx': elem_idx,
            'follow_text_score': _follow_text_score(elem_idx, page),
            'confidence': 0.95,
            'method': 'code_filter',
            'source': 'content_type_classification'
        })
    
    # NOTE: Frontmatter filtering is now handled UPSTREAM by coarse segmentation
    # We trust that elements have already been filtered to gameplay pages only
    # No need to re-detect section 1 or filter frontmatter here

    # STAGE 1: Page-level clustering with expected range selection to eliminate outliers
    clustered = _filter_page_outliers(candidates, gameplay_pages, max_section)
    
    # STAGE 2: Multi-page duplicate resolution
    deduplicated = _resolve_duplicates(clustered)
    
    # STAGE 3: Sequential validation (now redundant frontmatter check, but keeps logic clean)
    validated = _validate_sequential_ordering(deduplicated)
    
    # Sort by section number
    validated.sort(key=lambda b: int(b['section_id']))

    return validated


def _build_element_sequence(elements: List[Dict]) -> tuple:
    """Return (elements_sorted, element_sequence, id_to_index, id_to_seq)."""
    elements_sorted = sorted(elements, key=lambda e: int(e.get("seq") or 0))
    element_sequence = [e.get("id") for e in elements_sorted if e.get("id")]
    id_to_index = {eid: idx for idx, eid in enumerate(element_sequence)}
    id_to_seq = {e.get("id"): int(e.get("seq") or 0) for e in elements_sorted if e.get("id")}
    return elements_sorted, element_sequence, id_to_index, id_to_seq


def detect_ordering_conflicts(boundaries: List[Dict], id_to_seq: Dict[str, int]) -> Dict[str, Dict]:
    """
    Detect pages where numeric section order contradicts element sequence order.
    Group by page side (L/R) to avoid false conflicts across spreads.
    Returns {page: {"sides": {side: {"sections_seq": [...], "sections_numeric": [...]}}}}.
    """
    import re

    def page_side(b: Dict) -> str:
        eid = str(b.get("start_element_id") or "")
        m = re.match(r"^(\d+)([LR])-", eid)
        return m.group(2) if m else ""

    page_groups: Dict[str, Dict[str, List[Dict]]] = defaultdict(lambda: defaultdict(list))
    for b in boundaries:
        page = b.get("start_page")
        if page is None:
            continue
        side = page_side(b)
        page_key = f"{int(page)}{side}" if side else str(int(page))
        page_groups[page_key][side].append(b)

    conflicts: Dict[str, Dict] = {}
    for page_key, sides in page_groups.items():
        page_conflicts = {}
        for side, items in sides.items():
            if len(items) < 2:
                continue
            items_sorted = sorted(items, key=lambda b: id_to_seq.get(b.get("start_element_id"), 999999))
            seq_order = [int(b["section_id"]) for b in items_sorted]
            if seq_order != sorted(seq_order):
                page_conflicts[side or ""] = {
                    "sections_seq": seq_order,
                    "sections_numeric": sorted(seq_order),
                }
        if page_conflicts:
            conflicts[page_key] = {"sides": page_conflicts}
    return conflicts


def assign_macro_sections(boundaries: List[Dict], elements_by_id: Dict[str, Dict],
                          coarse_segments: Optional[Dict[str, Any]]) -> None:
    if not coarse_segments:
        return
    for b in boundaries:
        if b.get("macro_section"):
            continue
        page = b.get("start_page")
        if page is None:
            start_id = b.get("start_element_id")
            elem = elements_by_id.get(start_id) if start_id else None
            page = (elem.get("page") if elem else None) or (elem.get("metadata", {}).get("page_number") if elem else None)
            if page is None:
                page = page_num_from_element_id(start_id)
        b["macro_section"] = macro_section_for_page(page, coarse_segments)


def detect_span_issues(boundaries: List[Dict],
                       id_to_index: Dict[str, int],
                       elements_sorted: List[Dict],
                       min_words: int = 5,
                       min_alpha_ratio: float = 0.2,
                       min_alpha_chars: int = 20) -> Dict[int, Dict]:
    """
    Detect sections whose numeric-order span is inverted or has no real text.
    Returns {page: {"reason": "...", "section_id": "..."}}
    """
    issues: Dict[int, Dict] = {}
    if not boundaries:
        return issues

    boundaries_sorted = sorted(boundaries, key=lambda b: int(b["section_id"]))
    next_start_by_sid = {}
    for i, b in enumerate(boundaries_sorted):
        sid = b.get("section_id")
        if not sid:
            continue
        next_start_by_sid[sid] = boundaries_sorted[i + 1]["start_element_id"] if i + 1 < len(boundaries_sorted) else None

    for b in boundaries_sorted:
        sid = b.get("section_id")
        start_id = b.get("start_element_id")
        end_id = next_start_by_sid.get(sid)
        if not start_id or start_id not in id_to_index:
            continue
        start_idx = id_to_index[start_id]
        end_idx = id_to_index.get(end_id, len(elements_sorted)) if end_id else len(elements_sorted)
        page = b.get("start_page")
        if page is None:
            continue
        eid = str(start_id or "")
        side = ""
        if isinstance(eid, str) and len(eid) >= 5 and eid[3] in ("L", "R"):
            side = eid[3]
        page_key = f"{int(page)}{side}" if side else str(int(page))
        if end_idx < start_idx:
            issues[page_key] = {"reason": "inverted_span", "section_id": sid}
            continue
        span = elements_sorted[start_idx:end_idx]
        alpha_chars = 0
        total_chars = 0
        word_count = 0
        for e in span:
            if e.get("content_type") == "Section-header":
                continue
            text = (e.get("text") or "").strip()
            if not text:
                continue
            total_chars += len(text)
            alpha_chars += sum(ch.isalpha() for ch in text)
            word_count += len([w for w in text.split() if any(c.isalpha() for c in w)])
        alpha_ratio = (alpha_chars / total_chars) if total_chars else 0.0
        if word_count < min_words or alpha_chars < min_alpha_chars or alpha_ratio < min_alpha_ratio:
            issues[page_key] = {
                "reason": "empty_or_low_text_span",
                "section_id": sid,
                "word_count": word_count,
                "alpha_chars": alpha_chars,
                "alpha_ratio": round(alpha_ratio, 3),
            }
    return issues


def _filter_page_outliers(candidates: List[Dict], gameplay_pages: Optional[List] = None,
                          max_section: int = 400) -> List[Dict]:
    """
    Eliminate false positives using page-level clustering with expected range selection.

    Strategy: On each page, find clusters of consecutive sections (gap ≤ 5).
    Select the cluster whose center is CLOSEST to the expected section for that page.

    Why not "largest cluster"? False positives can outnumber valid sections!
    Example: Page 51 has [7,7,8,8,8,8] (6 false positives) and [148,149,150,151] (4 valid).
    Largest cluster = [7,8] ✗ Wrong! Expected section ~157, so [148-151] is correct ✓

    Args:
        candidates: Boundary candidates to filter
        gameplay_pages: [start, end] page range from coarse_segments (e.g., ["012L", "111L"])
        max_section: Maximum section number (default: 400)
    """
    import re

    def parse_page_num(page_id):
        """Extract numeric portion from page ID (e.g., "051L" → 51, 73 → 73)."""
        if isinstance(page_id, int):
            return page_id
        match = re.match(r'^(\d+)', str(page_id))
        return int(match.group(1)) if match else 0

    def expected_section_for_page(page_id):
        """Calculate expected section number for a page based on position in gameplay range."""
        if not gameplay_pages or len(gameplay_pages) < 2:
            # Fallback: assume linear distribution across all pages
            page_num = parse_page_num(page_id)
            return page_num * 4  # Rough estimate: ~4 sections per page

        start_num = parse_page_num(gameplay_pages[0])
        end_num = parse_page_num(gameplay_pages[1])
        page_num = parse_page_num(page_id)

        # Position in gameplay range (0 to 1)
        if end_num == start_num:
            position = 0.5
        else:
            position = (page_num - start_num) / (end_num - start_num)
            position = max(0, min(1, position))  # Clamp to [0, 1]

        return int(position * max_section)

    def cluster_center(cluster_indices, sections):
        """Calculate the center (average) of a cluster."""
        return sum(sections[i] for i in cluster_indices) / len(cluster_indices)

    # Group candidates by page
    page_groups = defaultdict(list)
    for boundary in candidates:
        page = boundary['start_page']
        page_groups[page].append(boundary)

    filtered = []

    for page, boundaries in page_groups.items():
        if len(boundaries) == 1:
            # Single section on page → keep it
            filtered.append(boundaries[0])
            continue

        # Sort by section number
        boundaries.sort(key=lambda b: int(b['section_id']))
        sections = [int(b['section_id']) for b in boundaries]

        # Find clusters (sections within 5 of each other)
        clusters = []
        current_cluster = [0]  # Indices
        for i in range(1, len(sections)):
            if sections[i] - sections[i-1] <= 5:
                current_cluster.append(i)
            else:
                clusters.append(current_cluster)
                current_cluster = [i]
        clusters.append(current_cluster)

        # Select cluster with WEIGHTED preference: larger clusters preferred unless smaller is significantly closer
        # Rationale: Non-uniform section distribution means expected section is approximate
        # Large clusters (multiple consecutive sections) are more likely valid than small false positives
        # Only prefer smaller cluster if it's 3× closer to expected section
        expected = expected_section_for_page(page)

        # Sort clusters by size (largest first)
        clusters_sorted = sorted(clusters, key=lambda c: len(c), reverse=True)

        # Start with largest cluster
        best_cluster_indices = clusters_sorted[0]
        best_center = cluster_center(best_cluster_indices, sections)
        best_distance = abs(best_center - expected)

        # Check if any smaller cluster is significantly closer (3× threshold)
        for cluster_indices in clusters_sorted[1:]:
            center = cluster_center(cluster_indices, sections)
            distance = abs(center - expected)

            # Only switch to smaller cluster if it's at least 3× closer
            if distance * 3 < best_distance:
                best_cluster_indices = cluster_indices
                best_center = center
                best_distance = distance

        # Keep only the best cluster
        for idx in best_cluster_indices:
            filtered.append(boundaries[idx])

    return filtered


def _resolve_duplicates(candidates: List[Dict]) -> List[Dict]:
    """
    Resolve duplicates by choosing the best instance of each section.
    
    Strategy: For sections appearing on multiple pages, calculate a \"fit score\"
    based on how well the section fits the local sequence.
    
    Fit score = number of consecutive sections on same page.
    Example:
        Section 97 on page 37: [89, 92, 97] → fit = 1 (no consecutive neighbors)
        Section 97 on page 39: [96, 97, 98, 99] → fit = 4 (part of consecutive run)
        → Choose page 39
    """
    # Group by section_id
    section_groups = defaultdict(list)
    for boundary in candidates:
        section_id = int(boundary['section_id'])
        section_groups[section_id].append(boundary)
    
    deduplicated = []
    
    for section_id, boundaries in section_groups.items():
        if len(boundaries) == 1:
            deduplicated.append(boundaries[0])
            continue

        # Multiple instances - calculate fit scores
        best_boundary = None
        best_fit = -1
        best_follow = -1
        
        for boundary in boundaries:
            page = boundary['start_page']

            follow = int(boundary.get("follow_text_score") or 0)

            # Get all sections on this page (from candidates)
            page_sections = sorted([
                int(b['section_id']) for b in candidates 
                if b['start_page'] == page
            ])
            
            # Calculate fit: count consecutive neighbors
            fit_score = 1  # The section itself
            
            # Check consecutive neighbors
            for offset in [1, -1]:
                check_section = section_id
                while True:
                    check_section += offset
                    if check_section in page_sections:
                        fit_score += 1
                    else:
                        break

            # Prefer the occurrence that best fits a consecutive run; use follow_text_score as tie-break.
            # Rationale: stray false positives can have high follow_text_score (because they're embedded in body text),
            # while true headers typically sit at the start of a consecutive run (e.g., 95-97).
            if fit_score > best_fit or (fit_score == best_fit and follow > best_follow):
                best_fit = fit_score
                best_follow = follow
                best_boundary = boundary
        
        deduplicated.append(best_boundary)
    
    return deduplicated


def _validate_sequential_ordering(candidates: List[Dict]) -> List[Dict]:
    """
    Eliminate false positives using sequential validation.

    Key insight: Fighting Fantasy sections are 100% in order.
    Section numbers MUST increase (roughly) with page numbers.

    NOTE: Frontmatter filtering is handled upstream by coarse segmentation.
    We just apply basic sequential validation here.
    """
    if not candidates:
        return []

    # Sort by page, then section number
    candidates.sort(key=lambda b: (b['start_page'], int(b['section_id'])))

    validated = []
    last_section = 0
    last_page = 0
    seen_sections = set()

    for boundary in candidates:
        page = boundary['start_page']
        sect = int(boundary['section_id'])

        # Skip duplicates
        if sect in seen_sections:
            continue

        # Accept sections that continue the sequence
        if sect > last_section:
            # Additional check: Is the jump REASONABLE?
            # Rule: Can't jump more than ~10 sections without advancing at least 1 page
            # (FF typically has 3-4 sections per page, so 10 is generous)
            section_jump = sect - last_section
            page_advance = page - last_page

            # Allow big jumps if pages advance, or small jumps on same page
            if page_advance > 0 or section_jump <= 10:
                validated.append(boundary)
                seen_sections.add(sect)
                last_section = sect
                last_page = page
            # else: reject (unreasonable jump on same page, likely false positive)
        else:
            # If we see a small backwards step on a later page, prefer the later page and
            # treat the prior accepted section as a false positive. This prevents one stray
            # misclassified header from derailing the rest of the sequence.
            #
            # Example (observed): page 37 has a false "97" candidate; page 38 correctly starts at 93.
            if validated and page >= last_page and (last_section - sect) <= 10 and (page - last_page) <= 3:
                prev = validated.pop()
                try:
                    seen_sections.remove(int(prev["section_id"]))
                except Exception:
                    pass
                validated.append(boundary)
                seen_sections.add(sect)
                last_section = sect
                last_page = page

    return validated


def find_missing_sections(boundaries: List[Dict], min_section: int, max_section: int) -> List[int]:
    """Find section numbers not detected."""
    detected = {int(b['section_id']) for b in boundaries}
    expected = set(range(min_section, max_section + 1))
    missing = sorted(expected - detected)
    return missing


def estimate_pages_for_sections_smart(missing_sections: List[int], detected_boundaries: List[Dict]) -> List[int]:
    """
    Smart page estimation using bracket constraints and ordering.
    Key insight: Sections are sequential, use detected sections as boundaries.
    """
    # Build map of detected section → page
    section_to_page = {}
    for boundary in detected_boundaries:
        section_id = int(boundary['section_id'])
        page = boundary.get('start_page')
        if page:
            section_to_page[section_id] = page
    
    if not section_to_page:
        return sorted(set(int(s / 3.5) for s in missing_sections))
    
    suspected_pages = set()
    
    for section_num in missing_sections:
        # Find IMMEDIATE neighbors (not just nearest)
        before = [s for s in section_to_page.keys() if s < section_num]
        after = [s for s in section_to_page.keys() if s > section_num]
        
        if before and after:
            nearest_before = max(before)
            nearest_after = min(after)
            page_before = section_to_page[nearest_before]
            page_after = section_to_page[nearest_after]
            
            if page_before == page_after:
                # Both neighbors on SAME page → target MUST be there
                # Example: page 26 has [43, 45] → section 44 must be on page 26
                suspected_pages.add(page_before)
            
            elif page_after == page_before + 1:
                # Neighbors on ADJACENT pages → target is on one of them
                # Don't search beyond these pages
                suspected_pages.add(page_before)
                suspected_pages.add(page_after)
            
            else:
                # Gap between pages → search the FULL range (no ±2, use actual bracket)
                # Example: page 20 has section 35, page 25 has section 45
                # Section 40 MUST be between pages 20-25
                for page in range(page_before, page_after + 1):
                    suspected_pages.add(page)
        
        elif before:
            # After last detected section - search next few pages only
            nearest_before = max(before)
            page_before = section_to_page[nearest_before]
            # Don't go crazy, just check next 3 pages
            for offset in range(0, 3):
                suspected_pages.add(page_before + offset)
        
        elif after:
            # Before first detected section - search previous few pages only
            nearest_after = min(after)
            page_after = section_to_page[nearest_after]
            # Check previous 3 pages
            for offset in range(-2, 1):
                suspected_pages.add(max(1, page_after + offset))
    
    return sorted([p for p in suspected_pages if p > 0])


def escalate_with_vision_cache(
    pages: List[int],
    missing_sections: List[int],
    escalation_cache: EscalationCache,
    triggered_by: str,
    existing_boundaries: List[Dict],
    elements_by_page: Dict[int, List[Dict]],
) -> List[Dict]:
    """
    Use vision escalation cache to find missing sections on problem pages.
    Returns boundary records for any found sections.
    """
    # Request escalation (cache handles dedup)
    escalation_data = escalation_cache.request_escalation(
        pages=pages,
        triggered_by=triggered_by,
        trigger_reason=f"missing_sections: {missing_sections[:20]}"
    )
    
    # Build set of already-detected sections
    already_detected = {int(b['section_id']) for b in existing_boundaries}
    existing_element_ids = {e.get("id") for elems in elements_by_page.values() for e in elems if e.get("id")}

    def _anchor_element_id(page: int, section_id: int) -> Optional[str]:
        """
        Try to anchor a vision-found section number to a real element ID on that page.

        Priority:
        1) Exact text match for the section number (allow trailing punctuation).
        2) Numeric-like element between immediate neighbor section headers on that page.
        """
        import re

        elems_all = sorted(elements_by_page.get(page, []), key=lambda e: int(e.get("seq") or 0))
        if not elems_all:
            return None

        page_tag = f"{page:03d}"
        elems_by_side: Dict[str, List[Dict]] = {"L": [], "R": [], "": []}
        for e in elems_all:
            eid = str(e.get("id") or "")
            if eid.startswith(page_tag + "L-"):
                elems_by_side["L"].append(e)
            elif eid.startswith(page_tag + "R-"):
                elems_by_side["R"].append(e)
            else:
                elems_by_side[""].append(e)

        # 1) Direct match: "48" / "48." / "48)" etc
        pat = re.compile(rf"^\s*{section_id}\s*[\.\)\:]?\s*$")
        direct_all = [e for e in elems_all if isinstance(e.get("text"), str) and pat.match(e["text"])]
        if direct_all:
            # Prefer the earliest occurrence in reading order.
            return direct_all[0].get("id")

        for side in ["L", "R", ""]:
            elems = elems_by_side[side]
            # Build id->seq for this side (fallback to 0)
            id_to_seq = {e.get("id"): int(e.get("seq") or 0) for e in elems if e.get("id")}

            # Find immediate neighbor boundaries ON THIS PAGE (prefer same side when possible)
            page_bounds = [b for b in existing_boundaries if int(b.get("start_page") or -1) == page]
            if side:
                page_bounds = [
                    b for b in page_bounds
                    if str(b.get("start_element_id") or "").startswith(page_tag + side + "-")
                ]
            left = [b for b in page_bounds if int(b["section_id"]) < section_id]
            right = [b for b in page_bounds if int(b["section_id"]) > section_id]
            left_b = max(left, key=lambda b: int(b["section_id"])) if left else None
            right_b = min(right, key=lambda b: int(b["section_id"])) if right else None

            left_seq = id_to_seq.get(left_b.get("start_element_id")) if left_b else None
            right_seq = id_to_seq.get(right_b.get("start_element_id")) if right_b else None

            # 2) Pick a numeric-like element between neighbor header elements.
            # This catches OCR slips like section "80" being read as standalone "0".
            numeric_like = []
            for e in elems:
                txt = (e.get("text") or "").strip()
                if not txt:
                    continue
                if not re.fullmatch(r"\d{1,3}\.?", txt):
                    continue
                # Avoid anchoring to already-classified Section-header elements for a different number
                # (e.g., running-header false positives like "197" on page 27L).
                if e.get("content_type") == "Section-header":
                    continue
                numeric_like.append(e)

            if left_seq is not None and right_seq is not None and left_seq < right_seq:
                between = [
                    e for e in numeric_like
                    if left_seq < int(e.get("seq") or 0) < right_seq
                ]
                if between:
                    return between[0].get("id")

        return None
    
    # Extract boundaries from escalation data
    boundaries = []
    missing_set = set(missing_sections)
    
    for page, page_data in escalation_data.items():
        for section_id_str, section_data in page_data.get("sections", {}).items():
            section_id = int(section_id_str)
            
            # Add ANY section found by vision that we don't already have
            # (not just ones in the missing list - vision might find sections
            # we didn't know were missing due to page estimation errors)
            if section_id not in already_detected:
                anchored_id = _anchor_element_id(page=page, section_id=section_id)
                if not anchored_id or anchored_id not in existing_element_ids:
                    raise RuntimeError(
                        f"Vision escalation found section {section_id} on page {page} "
                        f"but could not anchor to a real element id. "
                        f"Anchored={anchored_id!r}."
                    )
                boundaries.append({
                    'section_id': str(section_id),
                    'start_element_id': anchored_id,
                    'start_page': page,
                    'confidence': 0.99,
                    'method': 'vision_escalation',
                    'source': 'escalation_cache',
                    'header_position': section_data.get('header_position', 'unknown')
                })
    
    return boundaries


def escalate_pages_replace_boundaries(
    pages: List[int],
    escalation_cache: EscalationCache,
    triggered_by: str,
    trigger_reason: str,
    existing_boundaries: List[Dict],
    elements_by_page: Dict[int, List[Dict]],
) -> List[Dict]:
    """
    Escalate specific pages and return FULL boundary replacements for those pages.
    Unlike missing-section escalation, this replaces existing boundaries on the page.
    """
    escalation_data = escalation_cache.request_escalation(
        pages=pages,
        triggered_by=triggered_by,
        trigger_reason=trigger_reason
    )

    existing_element_ids = {e.get("id") for elems in elements_by_page.values() for e in elems if e.get("id")}

    def _anchor_element_id(page: int, section_id: int) -> Optional[str]:
        import re

        elems_all = sorted(elements_by_page.get(page, []), key=lambda e: int(e.get("seq") or 0))
        if not elems_all:
            return None

        page_tag = f"{page:03d}"
        elems_by_side: Dict[str, List[Dict]] = {"L": [], "R": [], "": []}
        for e in elems_all:
            eid = str(e.get("id") or "")
            if eid.startswith(page_tag + "L-"):
                elems_by_side["L"].append(e)
            elif eid.startswith(page_tag + "R-"):
                elems_by_side["R"].append(e)
            else:
                elems_by_side[""].append(e)

        pat = re.compile(rf"^\s*{section_id}\s*[\.\)\:]?\s*$")
        direct_all = [e for e in elems_all if isinstance(e.get("text"), str) and pat.match(e["text"])]
        if direct_all:
            return direct_all[0].get("id")

        for side in ["L", "R", ""]:
            elems = elems_by_side[side]
            id_to_seq = {e.get("id"): int(e.get("seq") or 0) for e in elems if e.get("id")}

            page_bounds = [b for b in existing_boundaries if int(b.get("start_page") or -1) == page]
            if side:
                page_bounds = [
                    b for b in page_bounds
                    if str(b.get("start_element_id") or "").startswith(page_tag + side + "-")
                ]
            left = [b for b in page_bounds if int(b["section_id"]) < section_id]
            right = [b for b in page_bounds if int(b["section_id"]) > section_id]
            left_b = max(left, key=lambda b: int(b["section_id"])) if left else None
            right_b = min(right, key=lambda b: int(b["section_id"])) if right else None

            left_seq = id_to_seq.get(left_b.get("start_element_id")) if left_b else None
            right_seq = id_to_seq.get(right_b.get("start_element_id")) if right_b else None

            numeric_like = []
            for e in elems:
                txt = (e.get("text") or "").strip()
                if not txt:
                    continue
                if not re.fullmatch(r"\d{1,3}\.?", txt):
                    continue
                if e.get("content_type") == "Section-header":
                    continue
                numeric_like.append(e)

            if left_seq is not None and right_seq is not None and left_seq < right_seq:
                between = [
                    e for e in numeric_like
                    if left_seq < int(e.get("seq") or 0) < right_seq
                ]
                if between:
                    return between[0].get("id")

        return None

    boundaries = []
    for page, page_data in escalation_data.items():
        for section_id_str, section_data in page_data.get("sections", {}).items():
            section_id = int(section_id_str)
            anchored_id = _anchor_element_id(page=page, section_id=section_id)
            if not anchored_id or anchored_id not in existing_element_ids:
                raise RuntimeError(
                    f"Vision escalation found section {section_id} on page {page} "
                    f"but could not anchor to a real element id. Anchored={anchored_id!r}."
                )
            boundaries.append({
                'section_id': str(section_id),
                'start_element_id': anchored_id,
                'start_page': page,
                'confidence': 0.99,
                'method': 'vision_escalation_ordering',
                'source': 'escalation_cache',
                'header_position': section_data.get('header_position', 'unknown')
            })

    return boundaries


def main():
    parser = argparse.ArgumentParser(
        description='Code-first section boundary detection with targeted escalation'
    )
    parser.add_argument('--inputs', nargs='*', help='Driver-provided inputs (elements_core_typed.jsonl)')
    parser.add_argument('--pages', help='Alias for --inputs (driver compatibility)')
    parser.add_argument('--elements', help='Alias for --inputs (driver compatibility)')
    parser.add_argument('--out', required=True, help='Output section_boundary_v1 JSONL')
    parser.add_argument('--run-id', '--run_id', dest='run_id', help='Run ID for logging')
    parser.add_argument('--min-section', '--min_section', type=int, default=1, dest='min_section',
                       help='Minimum section number')
    parser.add_argument('--max-section', '--max_section', type=int, default=400, dest='max_section',
                       help='Maximum section number')
    parser.add_argument('--target-coverage', '--target_coverage', type=float, default=0.95, 
                       dest='target_coverage', help='Target coverage ratio (0.95 = 95%%)')
    parser.add_argument('--max-escalation-pages', '--max_escalation_pages', type=int, default=30,
                       dest='max_escalation_pages', help='Max pages to escalate with AI')
    parser.add_argument('--max-ordering-pages', '--max_ordering_pages', type=int, default=15,
                       dest='max_ordering_pages', help='Max pages to escalate for ordering/span issues')
    parser.add_argument('--min-span-words', '--min_span_words', type=int, default=5,
                       dest='min_span_words', help='Minimum words required in a section span')
    parser.add_argument('--min-span-alpha', '--min_span_alpha', type=float, default=0.2,
                       dest='min_span_alpha', help='Minimum alpha ratio required in a section span')
    parser.add_argument('--min-span-chars', '--min_span_chars', type=int, default=20,
                       dest='min_span_chars', help='Minimum alphabetic chars required in a section span')
    parser.add_argument('--no-fail-on-ordering-conflict', '--no_fail_on_ordering_conflict',
                       dest='fail_on_ordering_conflict', action='store_false', default=True,
                       help='Do not fail if ordering/span issues remain after escalation')
    parser.add_argument('--ordering-pages', '--ordering_pages', dest='ordering_pages',
                       help='Comma-separated page keys to escalate for ordering/span issues (e.g., 28L,33L)')
    parser.add_argument('--model', default='gpt-4.1-mini', help='LLM model for gap analysis')
    parser.add_argument('--escalation-model', '--escalation_model', dest='escalation_model',
                       default='gpt-5', help='Stronger LLM for escalation')
    parser.add_argument('--images-dir', '--images_dir', dest='images_dir',
                       help='Images directory (defaults to run_dir/../images)')
    parser.add_argument('--coarse-segments', '--coarse_segments', dest='coarse_segments',
                       help='Path to coarse_segments.json (gameplay/frontmatter/endmatter ranges)')
    parser.add_argument('--state-file', dest='state_file', help='Driver state file (for progress/state updates)')
    parser.add_argument('--progress-file', dest='progress_file', help='Driver progress file (for progress/state updates)')

    args = parser.parse_args()
    
    logger = ProgressLogger(
        state_path=args.state_file,
        progress_path=args.progress_file,
        run_id=args.run_id,
    )
    
    # Get input path (support multiple aliases for driver compatibility)
    input_path = None
    if args.inputs:
        input_path = args.inputs[0] if isinstance(args.inputs, list) else args.inputs
    elif args.pages:
        input_path = args.pages
    elif args.elements:
        input_path = args.elements
    if not input_path:
        raise ValueError("No input path provided (use --inputs, --pages, or --elements)")
    
    # Determine run directory and images directory
    run_dir = Path(args.out).parent
    run_root = run_dir.parent
    images_dir = _resolve_images_dir(run_root=run_root, explicit=args.images_dir)

    # Initialize escalation cache
    escalation_cache = EscalationCache(
        run_dir=run_dir,
        images_dir=images_dir,
        model=args.escalation_model,
        logger=logger
    )
    logger.log('load', 'running', message=f'Using images_dir={images_dir}')
    
    logger.log('load', 'running', message=f'Loading {input_path}')
    elements = list(read_jsonl(input_path))
    logger.log('load', 'done', message=f'Loaded {len(elements)} elements')
    elements_by_id = {e.get("id"): e for e in elements if e.get("id")}

    # Load coarse segmentation (gameplay/frontmatter/endmatter ranges)
    coarse_segments = None
    gameplay_pages = None
    if args.coarse_segments:
        logger.log('load', 'running', message=f'Loading coarse segments from {args.coarse_segments}')
        import json
        with open(args.coarse_segments) as f:
            coarse_segments = json.load(f)
        gameplay_pages = coarse_segments.get('gameplay_pages')
        if gameplay_pages:
            logger.log('load', 'done', message=f'Gameplay pages: {gameplay_pages[0]} to {gameplay_pages[1]}')
        else:
            logger.log('load', 'done', message='No gameplay_pages range in coarse segments')

    # Filter elements to ONLY gameplay pages (exclude frontmatter/endmatter)
    # This is critical: we should NEVER process frontmatter or endmatter sections
    if gameplay_pages:
        logger.log('filter', 'running', message='Filtering elements to gameplay pages only')
        gameplay_elements = filter_elements_to_gameplay(elements, gameplay_pages)
        logger.log('filter', 'done', message=f'Filtered to {len(gameplay_elements)} gameplay elements (from {len(elements)} total)')
        elements = gameplay_elements

    # ========================================
    # STAGE 1: Code-first baseline (FREE)
    # ========================================
    logger.log('baseline', 'running', message='Code-first filtering for Section-header elements')

    boundaries = filter_section_headers(elements, args.min_section, args.max_section, gameplay_pages)
    
    logger.log(
        'baseline',
        'done',
        message=f'Code filter found {len(boundaries)} boundaries (FREE, instant)',
        artifact=args.out
    )
    
    # ========================================
    # STAGE 2: Ordering/span feasibility checks (pre-extraction guard)
    # ========================================
    elements_sorted, element_sequence, id_to_index, id_to_seq = _build_element_sequence(elements)
    ordering_conflicts = detect_ordering_conflicts(boundaries, id_to_seq)
    span_issues = detect_span_issues(
        boundaries,
        id_to_index=id_to_index,
        elements_sorted=elements_sorted,
        min_words=args.min_span_words,
        min_alpha_ratio=args.min_span_alpha,
        min_alpha_chars=args.min_span_chars,
    )
    report_path = Path(args.out).with_suffix(".ordering_report.json")
    report = {
        "schema_version": "boundary_order_guard_v1",
        "run_id": args.run_id,
        "ordering_conflicts": ordering_conflicts,
        "span_issues": span_issues,
        "ordering_conflicts_after": None,
        "span_issues_after": None,
        "flagged_pages": [],
        "repaired_boundaries": 0,
    }

    if ordering_conflicts or span_issues:
        logger.log(
            'validate',
            'running',
            message=f'Ordering/span issues detected: {len(ordering_conflicts)} ordering pages, '
                    f'{len(span_issues)} span pages',
            artifact=args.out
        )

        # Build per-page escalation list (ordering/span issues first)
        ordering_pages = sorted(set(ordering_conflicts.keys()))
        span_pages = sorted(set(span_issues.keys()))
        flagged_pages = []
        for p in ordering_pages + span_pages:
            if p not in flagged_pages:
                flagged_pages.append(p)

        if args.ordering_pages:
            requested = [p.strip() for p in args.ordering_pages.split(",") if p.strip()]
            flagged_pages = [p for p in requested if p in ordering_conflicts or p in span_issues]

        # Cap to avoid runaway escalation
        flagged_pages = flagged_pages[:args.max_ordering_pages]
        report["flagged_pages"] = flagged_pages
        if flagged_pages:
            logger.log(
                'escalate',
                'running',
                message=f'Escalating {len(flagged_pages)} pages for ordering/span issues (cap: {args.max_ordering_pages})',
                artifact=args.out
            )

            def _page_num_from_key(k: str) -> int:
                return int("".join(ch for ch in k if ch.isdigit()) or 0)

            flagged_page_nums = []
            for k in flagged_pages:
                num = _page_num_from_key(k)
                if num and num not in flagged_page_nums:
                    flagged_page_nums.append(num)

            elements_by_page: Dict[int, List[Dict]] = defaultdict(list)
            for e in elements:
                page = e.get("page")
                if isinstance(page, int):
                    elements_by_page[page].append(e)

            repaired = escalate_pages_replace_boundaries(
                pages=flagged_page_nums,
                escalation_cache=escalation_cache,
                triggered_by="detect_boundaries_code_first_v1",
                trigger_reason="ordering_or_empty_span",
                existing_boundaries=boundaries,
                elements_by_page=elements_by_page,
            )

            if repaired:
                repaired_sections = {b["section_id"] for b in repaired}
                boundaries = [
                    b for b in boundaries
                    if int(b.get("start_page") or -1) not in flagged_pages
                    and b.get("section_id") not in repaired_sections
                ]
                boundaries.extend(repaired)
                report["repaired_boundaries"] = len(repaired)

                # Re-validate sequential ordering after replacement
                boundaries = _validate_sequential_ordering(boundaries)

            logger.log(
                'escalate',
                'done',
                message=f'Repaired {len(repaired)} boundaries from ordering/span escalation',
                artifact=args.out
            )

        # Re-check ordering/span issues after escalation
        ordering_conflicts = detect_ordering_conflicts(boundaries, id_to_seq)
        span_issues = detect_span_issues(
            boundaries,
            id_to_index=id_to_index,
            elements_sorted=elements_sorted,
            min_words=args.min_span_words,
            min_alpha_ratio=args.min_span_alpha,
            min_alpha_chars=args.min_span_chars,
        )
        report["ordering_conflicts_after"] = ordering_conflicts
        report["span_issues_after"] = span_issues
        if (ordering_conflicts or span_issues) and args.fail_on_ordering_conflict:
            msg = (f'Ordering/span issues remain after escalation: '
                   f'{len(ordering_conflicts)} ordering pages, {len(span_issues)} span pages')
            logger.log('validate', 'failed', message=msg, artifact=args.out)
            raise SystemExit(msg)
    else:
        report["ordering_conflicts_after"] = ordering_conflicts
        report["span_issues_after"] = span_issues

    ensure_dir(str(report_path.parent))
    save_json(str(report_path), report)

    # ========================================
    # STAGE 3: Validate coverage
    # ========================================
    expected_total = args.max_section - args.min_section + 1
    target_count = int(expected_total * args.target_coverage)

    logger.log(
        'validate',
        'running',
        message=f'Coverage: {len(boundaries)}/{expected_total} ({len(boundaries)/expected_total:.1%}), target: {target_count} ({args.target_coverage:.0%})',
        artifact=args.out
    )

    if len(boundaries) >= target_count:
        logger.log(
            'validate',
            'done',
            message='✓ Target coverage met! No missing-section escalation needed.',
            artifact=args.out
        )
    else:
        logger.log(
            'validate',
            'running',
            message='Coverage below target; proceeding to missing-section escalation.',
            artifact=args.out
        )
    
    # ========================================
    # STAGE 3: Gap analysis
    # ========================================
    missing_sections = find_missing_sections(boundaries, args.min_section, args.max_section)
    
    logger.log(
        'gap_analysis',
        'running',
        message=f'Missing {len(missing_sections)} sections: {missing_sections[:10]}...',
        artifact=args.out
    )
    
    # Use smart bracket-constrained page estimation
    suspected_pages = estimate_pages_for_sections_smart(missing_sections, boundaries)
    
    logger.log(
        'gap_analysis',
        'running',
        message=f'Smart estimation: {len(missing_sections)} missing sections need {len(suspected_pages)} pages (using bracket constraints)',
        artifact=args.out
    )
    
    flagged_pages = suspected_pages[:args.max_escalation_pages]
    
    logger.log(
        'gap_analysis',
        'done',
        message=f'Flagged {len(flagged_pages)} pages for AI escalation (cap: {args.max_escalation_pages})',
        artifact=args.out
    )
    
    # ========================================
    # STAGE 4: Targeted vision escalation
    # ========================================
    logger.log(
        'escalate',
        'running',
        message=f'Escalating {len(flagged_pages)} pages with {args.escalation_model} (vision cache)',
        artifact=args.out
    )
    
    # Use escalation cache for all flagged pages
    elements_by_page: Dict[int, List[Dict]] = defaultdict(list)
    for e in elements:
        page = e.get("page")
        if isinstance(page, int):
            elements_by_page[page].append(e)

    discovered = escalate_with_vision_cache(
        pages=flagged_pages,
        missing_sections=missing_sections,
        escalation_cache=escalation_cache,
        triggered_by='detect_boundaries_code_first_v1',
        existing_boundaries=boundaries,
        elements_by_page=elements_by_page,
    )
    
    boundaries.extend(discovered)
    
    logger.log(
        'escalate',
        'done',
        message=f'Vision escalation found {len(discovered)} boundaries from {len(flagged_pages)} pages',
        artifact=args.out
    )
    
    # Annotate macro sections (frontmatter/gameplay/endmatter) for provenance.
    assign_macro_sections(boundaries, elements_by_id, coarse_segments)

    # ========================================
    # STAGE 5: Final validation
    # ========================================
    final_missing = find_missing_sections(boundaries, args.min_section, args.max_section)

    if len(boundaries) < target_count:
        # Check if we exhausted escalation attempts
        # We've exhausted attempts if we either:
        # 1. Scanned all suspected pages (flagged_pages == suspected_pages), or
        # 2. Hit the escalation cap (flagged_pages == max_escalation_pages)
        exhausted = (len(flagged_pages) == len(suspected_pages) or
                     len(flagged_pages) == args.max_escalation_pages)

        if exhausted:
            # We exhausted escalation - missing sections are likely not in source
            logger.log(
                'validate',
                'warning',
                message=f'⚠️  {len(boundaries)}/{expected_total} found. Exhausted escalation attempts ({len(flagged_pages)} pages). Suspected missing from source: {final_missing}',
                artifact=args.out
            )
            # Emit a run-root marker for downstream stages/validators.
            # This is explicit, append-only provenance that these section IDs could not be found even after escalation.
            try:
                unresolved_path = run_root / "unresolved_missing.json"
                if unresolved_path.exists():
                    # Append-only policy: never overwrite existing artifacts in the same run directory.
                    # If re-running in a reused run dir, emit a uniquely named artifact.
                    from datetime import datetime, timezone

                    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                    unresolved_path = run_root / f"unresolved_missing.{stamp}.json"

                with open(unresolved_path, "w", encoding="utf-8") as f:
                    json.dump([str(x) for x in final_missing], f, ensure_ascii=False, indent=2)
                logger.log(
                    'validate',
                    'warning',
                    message=f'Wrote {unresolved_path.name} ({len(final_missing)} ids)',
                    artifact=str(unresolved_path),
                )
            except Exception as e:
                logger.log(
                    'validate',
                    'warning',
                    message=f'Failed to write unresolved_missing.json: {e}',
                    artifact=str(run_root),
                )
            save_jsonl(args.out, boundaries)
            print(f'⚠️  Found {len(boundaries)}/{expected_total} boundaries ({len(boundaries)/expected_total:.1%})')
            print(f'  Baseline (code): {len(boundaries) - len(discovered)} boundaries (FREE)')
            print(f'  Escalation (AI): {len(flagged_pages)} pages scanned')
            print(f'  Exhausted escalation attempts (scanned all {len(flagged_pages)} suspected pages)')
            print(f'  Suspected missing from source: {final_missing}')
            print(f'  Note: These sections likely do not exist in the input document (missing/damaged pages)')
        else:
            # We didn't hit the cap - this is a real failure
            logger.log(
                'validate',
                'failed',
                message=f'FAILED: Only {len(boundaries)}/{expected_total} after {len(flagged_pages)} escalations. Missing: {final_missing[:20]}',
                artifact=args.out
            )
            # Save partial results for forensics
            save_jsonl(args.out, boundaries)
            raise Exception(
                f'Coverage target not met: {len(boundaries)}/{expected_total} '
                f'({len(boundaries)/expected_total:.1%}). '
                f'Missing {len(final_missing)} sections after {len(flagged_pages)} escalations.'
            )
    else:
        logger.log(
            'validate',
            'done',
            message=f'✓ Success! {len(boundaries)}/{expected_total} boundaries ({len(boundaries)/expected_total:.1%})',
            artifact=args.out
        )
        save_jsonl(args.out, boundaries)
        print(f'✓ Found {len(boundaries)}/{expected_total} boundaries ({len(boundaries)/expected_total:.1%})')
        print(f'  Baseline (code): {len(boundaries) - len(discovered)} boundaries (FREE)')
        print(f'  Escalation (AI): {len(flagged_pages)} pages scanned')


if __name__ == '__main__':
    main()
