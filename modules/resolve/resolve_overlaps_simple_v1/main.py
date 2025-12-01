import argparse
import json
from typing import List, Dict

from modules.common.utils import read_jsonl, save_jsonl, ProgressLogger
from schemas import ResolvedPortion


def overlaps(a_start, a_end, b_start, b_end):
    return not (a_end < b_start or b_end < a_start)


def main():
    parser = argparse.ArgumentParser(description="Resolve overlapping portion hypotheses by confidence (greedy).")
    parser.add_argument("--input", required=True, help="portion_hyp.jsonl")
    parser.add_argument("--out", required=True, help="portions_resolved.jsonl")
    parser.add_argument("--progress-file")
    parser.add_argument("--state-file")
    parser.add_argument("--run-id")
    args = parser.parse_args()

    hyps = list(read_jsonl(args.input))
    # sort by confidence desc, longer spans first, then lower page_start
    hyps.sort(key=lambda h: (-h.get("confidence", 0), -(h.get("page_end", 0) - h.get("page_start", 0)), h.get("page_start", 0)))

    accepted: List[Dict] = []
    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)

    for idx, h in enumerate(hyps, start=1):
        ps, pe = h.get("page_start"), h.get("page_end")
        if ps is None or pe is None:
            continue
        conflict = any(overlaps(ps, pe, a["page_start"], a["page_end"]) for a in accepted)
        if conflict:
            continue
        accepted.append(h)
        logger.log("resolve", "running", current=idx, total=len(hyps),
                   message=f"accept {ps}-{pe}", artifact=args.out,
                   module_id="resolve_overlaps_simple_v1", schema_version="resolved_portion_v1")

    resolved = []
    for h in accepted:
        res = ResolvedPortion(
            portion_id=str(h.get("portion_id") or f"P{h['page_start']:03d}-{h['page_end']:03d}"),
            page_start=h["page_start"],
            page_end=h["page_end"],
            title=h.get("title"),
            type=h.get("type"),
            confidence=h.get("confidence", 0),
            source_images=h.get("source_images", []),
            continuation_of=h.get("continuation_of"),
            continuation_confidence=h.get("continuation_confidence"),
            raw_text=h.get("raw_text"),
            element_ids=h.get("element_ids"),
            module_id="resolve_overlaps_simple_v1",
            run_id=args.run_id,
        )
        resolved.append(res.dict())

    save_jsonl(args.out, resolved)
    logger.log("resolve", "done", current=len(hyps), total=len(hyps),
               message=f"resolved {len(resolved)} portions", artifact=args.out,
               module_id="resolve_overlaps_simple_v1", schema_version="resolved_portion_v1")
    print(f"Saved {len(resolved)} resolved portions to {args.out}")


if __name__ == "__main__":
    main()
