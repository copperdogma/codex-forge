#!/usr/bin/env python3
"""
coarse_segment_patterns_v1: Pattern-based header/footer region detection.

Detects regions with consistent header/footer patterns (e.g., bottom page numbers,
top section ranges). Pattern regions are independent of semantic regions
(frontmatter/gameplay/endmatter) and can overlap.

Input: elements_core_typed.jsonl (with content_type classifications)
Output: pattern_regions.json
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Any

from modules.common.utils import read_jsonl, save_json


def detect_pattern_regions(elements: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Detect pattern regions based on header/footer classifications.
    
    Args:
        elements: List of elements with content_type classifications
        
    Returns:
        Dict with schema_version, total_pages, and regions list
    """
    # Collect page statistics
    page_stats = defaultdict(lambda: {'has_header': False, 'has_footer': False})
    total_pages = set()
    
    for elem in elements:
        page = elem.get('page')
        if page is None:
            continue
        total_pages.add(page)
        content_type = elem.get('content_type')
        
        if content_type == 'Page-header':
            page_stats[page]['has_header'] = True
        elif content_type == 'Page-footer':
            page_stats[page]['has_footer'] = True
    
    total_pages = sorted(total_pages)
    if not total_pages:
        return {
            'schema_version': 'pattern_regions_v1',
            'module_id': 'coarse_segment_patterns_v1',
            'total_pages': 0,
            'regions': []
        }
    
    # Cluster consecutive pages with same pattern into regions
    regions = []
    current_region = None
    
    for page in total_pages:
        stats = page_stats[page]
        has_header = stats['has_header']
        has_footer = stats['has_footer']
        
        # Determine pattern for this page
        if has_footer and not has_header:
            pattern = 'bottom_page_numbers'
        elif has_header and not has_footer:
            pattern = 'top_section_ranges'  # Could distinguish top_running_headers later
        elif has_header and has_footer:
            pattern = 'mixed'
        else:
            pattern = 'no_pattern'
        
        # Start new region or extend current
        if current_region is None:
            current_region = {
                'start_page': page,
                'end_page': page,
                'pattern': pattern,
                'header_count': 0,
                'footer_count': 0,
            }
        elif current_region['pattern'] == pattern:
            # Extend region (same pattern continues)
            current_region['end_page'] = page
        else:
            # Pattern changed - finalize current region and start new
            total_pages_in_region = current_region['end_page'] - current_region['start_page'] + 1
            regions.append({
                'start_page': current_region['start_page'],
                'end_page': current_region['end_page'],
                'pattern_style': current_region['pattern'],
                'description': _get_pattern_description(current_region['pattern']),
                'confidence': _calculate_confidence(
                    current_region['pattern'],
                    current_region['header_count'],
                    current_region['footer_count'],
                    total_pages_in_region
                ),
                'pattern_evidence': {
                    'page_footers': current_region['footer_count'],
                    'page_headers': current_region['header_count'],
                    'total_pages_in_region': total_pages_in_region
                }
            })
            current_region = {
                'start_page': page,
                'end_page': page,
                'pattern': pattern,
                'header_count': 0,
                'footer_count': 0,
            }
        
        # Count headers/footers in current region
        if has_header:
            current_region['header_count'] += 1
        if has_footer:
            current_region['footer_count'] += 1
    
    # Add last region
    if current_region:
        total_pages_in_region = current_region['end_page'] - current_region['start_page'] + 1
        regions.append({
            'start_page': current_region['start_page'],
            'end_page': current_region['end_page'],
            'pattern_style': current_region['pattern'],
            'description': _get_pattern_description(current_region['pattern']),
            'confidence': _calculate_confidence(
                current_region['pattern'],
                current_region['header_count'],
                current_region['footer_count'],
                total_pages_in_region
            ),
            'pattern_evidence': {
                'page_footers': current_region['footer_count'],
                'page_headers': current_region['header_count'],
                'total_pages_in_region': total_pages_in_region
            }
        })
    
    return {
        'schema_version': 'pattern_regions_v1',
        'module_id': 'coarse_segment_patterns_v1',
        'total_pages': len(total_pages),
        'regions': regions
    }


def _get_pattern_description(pattern_style: str) -> str:
    """Get description for pattern style."""
    descriptions = {
        'bottom_page_numbers': 'Page numbers consistently at bottom corners',
        'top_section_ranges': 'Section ranges consistently at top corners',
        'top_running_headers': 'Running headers consistently at top corners',
        'no_pattern': 'No clear header/footer pattern',
        'mixed': 'Multiple patterns present (headers and footers)'
    }
    return descriptions.get(pattern_style, 'Unknown pattern')


def _calculate_confidence(
    pattern: str,
    header_count: int,
    footer_count: int,
    total_pages: int
) -> float:
    """
    Calculate confidence score for a pattern region.
    
    High (0.9+): Consistent pattern across most pages
    Medium (0.7-0.9): Pattern present but some gaps
    Low (0.5-0.7): Inconsistent or mixed patterns
    Very low (<0.5): No clear pattern
    """
    if total_pages == 0:
        return 0.0
    
    if pattern == 'mixed':
        return 0.5
    
    if pattern == 'no_pattern':
        return 0.5
    
    # Calculate consistency ratio
    if pattern in ('bottom_page_numbers', 'top_section_ranges', 'top_running_headers'):
        if pattern == 'bottom_page_numbers':
            consistency = footer_count / total_pages
        else:  # top_section_ranges or top_running_headers
            consistency = header_count / total_pages
        
        # Scale to confidence: 1.0 consistency -> 0.95 confidence, 0.5 consistency -> 0.7 confidence
        confidence = 0.5 + (consistency * 0.45)
        return min(0.95, max(0.5, confidence))
    
    return 0.5


def main():
    parser = argparse.ArgumentParser(description='Detect header/footer pattern regions')
    parser.add_argument('--inputs', help='Path to elements_core_typed.jsonl')
    parser.add_argument('--pages', help='Alias for --inputs (driver compatibility)')
    parser.add_argument('--out', required=True, help='Path to output pattern_regions.json')
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
    
    # Detect pattern regions
    result = detect_pattern_regions(elements)
    
    # Save output
    save_json(args.out, result)
    
    print(f"Detected {len(result['regions'])} pattern regions across {result['total_pages']} pages")


if __name__ == '__main__':
    main()


