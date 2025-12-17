#!/usr/bin/env python3
"""
Code-First Choice Extraction Module v1

Extracts choices from section text using deterministic pattern matching.
Uses "turn to X" patterns as primary signal, AI only for validation if needed.

Pattern matching approach:
1. Scan text for "turn to X", "go to Y", "refer to Z" patterns
2. Extract target section numbers with confidence scores
3. Deduplicate and validate range (1-400)
4. Optionally use AI for ambiguous cases
5. Output choices with provenance metadata

Critical for 100% game engine accuracy - uses strong deterministic signals.
"""

import argparse
import json
import re
from typing import List, Dict, Tuple, Optional, Set
from dataclasses import dataclass

from modules.common.utils import read_jsonl, save_jsonl, ProgressLogger


@dataclass
class ChoiceCandidate:
    target: int
    text_snippet: str
    confidence: float
    pattern: str
    position: int  # Character position in text


def extract_choice_patterns(text: str, min_section: int = 1, max_section: int = 400) -> List[ChoiceCandidate]:
    """
    Extract choice candidates using pattern matching.
    
    Returns list of ChoiceCandidate objects with confidence scores.
    """
    if not text:
        return []
    
    candidates = []
    text_lower = text.lower()
    
    # Pattern definitions with confidence scores
    # High confidence: explicit choice instructions
    # Medium confidence: narrative references (might be story, not choice)
    patterns = [
        # High confidence patterns (explicit instructions)
        (r'\bturn\s+to\s+(?:paragraph\s+)?(\d{1,3})\b', 0.95, 'turn_to'),
        (r'\bgo\s+to\s+(?:section\s+)?(\d{1,3})\b', 0.90, 'go_to'),
        (r'\brefer\s+to\s+(?:paragraph\s+)?(\d{1,3})\b', 0.85, 'refer_to'),
        
        # Medium confidence patterns
        (r'\bcontinue\s+(?:to\s+)?(?:paragraph\s+)?(\d{1,3})\b', 0.80, 'continue_to'),
        (r'\bproceed\s+to\s+(?:paragraph\s+)?(\d{1,3})\b', 0.80, 'proceed_to'),
        
        # Combat/test patterns (common in Fighting Fantasy)
        (r'\bif\s+you\s+win,?\s+turn\s+to\s+(\d{1,3})\b', 0.95, 'if_win'),
        (r'\bif\s+you\s+(?:are\s+)?lucky,?\s+turn\s+to\s+(\d{1,3})\b', 0.95, 'if_lucky'),
        (r'\bif\s+you\s+(?:are\s+)?unlucky,?\s+turn\s+to\s+(\d{1,3})\b', 0.95, 'if_unlucky'),
    ]
    
    for pattern_str, confidence, pattern_name in patterns:
        pattern = re.compile(pattern_str, re.IGNORECASE)
        
        for match in pattern.finditer(text_lower):
            target_str = match.group(1)
            target = int(target_str)
            
            # Validate range
            if min_section <= target <= max_section:
                # Extract snippet around match for context
                start = max(0, match.start() - 30)
                end = min(len(text), match.end() + 30)
                snippet = text[start:end].strip()
                
                candidates.append(ChoiceCandidate(
                    target=target,
                    text_snippet=snippet,
                    confidence=confidence,
                    pattern=pattern_name,
                    position=match.start()
                ))
    
    return candidates


def deduplicate_choices(candidates: List[ChoiceCandidate]) -> List[Dict]:
    """
    Deduplicate choice candidates, keeping highest confidence for each target.
    
    Returns list of choice dicts ready for output.
    """
    # Group by target
    by_target: Dict[int, List[ChoiceCandidate]] = {}
    for cand in candidates:
        if cand.target not in by_target:
            by_target[cand.target] = []
        by_target[cand.target].append(cand)
    
    # Keep highest confidence for each target
    choices = []
    for target, cands in sorted(by_target.items()):
        best = max(cands, key=lambda c: c.confidence)
        choices.append({
            'target': str(target),
            'text': f"Turn to {target}",  # Simplified text
            'confidence': best.confidence,
            'extraction_method': 'pattern_match',
            'pattern': best.pattern,
            'text_snippet': best.text_snippet,
        })
    
    return choices


def find_orphaned_sections(portions: List[Dict], expected_range: Tuple[int, int]) -> Set[int]:
    """
    Find sections that are never referenced by any choice (orphans).
    
    Every section except the first should be reachable from some choice.
    Orphans indicate missing choices somewhere in the book.
    """
    min_section, max_section = expected_range
    
    # Collect all section IDs
    all_sections = set()
    for portion in portions:
        sid = portion.get('section_id', '')
        if sid and sid.isdigit():
            num = int(sid)
            if min_section <= num <= max_section:
                all_sections.add(num)
    
    # Collect all referenced targets
    referenced = set()
    for portion in portions:
        choices = portion.get('choices', [])
        for choice in choices:
            target = choice.get('target', '')
            if target and target.isdigit():
                num = int(target)
                if min_section <= num <= max_section:
                    referenced.add(num)
    
    # Find orphans (sections that exist but are never referenced)
    # Exclude section 1 (start) as it's not expected to be referenced
    orphans = all_sections - referenced - {min_section}
    
    return orphans


def main():
    parser = argparse.ArgumentParser(description='Extract choices using pattern matching')
    parser.add_argument('--inputs', required=True, help='Input portions JSONL')
    parser.add_argument('--out', required=True, help='Output portions JSONL with choices')
    parser.add_argument('--use-ai-validation', action='store_true', 
                       help='Use AI to validate ambiguous matches')
    parser.add_argument('--max-ai-calls', type=int, default=50,
                       help='Max AI validation calls')
    parser.add_argument('--confidence-threshold', type=float, default=0.8,
                       help='Min confidence for pattern match')
    parser.add_argument('--expected-range', default='1-400',
                       help='Expected section range (e.g., "1-400")')
    parser.add_argument('--run-id', help='Run ID for logging')
    args = parser.parse_args()
    
    logger = ProgressLogger()
    
    # Parse expected range
    range_parts = args.expected_range.split('-')
    min_section = int(range_parts[0])
    max_section = int(range_parts[1])
    
    # Load portions
    portions = list(read_jsonl(args.inputs))
    total = len(portions)
    
    # Extract choices for each portion
    output_portions = []
    stats = {
        'total_portions': total,
        'portions_with_choices': 0,
        'total_choices_extracted': 0,
        'low_confidence_count': 0,
        'ai_validations': 0,
    }
    
    for i, portion in enumerate(portions):
        section_id = portion.get('section_id', '')
        text = portion.get('raw_text', '')
        
        # Extract candidates using pattern matching
        candidates = extract_choice_patterns(text, min_section, max_section)
        
        # Deduplicate
        choices = deduplicate_choices(candidates)
        
        # Filter by confidence
        high_confidence_choices = [
            c for c in choices 
            if c['confidence'] >= args.confidence_threshold
        ]
        
        low_confidence_choices = [
            c for c in choices
            if c['confidence'] < args.confidence_threshold
        ]
        
        if low_confidence_choices:
            stats['low_confidence_count'] += len(low_confidence_choices)
        
        # TODO: AI validation for low confidence choices if enabled
        # For now, include all choices
        all_choices = high_confidence_choices + low_confidence_choices
        
        # Update portion
        portion['choices'] = all_choices
        output_portions.append(portion)
        
        if all_choices:
            stats['portions_with_choices'] += 1
            stats['total_choices_extracted'] += len(all_choices)
        
        if (i + 1) % 50 == 0:
            logger.log(
                "extract_choices",
                "running",
                current=i + 1,
                total=total,
                message=f"Extracted choices from {i + 1}/{total} portions",
                artifact=args.out,
                module_id="extract_choices_v1",
                schema_version="enriched_portion_v1"
            )
    
    # Find orphaned sections
    orphans = find_orphaned_sections(output_portions, (min_section, max_section))
    
    # Save output
    save_jsonl(args.out, output_portions)
    
    # Save stats
    stats['orphaned_sections'] = sorted(list(orphans))
    stats['orphaned_count'] = len(orphans)
    
    stats_path = args.out.replace('.jsonl', '_stats.json')
    with open(stats_path, 'w') as f:
        json.dump(stats, f, indent=2)
    
    logger.log(
        "extract_choices",
        "done",
        current=total,
        total=total,
        message=f"Extracted {stats['total_choices_extracted']} choices from {stats['portions_with_choices']} portions",
        artifact=args.out,
        module_id="extract_choices_v1",
        schema_version="enriched_portion_v1"
    )
    
    # Print summary
    print(f"\n=== Choice Extraction Summary ===")
    print(f"Total portions: {stats['total_portions']}")
    print(f"Portions with choices: {stats['portions_with_choices']}")
    print(f"Total choices extracted: {stats['total_choices_extracted']}")
    print(f"Low confidence choices: {stats['low_confidence_count']}")
    
    if orphans:
        print(f"\n⚠️ Found {len(orphans)} orphaned sections (never referenced):")
        print(f"   {sorted(list(orphans))[:20]}")
        if len(orphans) > 20:
            print(f"   ... and {len(orphans) - 20} more")
        print(f"\n   This indicates missing choices somewhere in the book!")
        print(f"   Orphaned sections are in {stats_path}")
    else:
        print(f"\n✅ All sections are reachable (no orphans detected)")
    
    print(f"\nStats saved to: {stats_path}")


if __name__ == '__main__':
    main()




