import argparse
from modules.common.utils import read_jsonl, save_jsonl, ProgressLogger
from schemas import ResolvedPortion


def main():
    parser = argparse.ArgumentParser(description="Convert portion_hyp_v1 rows to resolved_portion_v1 without filtering.")
    parser.add_argument("--input", help="portion_hyp.jsonl")
    parser.add_argument("--inputs", nargs="*", help="Alternative inputs list (use first)")
    parser.add_argument("--out", required=True, help="portions_resolved.jsonl")
    parser.add_argument("--progress-file")
    parser.add_argument("--state-file")
    parser.add_argument("--run-id")
    args = parser.parse_args()

    in_path = args.input
    if not in_path and args.inputs:
        in_path = args.inputs[0]
    if not in_path:
        raise SystemExit("Must provide --input or --inputs")

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    rows = []
    hyps = list(read_jsonl(in_path))
    total = len(hyps)
    seen = set()
    for idx, h in enumerate(hyps, start=1):
        res = ResolvedPortion(
            portion_id=str(h.get("portion_id") or f"P{h['page_start']:03d}-{h['page_end']:03d}"),
            page_start=h["page_start"],
            page_end=h["page_end"],
            title=h.get("title"),
            type=h.get("type"),
            confidence=h.get("confidence", 0),
            source_images=h.get("source_images", []),
            orig_portion_id=h.get("portion_id"),
            continuation_of=h.get("continuation_of"),
            continuation_confidence=h.get("continuation_confidence"),
            raw_text=h.get("raw_text"),
            element_ids=h.get("element_ids"),
            module_id="portion_hyp_to_resolved_v1",
            run_id=args.run_id,
        )
        if res.portion_id in seen:
            continue
        seen.add(res.portion_id)
        rows.append(res.dict())
        logger.log("adapter", "running", current=idx, total=total,
                   message=f"portion {res.portion_id}", artifact=args.out,
                   module_id="portion_hyp_to_resolved_v1", schema_version="resolved_portion_v1")

    save_jsonl(args.out, rows)
    logger.log("adapter", "done", current=total, total=total,
               message=f"converted {len(rows)} portions", artifact=args.out,
               module_id="portion_hyp_to_resolved_v1", schema_version="resolved_portion_v1")
    print(f"Converted {len(rows)} portions to resolved_portion_v1 → {args.out}")


if __name__ == "__main__":
    main()
