#!/usr/bin/env python3
"""
Trace orphan sections by scanning section text for explicit references.
Computes orphans from choices, then searches all raw_html for href and "turn to" patterns.
"""
import argparse
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
    ap = argparse.ArgumentParser(description="Trace orphan sections using explicit text references.")
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

    existing = {str(p.get("section_id") or p.get("portion_id")) for p in portions if str(p.get("section_id") or p.get("portion_id")).isdigit()}
    referenced: Set[str] = set()
    for p in portions:
        referenced.update(_choice_targets(p))

    orphans = sorted([s for s in existing if s != "1" and s not in referenced], key=lambda x: int(x))

    orphan_sources: Dict[str, List[str]] = {o: [] for o in orphans}
    for p in portions:
        sid = str(p.get("section_id") or p.get("portion_id") or "")
        explicit = _explicit_targets(p.get("raw_html") or "")
        for orphan in orphans:
            if orphan in explicit:
                orphan_sources[orphan].append(sid)

    unreferenced = sorted([o for o in orphans if not orphan_sources.get(o)], key=lambda x: int(x))

    report = {
        "schema_version": "validation_report_v1",
        "run_id": args.run_id,
        "orphans": orphans,
        "orphan_sources": orphan_sources,
        "unreferenced_orphans": unreferenced,
        "orphan_count": len(orphans),
        "unreferenced_count": len(unreferenced),
        "is_valid": len(orphans) == 0,
    }

    save_json(args.out, report)
    logger.log(
        "trace_orphans_text",
        "done",
        message=f"Orphan trace: {len(orphans)} orphans, {len(unreferenced)} unreferenced",
        artifact=args.out,
    )
    print(f"Orphan trace report -> {args.out}")
    print(f"Orphans: {len(orphans)}, Unreferenced: {len(unreferenced)}")


if __name__ == "__main__":
    main()
