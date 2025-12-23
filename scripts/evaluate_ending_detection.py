#!/usr/bin/env python3
"""Evaluate ending detection quality against ground truth reference list.

Usage:
    python scripts/evaluate_ending_detection.py \
        --portions output/runs/.../portions_with_endings.jsonl \
        --reference "2,3,4,7,8,17,19,34,44,61,70,85,96,101,116,140,193,219,233,255,268,272,276,317,325,329,333,334,347,359,366,372" \
        --out /tmp/ending_evaluation.json
"""

import argparse
import json
from pathlib import Path
from typing import Set, Dict, List

from modules.common.utils import read_jsonl


def load_reference_endings(reference_str: str) -> Set[str]:
    """Parse comma-separated reference list into set of section IDs."""
    return set(reference_str.split(','))


def load_detected_endings(portions_path: str) -> Dict[str, Dict]:
    """Load portions file and extract sections marked with ending field."""
    portions = list(read_jsonl(portions_path))
    detected = {}
    for p in portions:
        section_id = str(p.get('section_id', ''))
        if p.get('ending'):  # Has ending="death" or ending="victory"
            detected[section_id] = {
                'ending_type': p.get('ending'),
                'reason': p.get('repair', {}).get('ending_guard', {}).get('reason', 'N/A'),
                'has_choices': bool(p.get('choices') and len(p.get('choices', [])) > 0)
            }
    return detected


def evaluate(reference: Set[str], detected: Dict[str, Dict]) -> Dict:
    """Calculate precision, recall, F1, and identify errors."""
    detected_ids = set(detected.keys())

    # True positives: in both reference and detected
    true_positives = reference & detected_ids
    # False positives: detected but not in reference
    false_positives = detected_ids - reference
    # False negatives: in reference but not detected
    false_negatives = reference - detected_ids

    # Metrics
    precision = len(true_positives) / len(detected_ids) if detected_ids else 0.0
    recall = len(true_positives) / len(reference) if reference else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    # Gather details
    fp_details = []
    for sid in sorted(false_positives, key=int):
        fp_details.append({
            'section_id': sid,
            'ending_type': detected[sid]['ending_type'],
            'reason': detected[sid]['reason'][:100],
            'has_choices': detected[sid]['has_choices']
        })

    fn_details = [{'section_id': sid} for sid in sorted(false_negatives, key=int)]

    return {
        'summary': {
            'reference_count': len(reference),
            'detected_count': len(detected_ids),
            'true_positives': len(true_positives),
            'false_positives': len(false_positives),
            'false_negatives': len(false_negatives),
            'precision': round(precision, 4),
            'recall': round(recall, 4),
            'f1_score': round(f1, 4)
        },
        'reference_ids': sorted(reference, key=int),
        'detected_ids': sorted(detected_ids, key=int),
        'true_positive_ids': sorted(true_positives, key=int),
        'false_positive_ids': sorted(false_positives, key=int),
        'false_negative_ids': sorted(false_negatives, key=int),
        'false_positives_details': fp_details,
        'false_negatives_details': fn_details,
        'detected_by_type': {
            'death': [sid for sid, d in detected.items() if d['ending_type'] == 'death'],
            'victory': [sid for sid, d in detected.items() if d['ending_type'] == 'victory']
        }
    }


def print_report(results: Dict):
    """Print human-readable evaluation report."""
    s = results['summary']
    print("\n=== Ending Detection Evaluation ===\n")
    print(f"Reference endings: {s['reference_count']}")
    print(f"Detected endings:  {s['detected_count']}")
    print(f"\nMetrics:")
    print(f"  Precision: {s['precision']:.2%} ({s['true_positives']}/{s['detected_count']})")
    print(f"  Recall:    {s['recall']:.2%} ({s['true_positives']}/{s['reference_count']})")
    print(f"  F1 Score:  {s['f1_score']:.4f}")

    print(f"\nConfusion Matrix:")
    print(f"  True Positives:  {s['true_positives']}")
    print(f"  False Positives: {s['false_positives']}")
    print(f"  False Negatives: {s['false_negatives']}")

    if results['false_positives_details']:
        print(f"\n⚠️  False Positives ({len(results['false_positives_details'])}):")
        for fp in results['false_positives_details']:
            print(f"  - Section {fp['section_id']}: {fp['ending_type']} - {fp['reason']}")
            if fp['has_choices']:
                print(f"    ⚠️  Has choices! Should not be marked as ending.")

    if results['false_negatives_details']:
        print(f"\n❌ False Negatives ({len(results['false_negatives_details'])}):")
        for fn in results['false_negatives_details']:
            print(f"  - Section {fn['section_id']}: Not detected (should be ending)")

    print(f"\nDetected by type:")
    print(f"  Death:   {len(results['detected_by_type']['death'])}")
    print(f"  Victory: {len(results['detected_by_type']['victory'])}")

    if s['recall'] == 1.0 and s['precision'] == 1.0:
        print("\n✅ Perfect detection! 100% precision and recall.")
    elif s['recall'] == 1.0:
        print(f"\n✅ Perfect recall! All reference endings found.")
        print(f"⚠️  Precision: {s['precision']:.2%} - {s['false_positives']} extra endings detected.")
    elif s['precision'] == 1.0:
        print(f"\n✅ Perfect precision! No false positives.")
        print(f"⚠️  Recall: {s['recall']:.2%} - {s['false_negatives']} reference endings missed.")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--portions', required=True, help='Path to portions_with_endings.jsonl')
    parser.add_argument('--reference', required=True, help='Comma-separated list of reference ending section IDs')
    parser.add_argument('--out', help='Output JSON report path (optional)')
    args = parser.parse_args()

    # Load data
    reference = load_reference_endings(args.reference)
    detected = load_detected_endings(args.portions)

    # Evaluate
    results = evaluate(reference, detected)

    # Print report
    print_report(results)

    # Save JSON report
    if args.out:
        with open(args.out, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\n📄 Full report saved to: {args.out}")


if __name__ == '__main__':
    main()
