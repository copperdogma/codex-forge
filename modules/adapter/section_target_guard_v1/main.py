import argparse
import json
import os
import sys
from typing import List, Set, Tuple, Dict, Any

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if os.getcwd() not in sys.path:
    sys.path.insert(0, os.getcwd())

from modules.common.utils import read_jsonl, append_jsonl, ensure_dir  # noqa: E402


def collect_ids_and_targets(paths: List[str]) -> Tuple[Set[str], Set[str]]:
    """
    Gather known section/portion ids and all referenced targets from the provided enriched_portion JSONLs.
    """
    known_ids: Set[str] = set()
    targets: Set[str] = set()
    for path in paths:
        for row in read_jsonl(path):
            pid = row.get("portion_id")
            if pid is not None:
                known_ids.add(str(pid))
            sid = row.get("section_id")
            if sid is not None:
                known_ids.add(str(sid))
            for t in row.get("targets") or []:
                if t is not None:
                    targets.add(str(t))
            for choice in row.get("choices") or []:
                tgt = choice.get("target")
                if tgt is not None:
                    targets.add(str(tgt))
    return known_ids, targets


def map_hits(row: Dict[str, Any], known_ids: Set[str]) -> Dict[str, Any]:
    targets = row.get("targets") or []
    hits = [t for t in targets if str(t) in known_ids]
    misses = [t for t in targets if str(t) not in known_ids]
    updated = dict(row)
    updated["target_hits"] = hits
    updated["target_misses"] = misses
    return updated


def sort_targets(values: Set[str]) -> List[str]:
    def sort_key(x: str):
        return (0, int(x)) if x.isdigit() else (1, x)

    return sorted(list(values), key=sort_key)


def write_backfill(target: str, out_path: str):
    stub = {
        "schema_version": "enriched_portion_v1",
        "module_id": "section_target_guard_v1",
        "run_id": "section_target_guard",
        "portion_id": target,
        "section_id": target,
        "page_start": 0,
        "page_end": 0,
        "title": None,
        "type": "section",
        "confidence": 0.0,
        "source_images": [],
        "raw_text": "",
        "choices": [],
        "combat": None,
        "test_luck": None,
        "item_effects": [],
        "targets": [],
    }
    append_jsonl(out_path, stub)


def main():
    parser = argparse.ArgumentParser(
        description="Map targets to known sections, backfill missing ones, and emit a coverage report."
    )
    parser.add_argument("--inputs", nargs="+", required=True, help="Enriched_portion JSONLs (first is primary output)")
    parser.add_argument("--out", required=True, help="Output JSONL with mapped rows and backfilled stubs")
    parser.add_argument("--report", required=True, help="Coverage report JSON path")
    parser.add_argument("--allow-missing", action="store_true", help="Exit 0 even when missing targets exist")
    args = parser.parse_args()

    ensure_dir(os.path.dirname(args.out) or ".")
    ensure_dir(os.path.dirname(args.report) or ".")

    known_ids, targets = collect_ids_and_targets(args.inputs)
    missing = sort_targets(targets - known_ids)

    # Map hits/misses for primary input rows
    primary = args.inputs[0]
    for row in read_jsonl(primary):
        append_jsonl(args.out, map_hits(row, known_ids))

    # Backfill stubs for missing targets
    for tgt in missing:
        write_backfill(tgt, args.out)

    targets_present = len(targets) - len(missing)
    hit_rate = (targets_present / len(targets)) if targets else 1.0
    report = {
        "section_count": len(known_ids),
        "targets_count": len(targets),
        "targets_present": targets_present,
        "missing_count": len(missing),
        "missing_sample": missing[:50],
        "hit_rate": hit_rate,
        "stubbed_count": len(missing),
        "inputs": args.inputs,
        "out_path": args.out,
        "allow_missing": bool(args.allow_missing),
    }

    with open(args.report, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(json.dumps(report, indent=2))

    if missing and not args.allow_missing:
        sys.exit(1)


if __name__ == "__main__":
    main()
