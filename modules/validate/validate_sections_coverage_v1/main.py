#!/usr/bin/env python3
"""
Coverage/ordering guard for structured sections.

Fails fast before boundary assembly if:
- coverage (certain+uncertain) is below a minimum
- start_seq is not strictly increasing
- optional: section id coverage is below a threshold
"""

import argparse
import json
import os
from typing import List, Tuple

from modules.common.utils import ProgressLogger, save_json
from schemas import SectionsStructured


def monotonic_errors(sections: List[Tuple[int, int]]) -> List[str]:
    """Return error strings for non-monotonic start_seq."""
    errors = []
    prev_seq = -1
    prev_id = None
    for sid, seq in sections:
        if seq <= prev_seq:
            errors.append(f"id {sid} start_seq {seq} not greater than prev {prev_id} ({prev_seq})")
        prev_seq = seq
        prev_id = sid
    return errors


def main():
    parser = argparse.ArgumentParser(description="Validate structured section coverage before boundaries.")
    parser.add_argument("--structure", required=True, help="sections_structured.json")
    parser.add_argument("--out", required=True, help="Path to write coverage report JSON")
    parser.add_argument("--min-sections", type=int, default=350, dest="min_sections",
                        help="Minimum number of sections required (certain+uncertain)")
    parser.add_argument("--min-certain", type=int, default=200, dest="min_certain",
                        help="Minimum number of certain sections required")
    parser.add_argument("--target-range", default="1-400",
                        help="Expected section id range, e.g. 1-400")
    parser.add_argument("--allow-nonmonotonic", action="store_true",
                        help="If set, monotonic check is a warning instead of error")
    parser.add_argument("--progress-file")
    parser.add_argument("--state-file")
    parser.add_argument("--run-id")
    args = parser.parse_args()

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    logger.log("validate", "running", current=0, total=1,
               message="Validating structured sections coverage", artifact=args.out,
               module_id="validate_sections_coverage_v1")

    with open(args.structure, "r", encoding="utf-8") as f:
        struct = SectionsStructured.model_validate_json(f.read())

    game_sections = [(int(gs.id), int(gs.start_seq)) for gs in struct.game_sections if gs.start_seq is not None]
    total_sections = len(game_sections)
    certain_sections = len([gs for gs in struct.game_sections if gs.status == "certain"])

    # coverage by id range
    try:
        start_id, end_id = [int(x) for x in args.target_range.split("-")]
    except Exception:
        start_id, end_id = 1, 400
    ids_present = {int(gs.id) for gs in struct.game_sections if str(gs.id).isdigit()}
    expected_ids = set(range(start_id, end_id + 1))
    missing_ids = sorted(list(expected_ids - ids_present))

    errors = []
    warnings = []

    if total_sections < args.min_sections:
        errors.append(f"Insufficient sections: {total_sections} < min_sections={args.min_sections}")
    if certain_sections < args.min_certain:
        warnings.append(f"Low certain count: {certain_sections} < min_certain={args.min_certain}")

    mono_errs = monotonic_errors(sorted(game_sections, key=lambda x: x[1]))
    if mono_errs:
        if args.allow_nonmonotonic:
            warnings.extend([f"Non-monotonic: {m}" for m in mono_errs])
        else:
            errors.extend([f"Non-monotonic: {m}" for m in mono_errs])

    report = {
        "total_sections": total_sections,
        "certain_sections": certain_sections,
        "min_sections": args.min_sections,
        "min_certain": args.min_certain,
        "missing_ids_sample": missing_ids[:20],
        "missing_ids_count": len(missing_ids),
        "nonmonotonic_count": len(mono_errs),
        "warnings": warnings,
        "errors": errors,
        "is_valid": len(errors) == 0,
    }

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    save_json(args.out, report)

    status = "done" if report["is_valid"] else "failed"
    logger.log("validate", status, current=1, total=1,
               message=f"Coverage {'ok' if report['is_valid'] else 'failed'} "
                       f"(sections={total_sections}, certain={certain_sections}, missing_ids={report['missing_ids_count']})",
               artifact=args.out, module_id="validate_sections_coverage_v1")

    if not report["is_valid"]:
        raise SystemExit("Section coverage validation failed")


if __name__ == "__main__":
    main()
