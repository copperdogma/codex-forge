import argparse
from collections import defaultdict
from modules.common.utils import read_jsonl, save_jsonl, ProgressLogger
from schemas import ResolvedPortion


def main():
    parser = argparse.ArgumentParser(description="Convert portion_hyp_v1 rows to resolved_portion_v1, keeping the best occurrence per portion_id.")
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
    hyps = list(read_jsonl(in_path))
    grouped = defaultdict(list)
    for idx, h in enumerate(hyps):
        grouped[str(h.get("portion_id") or f"P{h['page_start']:03d}-{h['page_end']:03d}")].append((idx, h))

    def best_occurrence(items):
        """
        Pick the best hypothesis for a portion_id.
        Priority: higher confidence, later page_start (avoids TOC/frontmatter echoes),
        shorter span, then stable by original order for determinism.
        """
        def score(item):
            order_idx, h = item
            conf = h.get("confidence", 0) or 0
            page_start = h.get("page_start", 0) or 0
            span = (h.get("page_end", page_start) or page_start) - page_start
            return (conf, page_start, -span, -order_idx)
        return max(items, key=score)

    selected = []
    for portion_id, items in grouped.items():
        order_idx, h = best_occurrence(items)
        selected.append((portion_id, order_idx, h))

    # Sort for stable downstream processing: by page, then portion_id
    selected.sort(key=lambda t: (t[2].get("page_start", 0) or 0, t[0]))

    rows = []
    total = len(selected)
    for idx, (portion_id, _, h) in enumerate(selected, start=1):
        res = ResolvedPortion(
            portion_id=portion_id,
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
            macro_section=h.get("macro_section"),
            module_id="portion_hyp_to_resolved_v1",
            run_id=args.run_id,
        )
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
