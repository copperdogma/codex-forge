#!/usr/bin/env python3
"""
coarse_segment_ff_override_v1: FF-style override for gameplay start detection.

FF-specific rule: "Gameplay starts with BACKGROUND header"
This module searches for the BACKGROUND keyword and provides hints for
overriding semantic/pattern boundaries when found.

Input: elements_core.jsonl (to search for BACKGROUND)
Optional: coarse_segments.json, pattern_regions.json
Output: ff_segment_hints.json
"""

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional

from modules.common.utils import read_jsonl, save_json


def find_background_page(elements: List[Dict[str, Any]]) -> Optional[int]:
    """
    Find the first page containing "BACKGROUND" as a header/title.
    
    Only matches BACKGROUND when it appears as:
    - A Title or Section-header content_type
    - AND is one of the first 3 elements on its page (likely a header)
    - OR has layout.y < 0.2 (at top of page)
    
    This avoids matching "BACKGROUND" in body text like "ADVENTURE SHEET | | BACKGROUND"
    (which is in the TOC on page 5).
    
    Args:
        elements: List of elements to search (should be elements_core_typed.jsonl with content_type)
        
    Returns:
        Page number where BACKGROUND header is found, or None if not found
    """
    background_pattern = re.compile(r'^\s*BACKGROUND\s*$', re.IGNORECASE)
    
    # Group elements by page to check position within page
    elements_by_page: Dict[int, List[Dict[str, Any]]] = {}
    for elem in elements:
        page = elem.get('page')
        if page and isinstance(page, int):
            if page not in elements_by_page:
                elements_by_page[page] = []
            elements_by_page[page].append(elem)
    
    # Sort pages and check each one
    for page in sorted(elements_by_page.keys()):
        page_elements = sorted(elements_by_page[page], key=lambda e: e.get('seq', 999))
        
        # Check first 3 elements on this page
        for i, elem in enumerate(page_elements[:3]):
            text = elem.get('text', '').strip()
            if not text:
                continue
            
            # Only match if text is exactly "BACKGROUND" (standalone header)
            if not background_pattern.match(text):
                continue
            
            # Check if this is classified as a header
            content_type = elem.get('content_type')
            if content_type in ('Title', 'Section-header'):
                # Also check layout position if available
                layout = elem.get('layout', {})
                layout_y = layout.get('y') if isinstance(layout, dict) else None
                
                # If layout.y is available, ensure it's at top of page (y < 0.2) or middle is OK if first element
                if layout_y is not None:
                    if layout_y < 0.2:  # At top of page - definitely a header
                        return page
                    elif i == 0 and layout_y < 0.5:  # First element and not too far down - likely header
                        return page
                    # If y > 0.5, it's likely not a header (like page 5 TOC entry)
                else:
                    # No layout data - trust content_type and position (first few elements)
                    return page
    
    return None


def load_coarse_segments(path: Optional[str]) -> Optional[Dict[str, Any]]:
    """Load coarse_segments.json if provided."""
    if not path:
        return None
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"[coarse_segment_ff_override_v1] Warning: Failed to load coarse_segments: {e}")
        return None


def load_pattern_regions(path: Optional[str]) -> Optional[Dict[str, Any]]:
    """Load pattern_regions.json if provided."""
    if not path:
        return None
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"[coarse_segment_ff_override_v1] Warning: Failed to load pattern_regions: {e}")
        return None


def generate_ff_hints(
    background_page: Optional[int],
    coarse_segments: Optional[Dict[str, Any]] = None,
    pattern_regions: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Generate FF segment hints based on BACKGROUND detection.
    
    Args:
        background_page: Page number where BACKGROUND is found (or None)
        coarse_segments: Optional semantic segments
        pattern_regions: Optional pattern regions
        
    Returns:
        Dict with gameplay_start_page, override_applied, and notes
    """
    result = {
        'schema_version': 'ff_segment_hints_v1',
        'module_id': 'coarse_segment_ff_override_v1',
        'background_found': background_page is not None,
        'background_page': background_page,
        'gameplay_start_page': None,
        'override_applied': False,
        'notes': ''
    }
    
    if background_page is None:
        result['notes'] = 'BACKGROUND keyword not found. No override applied.'
        return result
    
    # Set gameplay start at BACKGROUND page (or page - 1 if needed)
    # Typically BACKGROUND appears on the first gameplay page, so use it directly
    gameplay_start = background_page
    
    # Check if this differs from semantic segments
    if coarse_segments:
        semantic_start = None
        gameplay_pages = coarse_segments.get('gameplay_pages')
        if gameplay_pages and isinstance(gameplay_pages, list) and len(gameplay_pages) >= 2:
            semantic_start = gameplay_pages[0]
        
        if semantic_start and semantic_start != gameplay_start:
            result['override_applied'] = True
            result['notes'] = (
                f'BACKGROUND found on page {background_page}. '
                f'Semantic segmenter suggested gameplay start at page {semantic_start}. '
                f'Override: gameplay starts at page {gameplay_start}.'
            )
        else:
            result['notes'] = (
                f'BACKGROUND found on page {background_page}. '
                f'Matches semantic segmenter (gameplay start: {semantic_start}).'
            )
    else:
        result['notes'] = f'BACKGROUND found on page {background_page}. No semantic segments to compare.'
    
    result['gameplay_start_page'] = gameplay_start
    return result


def main():
    parser = argparse.ArgumentParser(
        description='FF-style override: Detect gameplay start via BACKGROUND keyword'
    )
    parser.add_argument('--inputs', help='Path to elements_core.jsonl')
    parser.add_argument('--pages', help='Alias for --inputs (driver compatibility)')
    parser.add_argument('--coarse-segments', dest='coarse_segments', 
                       help='Optional path to coarse_segments.json')
    parser.add_argument('--coarse_segments', dest='coarse_segments',
                       help=argparse.SUPPRESS)  # alias for driver
    parser.add_argument('--pattern-regions', dest='pattern_regions',
                       help='Optional path to pattern_regions.json')
    parser.add_argument('--pattern_regions', dest='pattern_regions',
                       help=argparse.SUPPRESS)  # alias for driver
    parser.add_argument('--out', required=True, help='Path to output ff_segment_hints.json')
    parser.add_argument('--state-file', help='State file path (driver compatibility, unused)')
    parser.add_argument('--progress-file', help='Progress file path (driver compatibility, unused)')
    parser.add_argument('--run-id', help='Run ID (driver compatibility, unused)')
    args = parser.parse_args()
    
    # Handle driver input aliases
    inputs_path = args.pages or args.inputs
    if not inputs_path:
        parser.error("Missing --inputs (or --pages) input")
    
    # Load elements
    elements = list(read_jsonl(inputs_path))
    
    # Find BACKGROUND page
    background_page = find_background_page(elements)
    
    # Load optional inputs
    coarse_segments = load_coarse_segments(args.coarse_segments)
    pattern_regions = load_pattern_regions(args.pattern_regions)
    
    # Generate hints
    result = generate_ff_hints(background_page, coarse_segments, pattern_regions)
    
    # Save output
    save_json(args.out, result)
    
    if background_page:
        print(f"✅ BACKGROUND found on page {background_page}")
        print(f"   Gameplay start: page {result['gameplay_start_page']}")
        if result['override_applied']:
            print(f"   ⚠️  Override applied (differs from semantic segments)")
    else:
        print("⚠️  BACKGROUND keyword not found. No override applied.")


if __name__ == '__main__':
    main()

