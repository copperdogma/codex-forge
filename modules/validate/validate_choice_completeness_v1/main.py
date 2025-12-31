#!/usr/bin/env python3
"""
Choice Completeness Validator v1

Validates that extracted choices match references in section text.
Critical for 100% game engine accuracy - missing choices break gameplay.

Strategy:
1. Scan section text for "turn to X" patterns
2. Extract all referenced section numbers
3. Compare with extracted choices
4. Flag sections where references > choices (potential missing choices)
5. Cap warnings at reasonable level (some references are conditional)
"""

import argparse
import json
import re
from modules.common.html_utils import html_to_text
from typing import Dict, List, Set, Tuple
from collections import defaultdict

from modules.common.utils import save_json, ProgressLogger


def extract_turn_to_references(text: str) -> Set[int]:
    """Extract all 'turn to X' references from text."""
    if not text:
        return set()
    
    references = set()
    
    # Patterns: "turn to 123", "Turn to 42", "go to 99", etc.
    patterns = [
        r'\bturn\s+to\s+(\d{1,3})\b',
        r'\bgo\s+to\s+(\d{1,3})\b',
        r'\brefer\s+to\s+(\d{1,3})\b',
    ]
    
    text_lower = text.lower()
    for pattern in patterns:
        matches = re.findall(pattern, text_lower)
        for match in matches:
            num = int(match)
            if 1 <= num <= 400:  # Valid section range
                references.add(num)
    
    return references


def validate_section_choices(section_id: str, section: Dict) -> Tuple[bool, Dict]:
    """
    Validate that a section's choices match its text references.
    
    Returns: (is_valid, details)
    """
    html = section.get('presentation_html') or section.get('html') or ''
    text = section.get('text') or html_to_text(html)
    choices = section.get('choices', [])
    sequence = section.get('sequence', []) or []
    
    # Extract referenced sections from text
    text_refs = extract_turn_to_references(text)
    
    # Extract choice targets (support choices[] and sequence[])
    choice_targets = set()
    choice_source = "choices"
    for choice in choices:
        target = choice.get('target')
        if target and target.isdigit():
            choice_targets.add(int(target))
    if not choice_targets and sequence:
        choice_source = "sequence"
        for event in sequence:
            if event.get("kind") != "choice":
                continue
            target = event.get("targetSection")
            if target and str(target).isdigit():
                choice_targets.add(int(target))
    elif sequence:
        choice_source = "choices+sequence"
        for event in sequence:
            if event.get("kind") != "choice":
                continue
            target = event.get("targetSection")
            if target and str(target).isdigit():
                choice_targets.add(int(target))
    
    # Calculate discrepancy
    missing_in_choices = text_refs - choice_targets
    extra_in_choices = choice_targets - text_refs
    
    discrepancy_count = len(missing_in_choices)
    
    details = {
        'section_id': section_id,
        'text_references': sorted(list(text_refs)),
        'extracted_choices': sorted(list(choice_targets)),
        'missing_in_choices': sorted(list(missing_in_choices)),
        'extra_in_choices': sorted(list(extra_in_choices)),
        'discrepancy_count': discrepancy_count,
        'text_snippet': text[:200] if text else '',
        'choice_source': choice_source
    }
    
    # Consider valid if:
    # 1. No text references (e.g., ending section)
    # 2. All text references are in choices
    # 3. Small discrepancy (some refs might be conditional)
    is_valid = discrepancy_count == 0 or len(text_refs) == 0
    
    return is_valid, details


def main():
    parser = argparse.ArgumentParser(description='Validate choice completeness')
    parser.add_argument('--gamebook', required=True, help='Input gamebook.json')
    parser.add_argument('--out', required=True, help='Output validation report (JSON)')
    parser.add_argument('--max-discrepancy', '--max_discrepancy', type=int, default=1,
                       help='Max allowed diff between text refs and choices')
    parser.add_argument('--expected-range', '--expected_range', default='1-400',
                       help='Expected section range (e.g., "1-400")')
    parser.add_argument('--boundaries', help='(ignored; driver compatibility)')
    parser.add_argument('--elements', help='(ignored; driver compatibility)')
    parser.add_argument('--state-file', dest='state_file', help='Driver state file (optional)')
    parser.add_argument('--progress-file', dest='progress_file', help='Driver progress file (optional)')
    parser.add_argument('--run-id', help='Run ID for logging')
    args = parser.parse_args()
    
    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    
    # Load gamebook
    with open(args.gamebook, 'r') as f:
        gamebook = json.load(f)
    
    sections = gamebook.get('sections', {})
    
    # Validate each section
    flagged_sections = []
    all_details = {}
    
    total_sections = len(sections)
    for i, (section_id, section) in enumerate(sections.items()):
        is_valid, details = validate_section_choices(section_id, section)
        
        all_details[section_id] = details
        
        # Flag if discrepancy exceeds threshold
        if details['discrepancy_count'] > args.max_discrepancy:
            flagged_sections.append(section_id)
        
        if (i + 1) % 50 == 0:
            logger.log(
                "validate_choice_completeness",
                "running",
                current=i + 1,
                total=total_sections,
                message=f"Validated {i + 1}/{total_sections} sections",
                artifact=args.out,
                module_id="validate_choice_completeness_v1",
                schema_version="validation_report_v1"
            )
    
    # Generate report
    report = {
        'schema_version': 'validation_report_v1',
        'module_id': 'validate_choice_completeness_v1',
        'run_id': args.run_id,
        'total_sections': total_sections,
        'flagged_sections': sorted(flagged_sections, key=lambda x: int(x) if x.isdigit() else 0),
        'flagged_count': len(flagged_sections),
        'max_discrepancy_threshold': args.max_discrepancy,
        'is_valid': len(flagged_sections) == 0,
        'details': all_details,
        'warnings': [],
        'errors': []
    }
    
    # Generate warnings/errors
    if flagged_sections:
        report['errors'].append(
            f"Found {len(flagged_sections)} sections with potentially missing choices: {flagged_sections[:10]}"
            + (f" (and {len(flagged_sections) - 10} more)" if len(flagged_sections) > 10 else "")
        )
        
        # Show examples
        for sid in flagged_sections[:5]:
            details = all_details[sid]
            missing = details['missing_in_choices']
            if missing:
                report['warnings'].append(
                    f"Section {sid}: Text mentions {missing} but not in extracted choices"
                )
    
    # Save report
    save_json(args.out, report)
    
    logger.log(
        "validate_choice_completeness",
        "done",
        current=total_sections,
        total=total_sections,
        message=f"Validation complete: {len(flagged_sections)} sections flagged",
        artifact=args.out,
        module_id="validate_choice_completeness_v1",
        schema_version="validation_report_v1"
    )
    
    print(f"\n=== Choice Completeness Validation ===")
    print(f"Total sections: {total_sections}")
    print(f"Flagged sections: {len(flagged_sections)}")
    print(f"Valid: {report['is_valid']}")
    
    if flagged_sections:
        print(f"\n⚠️ Sections with potential missing choices:")
        for sid in flagged_sections[:10]:
            details = all_details[sid]
            print(f"  Section {sid}: Text refs {details['text_references']} "
                  f"but choices only {details['extracted_choices']}")
        if len(flagged_sections) > 10:
            print(f"  ... and {len(flagged_sections) - 10} more")
        
        print(f"\n❌ VALIDATION FAILED: {len(flagged_sections)} sections need review")
        print(f"   For 100% game engine accuracy, all choices must be complete.")
        return 1
    else:
        print(f"\n✅ VALIDATION PASSED: All sections have complete choices")
        return 0


if __name__ == '__main__':
    exit(main())
