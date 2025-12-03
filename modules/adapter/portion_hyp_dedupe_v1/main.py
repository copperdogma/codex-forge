import argparse
from collections import defaultdict

from modules.common.utils import read_jsonl, save_jsonl, ProgressLogger


def best_occurrence(items):
    # items: list of (idx, h)
    def score(item):
        order_idx, h = item
        conf = h.get("confidence", 0) or 0
        page_start = h.get("page_start", 0) or 0
        span = (h.get("page_end", page_start) or page_start) - page_start
        return (conf, page_start, -span, -order_idx)

    return max(items, key=score)


def main():
    ap = argparse.ArgumentParser(description="Dedupe portion_hyp_v1 by portion_id, keeping best occurrence.")
    ap.add_argument("--input", required=True, help="portion_hyp.jsonl")
    ap.add_argument("--out", required=True, help="deduped portion_hyp.jsonl")
    ap.add_argument("--progress-file")
    ap.add_argument("--state-file")
    ap.add_argument("--run-id")
    args = ap.parse_args()

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    grouped = defaultdict(list)
    for idx, h in enumerate(read_jsonl(args.input)):
        pid = str(h.get("portion_id"))
        grouped[pid].append((idx, h))

    rows = []
    selected = []
    for pid, items in grouped.items():
        order_idx, h = best_occurrence(items)
        selected.append((pid, order_idx, h))
    selected.sort(key=lambda t: (t[2].get("page_start", 0) or 0, t[0]))

    total = len(selected)
    for idx, (pid, _, h) in enumerate(selected, start=1):
        rows.append(h)
        logger.log("adapter", "running", current=idx, total=total,
                   message=f"keep {pid}", artifact=args.out,
                   module_id="portion_hyp_dedupe_v1", schema_version="portion_hyp_v1")

    save_jsonl(args.out, rows)
    logger.log("adapter", "done", current=total, total=total,
               message=f"deduped {total} headers", artifact=args.out,
               module_id="portion_hyp_dedupe_v1", schema_version="portion_hyp_v1")
    print(f"Deduped to {total} headers → {args.out}")


if __name__ == "__main__":
    main()
