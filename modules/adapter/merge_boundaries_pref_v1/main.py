#!/usr/bin/env python3
import argparse
import json
from modules.common.utils import read_jsonl, save_jsonl, ProgressLogger
from modules.common.macro_section import macro_section_for_page, page_num_from_element_id


def main():
    parser = argparse.ArgumentParser(description="Merge boundary sets preferring primary, filling gaps with fallback.")
    parser.add_argument("--primary", help="Primary section_boundaries.jsonl")
    parser.add_argument("--fallback", help="Fallback section_boundaries.jsonl (e.g., AI scan)")
    parser.add_argument("--inputs", nargs="+", help="Driver compatibility: [primary fallback]")
    parser.add_argument("--out", required=True, help="Output merged section_boundaries.jsonl")
    parser.add_argument("--elements-core", dest="elements_core", help="Optional elements_core.jsonl to filter/sort by seq")
    parser.add_argument("--coarse-segments", "--coarse_segments", dest="coarse_segments",
                        help="Optional coarse_segments.json or merged_segments.json for macro_section tagging")
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
    id_to_page = None
    if args.elements_core:
        from schemas import ElementCore
        id_to_seq = {}
        id_to_page = {}
        with open(args.elements_core, "r", encoding="utf-8") as f:
            for line in f:
                elem = ElementCore(**json.loads(line))
                id_to_seq[elem.id] = elem.seq
                id_to_page[elem.id] = elem.page

    coarse_segments = None
    if args.coarse_segments:
        try:
            with open(args.coarse_segments, "r", encoding="utf-8") as f:
                coarse_segments = json.load(f)
        except Exception as exc:
            logger.log("adapter", "warning", current=0, total=1,
                       message=f"Failed to load coarse segments: {exc}", artifact=args.out,
                       module_id="merge_boundaries_pref_v1")

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

    if coarse_segments:
        for b in merged:
            if b.get("macro_section"):
                continue
            page = b.get("start_page")
            if page is None:
                start_id = b.get("start_element_id")
                if id_to_page and start_id in id_to_page:
                    page = id_to_page.get(start_id)
                if page is None:
                    page = page_num_from_element_id(start_id)
            b["macro_section"] = macro_section_for_page(page, coarse_segments)

    save_jsonl(args.out, merged)
    logger.log("adapter", "done", current=len(merged), total=len(merged),
               message=f"Merged boundaries: {len(primary)} primary, {len(fallback)} fallback -> {len(merged)} kept",
               artifact=args.out, module_id="merge_boundaries_pref_v1")
    print(f"[merge-boundaries] wrote {len(merged)} rows to {args.out}")


if __name__ == "__main__":
    main()
