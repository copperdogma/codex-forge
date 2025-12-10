#!/usr/bin/env python3
"""
Boundary coverage validator: ensures enough section_ids are present and reports missing IDs.
"""
import argparse
import json
import os
from typing import Dict, Set

from modules.common.utils import read_jsonl, save_json, ProgressLogger


def main():
    parser = argparse.ArgumentParser(description="Validate boundary coverage (section ids).")
    parser.add_argument("--boundaries", required=True, help="section_boundaries.jsonl (merged)")
    parser.add_argument("--out", required=True, help="Output report JSON")
    parser.add_argument("--range", default="1-400", help="Expected id range, e.g., 1-400")
    parser.add_argument("--min-present", "--min_present", type=int, default=320, dest="min_present",
                        help="Minimum unique ids required to pass")
    parser.add_argument("--elements", help="Ignored (driver compatibility)", required=False)
    parser.add_argument("--progress-file")
    parser.add_argument("--state-file")
    parser.add_argument("--run-id")
    args = parser.parse_args()

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    logger.log("validate", "running", current=0, total=1,
               message="Validating boundary coverage", artifact=args.out,
               module_id="validate_boundary_coverage_v1")

    try:
        start_id, end_id = [int(x) for x in args.range.split("-")]
    except Exception:
        start_id, end_id = 1, 400
    expected: Set[str] = {str(i) for i in range(start_id, end_id + 1)}

    found: Set[str] = set()
    for b in read_jsonl(args.boundaries):
        sid = str(b.get("section_id"))
        if sid.isdigit():
            found.add(sid)

    missing = sorted(list(expected - found), key=int)
    report = {
        "found": len(found),
        "missing_count": len(missing),
        "missing_sample": missing[:30],
        "min_present": args.min_present,
        "range": args.range,
        "is_valid": len(found) >= args.min_present,
    }

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    save_json(args.out, report)

    status = "done" if report["is_valid"] else "failed"
    logger.log("validate", status, current=1, total=1,
               message=f"Boundary coverage {'ok' if report['is_valid'] else 'failed'} "
                       f"(found {len(found)}, missing {len(missing)})",
               artifact=args.out, module_id="validate_boundary_coverage_v1")

    if not report["is_valid"]:
        raise SystemExit("Boundary coverage validation failed")


if __name__ == "__main__":
    main()
