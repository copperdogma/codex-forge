#!/usr/bin/env python3
"""
Trace a section ID through the entire pipeline to find where it appears/disappears.

Usage:
    python scripts/trace_section_pipeline.py --run-id <run_id> --section <section_number>
    python scripts/trace_section_pipeline.py --run-id ff-canonical --section 17
"""

#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.common.utils import read_jsonl


def find_in_elements(elements: List[Dict], section_id: int) -> List[Dict]:
    """Find all elements that mention section_id."""
    results = []
    section_str = str(section_id)
    
    for elem in elements:
        text = elem.get('text', '')
        content_type = elem.get('content_type', '')
        
        # Check if text contains the section number as standalone or in range
        if section_str in text:
            # Check if it's a standalone number (e.g., "17" not "117" or "17-18")
            import re
            # Match standalone number or at start/end of range
            pattern = r'\b' + re.escape(section_str) + r'\b'
            if re.search(pattern, text):
                results.append({
                    'element_id': elem.get('id'),
                    'page': elem.get('page'),
                    'seq': elem.get('seq'),
                    'text': text[:100],
                    'content_type': content_type,
                    'layout': elem.get('layout', {})
                })
    
    return results


def find_in_boundaries(boundaries: List[Dict], section_id: int) -> Optional[Dict]:
    """Find section in boundaries."""
    for boundary in boundaries:
        if str(boundary.get('section_id')) == str(section_id):
            return boundary
    return None


def find_in_portions(portions: List[Dict], section_id: int) -> Optional[Dict]:
    """Find section in portions."""
    for portion in portions:
        if str(portion.get('section_id')) == str(section_id):
            return portion
    return None


def trace_section(run_dir: Path, section_id: int) -> Dict[str, Any]:
    """Trace a section through the pipeline."""
    trace = {
        'section_id': section_id,
        'found_at_stages': [],
        'missing_at_stages': [],
        'evidence': {}
    }
    
    # Stage 1: elements_core_typed.jsonl
    elements_file = run_dir / '09_elements_content_type_v1' / 'elements_core_typed.jsonl'
    if elements_file.exists():
        elements = list(read_jsonl(str(elements_file)))
        matches = find_in_elements(elements, section_id)
        if matches:
            trace['found_at_stages'].append('elements_core_typed')
            trace['evidence']['elements'] = matches
        else:
            trace['missing_at_stages'].append('elements_core_typed')
    
    # Stage 2: section_boundaries_merged.jsonl
    boundaries_file = run_dir / '18_merge_boundaries_pref_v1' / 'section_boundaries_merged.jsonl'
    if boundaries_file.exists():
        boundaries = list(read_jsonl(str(boundaries_file)))
        boundary = find_in_boundaries(boundaries, section_id)
        if boundary:
            trace['found_at_stages'].append('section_boundaries_merged')
            trace['evidence']['boundary'] = {
                'start_page': boundary.get('start_page'),
                'start_element_id': boundary.get('start_element_id'),
                'end_page': boundary.get('end_page'),
                'end_element_id': boundary.get('end_element_id'),
                'confidence': boundary.get('confidence')
            }
        else:
            trace['missing_at_stages'].append('section_boundaries_merged')
    
    # Stage 3: portions_enriched_clean.jsonl
    portions_file = run_dir / '27_strip_section_numbers_v1' / 'portions_enriched_clean.jsonl'
    if portions_file.exists():
        portions = list(read_jsonl(str(portions_file)))
        portion = find_in_portions(portions, section_id)
        if portion:
            trace['found_at_stages'].append('portions_enriched_clean')
            trace['evidence']['portion'] = {
                'page': portion.get('page'),
                'text_length': len(portion.get('text', '')),
                'has_choices': len(portion.get('choices', [])) > 0
            }
        else:
            trace['missing_at_stages'].append('portions_enriched_clean')
    
    # Stage 4: gamebook.json
    gamebook_file = run_dir / 'gamebook.json'
    if gamebook_file.exists():
        with open(gamebook_file) as f:
            gamebook = json.load(f)
        sections = {s.get('id'): s for s in gamebook.get('sections', [])}
        if str(section_id) in sections:
            section = sections[str(section_id)]
            trace['found_at_stages'].append('gamebook')
            trace['evidence']['gamebook_section'] = {
                'has_text': bool(section.get('text')),
                'is_stub': section.get('text', '').strip() == '',
                'choice_count': len(section.get('choices', []))
            }
        else:
            trace['missing_at_stages'].append('gamebook')
    
    return trace


def print_trace(trace: Dict[str, Any]):
    """Print formatted trace results."""
    section_id = trace['section_id']
    print(f"\n{'='*70}")
    print(f"Section {section_id} Pipeline Trace")
    print(f"{'='*70}\n")
    
    print("✅ Found at stages:")
    for stage in trace['found_at_stages']:
        print(f"   - {stage}")
        if stage == 'elements_core_typed' and 'elements' in trace['evidence']:
            print(f"     Elements found: {len(trace['evidence']['elements'])}")
            for elem in trace['evidence']['elements'][:3]:  # Show first 3
                print(f"       Page {elem['page']}, seq {elem['seq']}: '{elem['text']}' ({elem['content_type']})")
        elif stage == 'section_boundaries_merged' and 'boundary' in trace['evidence']:
            b = trace['evidence']['boundary']
            print(f"     Start: page {b['start_page']}, element {b['start_element_id']}")
            print(f"     End: page {b['end_page']}, element {b['end_element_id']}")
            print(f"     Confidence: {b.get('confidence', 'N/A')}")
        elif stage == 'portions_enriched_clean' and 'portion' in trace['evidence']:
            p = trace['evidence']['portion']
            print(f"     Page: {p['page']}, Text length: {p['text_length']}, Choices: {p['has_choices']}")
        elif stage == 'gamebook' and 'gamebook_section' in trace['evidence']:
            gs = trace['evidence']['gamebook_section']
            stub_status = "STUB" if gs['is_stub'] else "HAS TEXT"
            print(f"     Status: {stub_status}, Choices: {gs['choice_count']}")
    
    if trace['missing_at_stages']:
        print("\n❌ Missing at stages:")
        for stage in trace['missing_at_stages']:
            print(f"   - {stage}")
        
        # Provide diagnostic guidance
        if 'elements_core_typed' in trace['missing_at_stages']:
            print("\n   → Section not found in elements - likely OCR issue or not present in source")
        elif 'section_boundaries_merged' in trace['missing_at_stages']:
            print("\n   → Section found in elements but missing from boundaries - boundary detection issue")
            if 'elements' in trace['evidence']:
                print(f"     Found {len(trace['evidence']['elements'])} elements mentioning section {section_id}")
        elif 'portions_enriched_clean' in trace['missing_at_stages']:
            print("\n   → Section has boundary but no portion - extraction issue")
            if 'boundary' in trace['evidence']:
                print(f"     Boundary exists: pages {trace['evidence']['boundary']['start_page']}-{trace['evidence']['boundary']['end_page']}")
        elif 'gamebook' in trace['missing_at_stages']:
            print("\n   → Section has portion but missing from gamebook - build/validation issue")
    
    print(f"\n{'='*70}\n")


def main():
    parser = argparse.ArgumentParser(description='Trace section through pipeline')
    parser.add_argument('--run-id', required=True, help='Run ID (e.g., ff-canonical)')
    parser.add_argument('--section', type=int, required=True, help='Section ID to trace')
    parser.add_argument('--run-dir', help='Override run directory path')
    args = parser.parse_args()
    
    # Determine run directory
    if args.run_dir:
        run_dir = Path(args.run_dir)
    else:
        run_dir = Path('output/runs') / args.run_id
    
    if not run_dir.exists():
        print(f"❌ Run directory not found: {run_dir}")
        return 1
    
    # Trace section
    trace = trace_section(run_dir, args.section)
    print_trace(trace)
    
    return 0


if __name__ == '__main__':
    exit(main())

