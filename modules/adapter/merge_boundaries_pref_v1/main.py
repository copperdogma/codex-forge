#!/usr/bin/env python3
import argparse
import json
from modules.common.utils import read_jsonl, save_jsonl, ProgressLogger


def main():
    parser = argparse.ArgumentParser(description="Merge boundary sets preferring primary, filling gaps with fallback.")
    parser.add_argument("--primary", help="Primary section_boundaries.jsonl")
    parser.add_argument("--fallback", help="Fallback section_boundaries.jsonl (e.g., AI scan)")
    parser.add_argument("--inputs", nargs="+", help="Driver compatibility: [primary fallback]")
    parser.add_argument("--out", required=True, help="Output merged section_boundaries.jsonl")
    parser.add_argument("--elements-core", dest="elements_core", help="Optional elements_core.jsonl to filter/sort by seq")
    parser.add_argument("--progress-file")
    parser.add_argument("--state-file")
    parser.add_argument("--run-id")
    args = parser.parse_args()

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)

    primary_path = args.primary
    fallback_path = args.fallback
    if args.inputs and len(args.inputs) >= 2:
        primary_path, fallback_path = args.inputs[0], args.inputs[1]
    if not primary_path or not fallback_path:
        raise SystemExit("merge_boundaries_pref_v1 requires --primary/--fallback or --inputs primary fallback")

    primary = {b["section_id"]: b for b in read_jsonl(primary_path)}
    fallback = {b["section_id"]: b for b in read_jsonl(fallback_path)}

    id_to_seq = None
    if args.elements_core:
        from schemas import ElementCore
        id_to_seq = {ElementCore(**json.loads(l)).id: ElementCore(**json.loads(l)).seq for l in open(args.elements_core)}

    merged_by_sid = dict(primary)
    for sid, b in fallback.items():
        if sid not in merged_by_sid:
            merged_by_sid[sid] = b

    merged = list(merged_by_sid.values())
    if id_to_seq:
        filtered = []
        for b in merged:
            seq = id_to_seq.get(b.get("start_element_id"))
            if seq is None:
                continue
            b["_seq"] = seq
            filtered.append(b)
        merged = filtered
        merged.sort(key=lambda x: x["_seq"])
        filtered_nonoverlap = []
        prev_seq = -1
        for b in merged:
            seq = b["_seq"]
            if seq <= prev_seq:
                continue
            prev_seq = seq
            b.pop("_seq", None)
            filtered_nonoverlap.append(b)
        merged = filtered_nonoverlap
    else:
        merged.sort(key=lambda x: int(x["section_id"]) if x["section_id"].isdigit() else 999999)

    save_jsonl(args.out, merged)
    logger.log("adapter", "done", current=len(merged), total=len(merged),
               message=f"Merged boundaries: {len(primary)} primary, {len(fallback)} fallback -> {len(merged)} kept",
               artifact=args.out, module_id="merge_boundaries_pref_v1")
    print(f"[merge-boundaries] wrote {len(merged)} rows to {args.out}")


if __name__ == "__main__":
    main()
