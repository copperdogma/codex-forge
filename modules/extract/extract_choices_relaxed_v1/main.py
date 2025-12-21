#!/usr/bin/env python3
"""
Code-First Choice Extraction Module (Relaxed)

Extracts choices from section text using deterministic pattern matching.
Adds a relaxed, text-only rescan over HTML-stripped text to surface
missed references without altering primary choices.

Pattern matching approach:
1. Scan text for "turn to X", "go to Y", "refer to Z" patterns
2. Extract target section numbers with confidence scores
3. Deduplicate and validate range (1-400)
4. Optionally use AI for ambiguous cases
5. Output choices + relaxed reference evidence

Critical for 100% game engine accuracy - uses strong deterministic signals.
"""

import argparse
import html as html_lib
import json
import os
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


def _normalize_section_ref_token(token: str) -> Optional[int]:
    """
    Normalize common OCR confusions in a numeric section reference token.

    Intended for tokens captured from "turn/go/refer to <N>" patterns where <N> is
    expected to be numeric, but may contain OCR confusions (e.g., "1S7" -> "157").
    """
    if not token:
        return None
    raw = (token or "").strip().strip(".,;:!?()[]{}<>\"'“”’`")
    if not raw:
        return None
    if raw.isdigit():
        try:
            return int(raw)
        except Exception:
            return None

    # Conservative mapping: only characters that frequently appear as digit confusions.
    digit_map = {
        "O": "0",
        "o": "0",
        "D": "0",
        "Q": "0",
        "I": "1",
        "l": "1",
        "!": "1",
        "S": "5",
        "s": "5",
        "Z": "2",
        "B": "8",
        # Keep this tight; avoid broad mappings like A->4 unless proven needed.
    }
    fixed = "".join(digit_map.get(ch, ch) for ch in raw)

    # Only accept if the result becomes purely digits and at least one character changed.
    if fixed == raw or not fixed.isdigit():
        return None
    try:
        return int(fixed)
    except Exception:
        return None


def extract_choice_patterns(text: str, min_section: int = 1, max_section: int = 400) -> List[ChoiceCandidate]:
    """
    Extract choice candidates using pattern matching.
    
    Returns list of ChoiceCandidate objects with confidence scores.
    """
    if not text:
        return []
    
    candidates = []
    
    # Pattern definitions with confidence scores
    # High confidence: explicit choice instructions
    # Medium confidence: narrative references (might be story, not choice)
    # Note: tolerate OCR confusions for gamebook navigation phrases:
    # - "tum" for "turn"
    # - "t0"/"tO" for "to"
    # - digit/letter confusions in target section number token ("1S7" -> 157)
    turn_word = r'(?:turn|tum)'
    to_word = r'(?:to|t0|tO)'
    target_token = r'([0-9A-Za-z!]{1,4})'
    patterns = [
        # High confidence patterns (explicit instructions)
        (rf'\b{turn_word}\s+{to_word}\s+(?:paragraph\s+)?{target_token}\b', 0.95, 'turn_to'),
        (rf'\bgo\s+{to_word}\s+(?:section\s+)?{target_token}\b', 0.90, 'go_to'),
        (rf'\brefer\s+{to_word}\s+(?:paragraph\s+)?{target_token}\b', 0.85, 'refer_to'),
        
        # Medium confidence patterns
        (rf'\bcontinue\s+(?:{to_word}\s+)?(?:paragraph\s+)?{target_token}\b', 0.80, 'continue_to'),
        (rf'\bproceed\s+{to_word}\s+(?:paragraph\s+)?{target_token}\b', 0.80, 'proceed_to'),
        
        # Combat/test patterns (common in Fighting Fantasy)
        (rf'\bif\s+you\s+win,?\s+{turn_word}\s+{to_word}\s+{target_token}\b', 0.95, 'if_win'),
        (rf'\bif\s+you\s+(?:are\s+)?lucky,?\s+{turn_word}\s+{to_word}\s+{target_token}\b', 0.95, 'if_lucky'),
        (rf'\bif\s+you\s+(?:are\s+)?unlucky,?\s+{turn_word}\s+{to_word}\s+{target_token}\b', 0.95, 'if_unlucky'),
    ]
    
    for pattern_str, confidence, pattern_name in patterns:
        pattern = re.compile(pattern_str, re.IGNORECASE)
        
        for match in pattern.finditer(text):
            target_str = match.group(1)
            target = _normalize_section_ref_token(target_str)
            if target is None:
                continue
            
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


def _html_to_text(html: str) -> str:
    if not html:
        return ""
    text = html

    def _img_alt(match: re.Match) -> str:
        alt = match.group(1) or ""
        return f" {alt} " if alt else " "

    text = re.sub(r'<img[^>]*alt="([^"]*)"[^>]*>', _img_alt, text, flags=re.IGNORECASE)
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)

    block_tags = [
        "p", "h1", "h2", "h3", "h4", "h5", "h6",
        "li", "ul", "ol", "dl", "dt", "dd",
        "table", "thead", "tbody", "tr", "td", "th",
        "div", "section", "header", "footer",
    ]
    for tag in block_tags:
        text = re.sub(rf'</?{tag}[^>]*>', '\n', text, flags=re.IGNORECASE)

    text = re.sub(r'<[^>]+>', ' ', text)
    text = html_lib.unescape(text)
    text = re.sub(r'[ \t\r\f\v]+', ' ', text)
    text = re.sub(r'\n\s*\n+', '\n', text)
    return text.strip()


def extract_choice_patterns_relaxed(text: str, min_section: int, max_section: int) -> List[ChoiceCandidate]:
    if not text:
        return []

    candidates: List[ChoiceCandidate] = []

    target_token = r'([0-9A-Za-z!]{1,4})'
    verb_patterns = [
        (rf'\b(?:see|return|leave|enter|head|move|climb|drink|eat|open|close|choose|select|take|try)\s+(?:to\s+)?(?:paragraph\s+|section\s+)?{target_token}\b', 0.72, 'verb_to'),
        (rf'\b(?:option|choice)\s+(?:is|:)?\s*{target_token}\b', 0.65, 'option_is'),
        (rf'\b(?:or)\s+(?:{target_token})\b', 0.60, 'or_number'),
    ]
    for pattern_str, confidence, pattern_name in verb_patterns:
        pattern = re.compile(pattern_str, re.IGNORECASE)
        for match in pattern.finditer(text):
            target = _normalize_section_ref_token(match.group(1))
            if target is None or not (min_section <= target <= max_section):
                continue
            start = max(0, match.start() - 30)
            end = min(len(text), match.end() + 30)
            snippet = text[start:end].strip()
            candidates.append(ChoiceCandidate(
                target=target,
                text_snippet=snippet,
                confidence=confidence,
                pattern=pattern_name,
                position=match.start(),
            ))

    keyword_lines = [
        "turn", "tum", "go", "refer", "see", "return", "leave", "enter",
        "continue", "proceed", "paragraph", "section", "choice", "option",
        "if you", "otherwise", "or", "win", "lucky", "unlucky",
    ]
    token_pattern = re.compile(r'\b[0-9A-Za-z!]{1,4}\b')
    for line in text.splitlines():
        if not line:
            continue
        lower = line.lower()
        if not any(k in lower for k in keyword_lines):
            continue
        for token in token_pattern.findall(line):
            target = _normalize_section_ref_token(token)
            if target is None or not (min_section <= target <= max_section):
                continue
            candidates.append(ChoiceCandidate(
                target=target,
                text_snippet=line.strip(),
                confidence=0.60,
                pattern="keyword_line",
                position=0,
            ))

    return candidates


def deduplicate_choices(candidates: List[ChoiceCandidate], extraction_method: str) -> List[Dict]:
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
            'text': f"Turn to {target}",
            'confidence': best.confidence,
            'extraction_method': extraction_method,
            'pattern': best.pattern,
            'text_snippet': best.text_snippet,
        })
    
    return choices


def find_orphaned_sections(portions: List[Dict], expected_range: Tuple[int, int], choices_key: str = "choices") -> Set[int]:
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
        choices = portion.get(choices_key, [])
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
    parser.add_argument('--inputs', help='Input portions JSONL (alias: --pages)')
    parser.add_argument('--pages', help='Input portions JSONL (driver extract-stage compatibility)')
    parser.add_argument('--outdir', help='Output directory (driver extract-stage compatibility)')
    parser.add_argument('--out', help='Output portions JSONL with choices')
    parser.add_argument('--pdf', help='Ignored (driver extract-stage compatibility)')
    parser.add_argument('--images', help='Ignored (driver extract-stage compatibility)')
    parser.add_argument('--use-ai-validation', '--use_ai_validation', action='store_true',
                        help='Use AI to validate ambiguous matches')
    parser.add_argument('--max-ai-calls', '--max_ai_calls', type=int, default=50,
                        help='Max AI validation calls')
    parser.add_argument('--confidence-threshold', '--confidence_threshold', type=float, default=0.8,
                        help='Min confidence for pattern match')
    parser.add_argument('--expected-range', '--expected_range', default='1-400',
                        help='Expected section range (e.g., "1-400")')
    parser.add_argument('--state-file', dest='state_file', help='Driver state file (optional)')
    parser.add_argument('--progress-file', dest='progress_file', help='Driver progress file (optional)')
    parser.add_argument('--run-id', help='Run ID for logging')
    args = parser.parse_args()

    portions_path = args.inputs or args.pages
    if not portions_path:
        raise SystemExit("Missing --inputs or --pages")
    out_name = args.out or 'portions_with_choices.jsonl'
    if args.outdir and not os.path.isabs(out_name) and os.sep not in out_name:
        out_path = os.path.join(args.outdir, out_name)
    elif os.path.isabs(out_name) or os.sep in out_name:
        out_path = out_name
    else:
        out_path = out_name
    
    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    
    # Parse expected range
    range_parts = args.expected_range.split('-')
    min_section = int(range_parts[0])
    max_section = int(range_parts[1])
    
    # Load portions
    portions = list(read_jsonl(portions_path))
    total = len(portions)
    
    # Extract choices for each portion
    output_portions = []
    stats = {
        'total_portions': total,
        'portions_with_choices': 0,
        'total_choices_extracted': 0,
        'low_confidence_count': 0,
        'ai_validations': 0,
        'portions_with_relaxed_refs': 0,
        'total_relaxed_refs': 0,
    }
    relaxed_reference_index: Dict[str, Set[str]] = {}
    
    for i, portion in enumerate(portions):
        section_id = portion.get('section_id', '')
        raw_text = portion.get('raw_text') or ''
        raw_html = portion.get('raw_html') or ''
        html_text = _html_to_text(raw_html)
        text = raw_text or html_text
        
        # Extract candidates using pattern matching
        candidates = extract_choice_patterns(text, min_section, max_section)
        
        # Deduplicate
        choices = deduplicate_choices(candidates, "pattern_match")

        relaxed_candidates = extract_choice_patterns_relaxed(html_text, min_section, max_section)
        relaxed_choices = deduplicate_choices(relaxed_candidates, "pattern_match_relaxed")
        
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
        portion['choices_relaxed'] = relaxed_choices
        output_portions.append(portion)
        
        if all_choices:
            stats['portions_with_choices'] += 1
            stats['total_choices_extracted'] += len(all_choices)
        if relaxed_choices:
            stats['portions_with_relaxed_refs'] += 1
            stats['total_relaxed_refs'] += len(relaxed_choices)
            if section_id:
                for choice in relaxed_choices:
                    target = choice.get('target')
                    if not target:
                        continue
                    if target not in relaxed_reference_index:
                        relaxed_reference_index[target] = set()
                    relaxed_reference_index[target].add(section_id)
        
        if (i + 1) % 50 == 0:
            logger.log(
                "extract_choices",
                "running",
                current=i + 1,
                total=total,
                message=f"Extracted choices from {i + 1}/{total} portions",
                artifact=out_path,
                module_id="extract_choices_relaxed_v1",
                schema_version="enriched_portion_v1"
            )
    
    # Find orphaned sections
    orphans = find_orphaned_sections(output_portions, (min_section, max_section), choices_key="choices")
    orphans_relaxed = find_orphaned_sections(output_portions, (min_section, max_section), choices_key="choices_relaxed")
    
    # Save output
    save_jsonl(out_path, output_portions)
    
    # Save stats
    stats['orphaned_sections'] = sorted(list(orphans))
    stats['orphaned_count'] = len(orphans)
    stats['orphaned_sections_relaxed'] = sorted(list(orphans_relaxed))
    stats['orphaned_count_relaxed'] = len(orphans_relaxed)
    if relaxed_reference_index:
        stats['relaxed_reference_index'] = {
            target: sorted(list(sources))
            for target, sources in relaxed_reference_index.items()
        }
    
    stats_path = out_path.replace('.jsonl', '_stats.json')
    with open(stats_path, 'w') as f:
        json.dump(stats, f, indent=2)
    
    logger.log(
        "extract_choices",
        "done",
        current=total,
        total=total,
        message=f"Extracted {stats['total_choices_extracted']} choices from {stats['portions_with_choices']} portions",
        artifact=out_path,
        module_id="extract_choices_relaxed_v1",
        schema_version="enriched_portion_v1"
    )
    
    # Print summary
    print(f"\n=== Choice Extraction Summary ===")
    print(f"Total portions: {stats['total_portions']}")
    print(f"Portions with choices: {stats['portions_with_choices']}")
    print(f"Total choices extracted: {stats['total_choices_extracted']}")
    print(f"Low confidence choices: {stats['low_confidence_count']}")
    print(f"Portions with relaxed refs: {stats['portions_with_relaxed_refs']}")
    print(f"Total relaxed refs: {stats['total_relaxed_refs']}")
    
    if orphans:
        print(f"\n⚠️ Found {len(orphans)} orphaned sections (never referenced):")
        print(f"   {sorted(list(orphans))[:20]}")
        if len(orphans) > 20:
            print(f"   ... and {len(orphans) - 20} more")
        print(f"\n   This indicates missing choices somewhere in the book!")
        print(f"   Orphaned sections are in {stats_path}")
    else:
        print(f"\n✅ All sections are reachable (no orphans detected)")

    if orphans_relaxed and not orphans:
        print(f"\nℹ️ Relaxed scan still has {len(orphans_relaxed)} orphans (diagnostic only).")
    elif not orphans_relaxed and orphans:
        print(f"\n✅ Relaxed scan references all sections (diagnostic only).")
    
    print(f"\nStats saved to: {stats_path}")


if __name__ == '__main__':
    main()
