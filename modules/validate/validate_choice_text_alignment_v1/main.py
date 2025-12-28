#!/usr/bin/env python3
"""
Validate that extracted choices align with explicit references in section text.
Scans raw_html for href targets and "turn to" style phrases, compares to choices.
"""
import argparse
import json
import re
from typing import Dict, List, Set

from modules.common.utils import read_jsonl, save_json, ProgressLogger


TURN_TO_RE = re.compile(r"\b(?:turn to|go to|refer to|proceed to)\s*(\d{1,3})\b", re.IGNORECASE)
HREF_RE = re.compile(r'href="#(\d{1,3})"')


def _explicit_targets(raw_html: str) -> Set[str]:
    targets: Set[str] = set()
    if not raw_html:
        return targets
    for m in TURN_TO_RE.finditer(raw_html):
        targets.add(m.group(1))
    for m in HREF_RE.finditer(raw_html):
        targets.add(m.group(1))
    return targets


def _choice_targets(portion: Dict) -> Set[str]:
    targets: Set[str] = set()
    for choice in portion.get("choices", []) or []:
        tgt = choice.get("target")
        if tgt is None:
            continue
        targets.add(str(tgt))
    return targets


def main() -> None:
    ap = argparse.ArgumentParser(description="Validate choice extraction vs explicit text references.")
    ap.add_argument("--portions", required=True, help="Input enriched_portion_v1 JSONL")
    ap.add_argument("--out", required=True, help="Output report JSON")
    ap.add_argument("--expected-range-start", "--expected_range_start", type=int, default=1)
    ap.add_argument("--expected-range-end", "--expected_range_end", type=int, default=400)
    ap.add_argument("--run-id")
    ap.add_argument("--state-file")
    ap.add_argument("--progress-file")
    args = ap.parse_args()

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    portions = [row for row in read_jsonl(args.portions) if "error" not in row]

    issues: List[Dict] = []
    for p in portions:
        sid = str(p.get("section_id") or p.get("portion_id") or "")
        raw_html = p.get("raw_html") or ""
        explicit = _explicit_targets(raw_html)
        choices = _choice_targets(p)

        missing = sorted([t for t in explicit if t not in choices and t.isdigit()], key=lambda x: int(x))
        if missing:
            issues.append({
                "section_id": sid,
                "missing_choice_targets": missing,
            })

    flagged_sections = sorted({i["section_id"] for i in issues if i.get("section_id")}, key=lambda x: int(x) if str(x).isdigit() else x)

    report = {
        "schema_version": "validation_report_v1",
        "run_id": args.run_id,
        "total_sections": len(portions),
        "flagged_sections": flagged_sections,
        "flagged_count": len(flagged_sections),
        "issues": issues,
        "is_valid": len(flagged_sections) == 0,
    }

    save_json(args.out, report)
    logger.log(
        "validate_choice_text_alignment",
        "done",
        message=f"Choice/text alignment: {len(flagged_sections)} sections flagged",
        artifact=args.out,
    )
    print(f"Choice/text alignment report -> {args.out}")
    print(f"Flagged sections: {len(flagged_sections)}")


if __name__ == "__main__":
    main()
