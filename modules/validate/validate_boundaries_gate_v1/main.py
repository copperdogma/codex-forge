#!/usr/bin/env python3
"""
Sanity gate for section_boundaries before extraction.
Checks:
- minimum boundary count
- monotonic start order (by element seq)
- optional: max gap between starts (warn)
Fails fast on count/monotonic errors.
"""

import argparse
import os
from typing import Dict, List

from modules.common.utils import read_jsonl, save_json, ProgressLogger
from schemas import SectionBoundary, ElementCore


def load_elements(elements_path: str) -> Dict[str, ElementCore]:
    elems = {}
    for e in read_jsonl(elements_path):
        elem = ElementCore(**e)
        elems[elem.id] = elem
    return elems


def validate(boundaries: List[SectionBoundary], elements: Dict[str, ElementCore],
             min_count: int, max_gap: int | None) -> dict:
    id_to_seq = {e.id: e.seq for e in elements.values()}
    errors = []
    warnings = []

    if len(boundaries) < min_count:
        errors.append(f"Boundary count {len(boundaries)} < min_count {min_count}")

    # sort by start seq
    ordered = sorted(boundaries, key=lambda b: id_to_seq.get(b.start_element_id, 999999))
    prev_seq = -1
    for b in ordered:
        seq = id_to_seq.get(b.start_element_id)
        if seq is None:
            errors.append(f"start_element_id {b.start_element_id} missing in elements")
            continue
        if seq <= prev_seq:
            errors.append(f"Non-monotonic start seq at section {b.section_id} ({seq} <= {prev_seq})")
        if max_gap is not None and prev_seq >= 0 and seq - prev_seq > max_gap:
            warnings.append(f"Large gap {seq - prev_seq} before section {b.section_id}")
        prev_seq = seq

    return {
        "count": len(boundaries),
        "errors": errors,
        "warnings": warnings,
        "is_valid": len(errors) == 0,
    }


def main():
    parser = argparse.ArgumentParser(description="Validate boundary set before extraction.")
    parser.add_argument("--boundaries", required=True, help="section_boundaries.jsonl (merged)")
    parser.add_argument("--elements", required=True, help="elements_core.jsonl")
    parser.add_argument("--out", required=True, help="Output report JSON")
    parser.add_argument("--min-count", "--min_count", type=int, default=350, dest="min_count")
    parser.add_argument("--max-gap", "--max_gap", type=int, default=None, dest="max_gap")
    parser.add_argument("--progress-file")
    parser.add_argument("--state-file")
    parser.add_argument("--run-id")
    args = parser.parse_args()

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    logger.log("validate", "running", current=0, total=1,
               message="Validating boundaries", artifact=args.out,
               module_id="validate_boundaries_gate_v1")

    boundaries = [SectionBoundary(**b) for b in read_jsonl(args.boundaries)]
    elements = load_elements(args.elements)

    report = validate(boundaries, elements, args.min_count, args.max_gap)

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    save_json(args.out, report)

    status = "done" if report["is_valid"] else "failed"
    logger.log("validate", status, current=1, total=1,
               message=f"Boundary gate {'ok' if report['is_valid'] else 'failed'} (count={report['count']})",
               artifact=args.out, module_id="validate_boundaries_gate_v1")

    if not report["is_valid"]:
        raise SystemExit("Boundary gate failed")


if __name__ == "__main__":
    main()
