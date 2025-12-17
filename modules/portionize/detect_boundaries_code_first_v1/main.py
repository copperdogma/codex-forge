#!/usr/bin/env python3
"""
Code-first section boundary detection with targeted AI escalation.

Follows AGENTS.md pattern: code → validate → targeted escalate → validate
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Optional, Any

from modules.common.utils import read_jsonl, save_jsonl, ProgressLogger
from modules.common.escalation_cache import EscalationCache


def filter_section_headers(elements: List[Dict], min_section: int, max_section: int) -> List[Dict]:
    """
    Code-first: Filter elements for Section-header with valid numbers.
    This is FREE, instant, and deterministic.
    
    CRITICAL: Applies multi-stage validation to eliminate false positives:
    1. Find section 1 to determine frontmatter boundary
    2. Filter frontmatter (BEFORE duplicate resolution to avoid losing valid instances)
    3. Page-level clustering (eliminate outliers on same page)
    4. Multi-page duplicate resolution (choose best instance)
    5. Sequential validation (enforce ordering)
"""
    candidates = []
    
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
        candidates.append({
            'section_id': str(section_num),
            'start_element_id': element_id,
            'start_page': page,
            'start_line_idx': elem.get('line_idx'),
            'confidence': 0.95,
            'method': 'code_filter',
            'source': 'content_type_classification'
        })
    
    # Find section 1 to determine frontmatter boundary (must happen early!)
    # CRITICAL: There may be multiple false positives for section 1 in frontmatter
    # We need to find the CORRECT section 1 (the one that would win duplicate resolution)
    # Strategy: Find the section 1 instance on the page with the best fit score
    # (i.e., the page with the most consecutive sections starting from 1)
    section_1_candidates = [b for b in candidates if int(b['section_id']) == 1]
    section_1_page = None
    
    if section_1_candidates:
        # For each section 1 candidate, calculate fit score (consecutive neighbors)
        best_section_1 = None
        best_score = -1
        
        for boundary in section_1_candidates:
            page = boundary['start_page']
            # Find all sections on this page
            page_sections = sorted([
                int(b['section_id']) for b in candidates 
                if b['start_page'] == page
            ])
            
            # Calculate fit: count consecutive sections starting from 1
            fit_score = 1  # Section 1 itself
            check_section = 1
            while check_section + 1 in page_sections:
                fit_score += 1
                check_section += 1
            
            if fit_score > best_score:
                best_score = fit_score
                best_section_1 = boundary
                section_1_page = page
        
        # If no good fit found, use the lowest page number (assumes earlier instances are false positives)
        if section_1_page is None:
            section_1_page = min(b['start_page'] for b in section_1_candidates)
    
    # STAGE 0: Filter frontmatter BEFORE duplicate resolution
    # This prevents valid instances from being lost when duplicate resolution
    # chooses a frontmatter instance that later gets filtered out
    if section_1_page is not None:
        candidates = [b for b in candidates if b['start_page'] >= section_1_page]
    
    # STAGE 1: Page-level clustering to eliminate outliers
    clustered = _filter_page_outliers(candidates)
    
    # STAGE 2: Multi-page duplicate resolution
    deduplicated = _resolve_duplicates(clustered)
    
    # STAGE 3: Sequential validation (now redundant frontmatter check, but keeps logic clean)
    validated = _validate_sequential_ordering(deduplicated)
    
    # Sort by section number
    validated.sort(key=lambda b: int(b['section_id']))
    
    return validated


def _filter_page_outliers(candidates: List[Dict]) -> List[Dict]:
    """
    Eliminate false positives using page-level clustering.
    
    Strategy: On each page, find the MAIN CLUSTER (largest group of consecutive sections).
    Outliers (sections with gap >5 from cluster) are likely false positives.
    
    Example:
        Page 39: [87, 96, 97, 98, 99]
        - Gap between 87 and 96 is 9 (large)
        - Main cluster: [96, 97, 98, 99]
        - Outlier: [87] ← false positive, eliminated
    """
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
        
        # Keep only the LARGEST cluster
        main_cluster_indices = max(clusters, key=len)
        for idx in main_cluster_indices:
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
        best_score = -1
        
        for boundary in boundaries:
            page = boundary['start_page']
            
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
            
            if fit_score > best_score:
                best_score = fit_score
                best_boundary = boundary
        
        deduplicated.append(best_boundary)
    
    return deduplicated


def _validate_sequential_ordering(candidates: List[Dict]) -> List[Dict]:
    """
    Eliminate false positives using sequential validation.
    
    Key insight: Fighting Fantasy sections are 100% in order.
    Section numbers MUST increase (roughly) with page numbers.
    
    Strategy:
    1. Find section 1 (the TRUE anchor point) - ignores intro/rules pages
    2. Start sequential validation from section 1's page
    3. Accept sections that continue the sequence
    4. Reject anything before section 1's page (front matter false positives)
    
    Example:
        Page 5-15: [17, 18, 10, 11, 2, 7] ✗ (intro/rules false positives)
        Page 16: [1, 2] ✓ (TRUE section 1 starts here)
        Page 17: [3, 4, 5] ✓ (continues sequence)
    """
    if not candidates:
        return []
    
    # Find section 1 (the TRUE anchor)
    section_1 = None
    section_1_page = None
    for boundary in candidates:
        if int(boundary['section_id']) == 1:
            section_1 = boundary
            section_1_page = boundary['start_page']
            break
    
    if section_1 is None:
        # No section 1 found - fall back to accepting all (will escalate later)
        # But still apply basic sequential validation
        candidates.sort(key=lambda b: (b['start_page'], int(b['section_id'])))
        validated = []
        last_section = 0
        seen_sections = set()
        
        for boundary in candidates:
            sect = int(boundary['section_id'])
            if sect in seen_sections:
                continue
            if sect > last_section:
                validated.append(boundary)
                seen_sections.add(sect)
                last_section = sect
        return validated
    
    # Sort by page, then section number
    candidates.sort(key=lambda b: (b['start_page'], int(b['section_id'])))
    
    validated = []
    last_section = 0
    seen_sections = set()
    
    # Process candidates, starting from section 1's page
    last_page = section_1_page
    
    for boundary in candidates:
        page = boundary['start_page']
        sect = int(boundary['section_id'])
        
        # Reject anything before section 1's page (front matter)
        if page < section_1_page:
            continue
        
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
    existing_boundaries: List[Dict]
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
                boundaries.append({
                    'section_id': str(section_id),
                    'start_page': page,
                    'confidence': 0.99,
                    'method': 'vision_escalation',
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
    parser.add_argument('--model', default='gpt-4.1-mini', help='LLM model for gap analysis')
    parser.add_argument('--escalation-model', '--escalation_model', dest='escalation_model',
                       default='gpt-5', help='Stronger LLM for escalation')
    parser.add_argument('--images-dir', '--images_dir', dest='images_dir',
                       help='Images directory (defaults to run_dir/../images)')
    parser.add_argument('--state-file', dest='state_file', help='Driver state file (ignored)')
    parser.add_argument('--progress-file', dest='progress_file', help='Driver progress file (ignored)')
    
    args = parser.parse_args()
    
    logger = ProgressLogger(args.run_id, 'detect_boundaries_code_first_v1')
    
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
    images_dir = Path(args.images_dir) if args.images_dir else run_dir.parent / "images"
    
    # Initialize escalation cache
    escalation_cache = EscalationCache(
        run_dir=run_dir,
        images_dir=images_dir,
        model=args.escalation_model,
        logger=logger
    )
    
    logger.log('load', 'running', message=f'Loading {input_path}')
    elements = list(read_jsonl(input_path))
    logger.log('load', 'done', message=f'Loaded {len(elements)} elements')
    
    # ========================================
    # STAGE 1: Code-first baseline (FREE)
    # ========================================
    logger.log('baseline', 'running', message='Code-first filtering for Section-header elements')
    
    boundaries = filter_section_headers(elements, args.min_section, args.max_section)
    
    logger.log(
        'baseline',
        'done',
        message=f'Code filter found {len(boundaries)} boundaries (FREE, instant)',
        artifact=args.out
    )
    
    # ========================================
    # STAGE 2: Validate coverage
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
            message=f'✓ Target coverage met! No escalation needed.',
            artifact=args.out
        )
        save_jsonl(args.out, boundaries)
        print(f'✓ Found {len(boundaries)}/{expected_total} boundaries ({len(boundaries)/expected_total:.1%}) - target met!')
        return
    
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
    discovered = escalate_with_vision_cache(
        pages=flagged_pages,
        missing_sections=missing_sections,
        escalation_cache=escalation_cache,
        triggered_by='detect_boundaries_code_first_v1',
        existing_boundaries=boundaries
    )
    
    boundaries.extend(discovered)
    
    logger.log(
        'escalate',
        'done',
        message=f'Vision escalation found {len(discovered)} boundaries from {len(flagged_pages)} pages',
        artifact=args.out
    )
    
    # ========================================
    # STAGE 5: Final validation / fail
    # ========================================
    final_missing = find_missing_sections(boundaries, args.min_section, args.max_section)
    
    if len(boundaries) < target_count:
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
    
    logger.log(
        'validate',
        'done',
        message=f'✓ Success! {len(boundaries)}/{expected_total} boundaries ({len(boundaries)/expected_total:.1%})',
        artifact=args.out
    )
    
    save_jsonl(args.out, boundaries)
    print(f'✓ Found {len(boundaries)}/{expected_total} boundaries ({len(boundaries)/expected_total:.1%})')
    print(f'  Baseline (code): {len(boundaries) - len(flagged_pages)} boundaries (FREE)')
    print(f'  Escalation (AI): {len(flagged_pages)} pages scanned')


if __name__ == '__main__':
    main()

