#!/usr/bin/env python3
"""
coarse_segment_merge_v1: Merge semantic and pattern segmenters.

Combines results from:
- coarse_segment_v1 (semantic: frontmatter/gameplay/endmatter)
- coarse_segment_patterns_v1 (pattern: header/footer style regions)
- coarse_segment_ff_override_v1 (FF override: BACKGROUND rule)

Outputs refined segment boundaries with evidence from all sources.
"""

import argparse
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

from modules.common.utils import save_json


def load_json(path: str) -> Optional[Dict[str, Any]]:
    """Load JSON file."""
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"[coarse_segment_merge_v1] Warning: Failed to load {path}: {e}")
        return None


def find_pattern_transition(
    pattern_regions: List[Dict[str, Any]],
    target_page: int
) -> Optional[Tuple[int, str, str]]:
    """
    Find pattern transition near target page.
    
    Returns:
        (page, from_pattern, to_pattern) if transition found, else None
    """
    for i, region in enumerate(pattern_regions):
        start = region['start_page']
        end = region['end_page']
        
        # Check if target page is near this region boundary
        if abs(start - target_page) <= 2 or abs(end - target_page) <= 2:
            if i > 0:
                prev_region = pattern_regions[i - 1]
                return (start, prev_region['pattern_style'], region['pattern_style'])
            if i < len(pattern_regions) - 1:
                next_region = pattern_regions[i + 1]
                return (end + 1, region['pattern_style'], next_region['pattern_style'])
    
    return None


def merge_segments(
    coarse_segments: Dict[str, Any],
    pattern_regions: Dict[str, Any],
    ff_hints: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Merge semantic segments, pattern regions, and FF override hints.
    
    Strategy:
    1. FF override takes precedence (if BACKGROUND found)
    2. Use semantic segments as base
    3. Refine boundaries using pattern transitions
    4. Document evidence from all sources
    """
    result = {
        'schema_version': 'merged_segments_v1',
        'module_id': 'coarse_segment_merge_v1',
        'frontmatter_pages': None,
        'gameplay_pages': None,
        'endmatter_pages': None,
        'override_applied': False,
        'pattern_evidence': {},
        'notes': []
    }
    
    # Get semantic segments
    semantic_frontmatter = coarse_segments.get('frontmatter_pages', [])
    semantic_gameplay = coarse_segments.get('gameplay_pages', [])
    semantic_endmatter = coarse_segments.get('endmatter_pages')
    
    # Get pattern regions
    pattern_regions_list = pattern_regions.get('regions', [])
    
    # Check FF override first (takes precedence)
    if ff_hints and ff_hints.get('background_found'):
        gameplay_start = ff_hints.get('gameplay_start_page')
        if gameplay_start:
            result['override_applied'] = True
            result['notes'].append(
                f"FF override: BACKGROUND found on page {gameplay_start}, "
                f"overriding semantic gameplay start at {semantic_gameplay[0] if semantic_gameplay else 'unknown'}"
            )
            
            # Use FF override for gameplay start
            frontmatter_end = gameplay_start - 1
            result['frontmatter_pages'] = [1, frontmatter_end]
            result['gameplay_pages'] = [gameplay_start, semantic_gameplay[1] if semantic_gameplay else gameplay_start + 100]
            
            # Keep endmatter from semantic (or infer)
            if semantic_endmatter:
                result['endmatter_pages'] = semantic_endmatter
            else:
                # Infer endmatter: gameplay end + 1 to end of book
                gameplay_end = result['gameplay_pages'][1]
                total_pages = pattern_regions.get('total_pages', 113)
                if gameplay_end < total_pages:
                    result['endmatter_pages'] = [gameplay_end + 1, total_pages]
            
            # Document pattern evidence
            transition = find_pattern_transition(pattern_regions_list, gameplay_start)
            if transition:
                result['pattern_evidence']['gameplay_start'] = {
                    'page': transition[0],
                    'from_pattern': transition[1],
                    'to_pattern': transition[2]
                }
            
            return result
    
    # No FF override - use semantic segments as base, refine with patterns
    result['frontmatter_pages'] = semantic_frontmatter
    result['gameplay_pages'] = semantic_gameplay
    result['endmatter_pages'] = semantic_endmatter
    
    # Refine boundaries using pattern transitions
    if semantic_gameplay and len(semantic_gameplay) >= 2:
        gameplay_start = semantic_gameplay[0]
        transition = find_pattern_transition(pattern_regions_list, gameplay_start)
        if transition:
            result['pattern_evidence']['gameplay_start'] = {
                'page': transition[0],
                'from_pattern': transition[1],
                'to_pattern': transition[2]
            }
            result['notes'].append(
                f"Pattern transition near gameplay start: {transition[1]} → {transition[2]} at page {transition[0]}"
            )
    
    if semantic_endmatter and len(semantic_endmatter) >= 2:
        endmatter_start = semantic_endmatter[0]
        transition = find_pattern_transition(pattern_regions_list, endmatter_start)
        if transition:
            result['pattern_evidence']['endmatter_start'] = {
                'page': transition[0],
                'from_pattern': transition[1],
                'to_pattern': transition[2]
            }
            result['notes'].append(
                f"Pattern transition near endmatter start: {transition[1]} → {transition[2]} at page {transition[0]}"
            )
    
    return result


def main():
    parser = argparse.ArgumentParser(
        description='Merge semantic and pattern segmenters'
    )
    parser.add_argument('--coarse-segments', dest='coarse_segments', required=True,
                       help='Path to coarse_segments.json')
    parser.add_argument('--coarse_segments', dest='coarse_segments',
                       help=argparse.SUPPRESS)  # alias
    parser.add_argument('--pattern-regions', dest='pattern_regions', required=True,
                       help='Path to pattern_regions.json')
    parser.add_argument('--pattern_regions', dest='pattern_regions',
                       help=argparse.SUPPRESS)  # alias
    parser.add_argument('--ff-hints', dest='ff_hints',
                       help='Optional path to ff_segment_hints.json')
    parser.add_argument('--ff_hints', dest='ff_hints',
                       help=argparse.SUPPRESS)  # alias
    parser.add_argument('--out', required=True, help='Path to output merged_segments.json')
    parser.add_argument('--state-file', help='State file path (driver compatibility, unused)')
    parser.add_argument('--progress-file', help='Progress file path (driver compatibility, unused)')
    parser.add_argument('--run-id', help='Run ID (driver compatibility, unused)')
    args = parser.parse_args()
    
    # Load inputs
    coarse_segments = load_json(args.coarse_segments)
    pattern_regions = load_json(args.pattern_regions)
    ff_hints = load_json(args.ff_hints) if args.ff_hints else None
    
    if not coarse_segments:
        raise ValueError(f"Failed to load coarse_segments from {args.coarse_segments}")
    if not pattern_regions:
        raise ValueError(f"Failed to load pattern_regions from {args.pattern_regions}")
    
    # Merge segments
    result = merge_segments(coarse_segments, pattern_regions, ff_hints)
    
    # Save output
    save_json(args.out, result)
    
    print(f"✅ Merged segments:")
    print(f"   Frontmatter: {result['frontmatter_pages']}")
    print(f"   Gameplay: {result['gameplay_pages']}")
    print(f"   Endmatter: {result['endmatter_pages']}")
    if result['override_applied']:
        print(f"   ⚠️  FF override applied")
    if result['pattern_evidence']:
        print(f"   📊 Pattern evidence: {len(result['pattern_evidence'])} transitions found")


if __name__ == '__main__':
    main()


