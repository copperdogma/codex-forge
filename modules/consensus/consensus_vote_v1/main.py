import argparse
from collections import defaultdict, Counter
from typing import List, Dict, Tuple

from modules.common.utils import read_jsonl, save_jsonl, ProgressLogger
from schemas import LockedPortion


def vote_portions(hypotheses: List[Dict], min_conf: float = 0.6, forced_range=None):
    # Group identical spans
    span_votes = defaultdict(list)
    for h in hypotheses:
        if "page_start" not in h or "page_end" not in h:
            continue
        if h.get("confidence", 0) < min_conf:
            continue
        span_votes[(h["page_start"], h["page_end"], h.get("title"), h.get("type"))].append(h)

    # Greedy select non-overlapping spans, highest votes then confidence then length
    candidates = []
    for key, items in span_votes.items():
        votes = len(items)
        best_conf = max(i.get("confidence", 0) for i in items)
        candidates.append((votes, best_conf, key, items))
    candidates.sort(key=lambda x: (-x[0], -x[1], x[2][1]-x[2][0]))

    locked = []
    occupied = set()
    next_portion_idx = 1
    for votes, conf, key, items in candidates:
        ps, pe, title, typ = key
        span_pages = set(range(ps, pe+1))
        if occupied & span_pages:
            continue
        locked.append(LockedPortion(
            portion_id=items[0].get("portion_id") or f"P{next_portion_idx:03d}",
            page_start=ps,
            page_end=pe,
            title=title,
            type=typ,
            confidence=conf,
            source_images=[]
        ).dict())
        occupied |= span_pages
        next_portion_idx += 1

    # Fill gaps with best available hypothesis covering missing pages
    if locked:
        if forced_range:
            all_pages = set(range(forced_range[0], forced_range[1] + 1))
        else:
            all_pages = set(range(min(h['page_start'] for h in hypotheses if 'page_start' in h and 'page_end' in h),
                                  max(h['page_end'] for h in hypotheses if 'page_start' in h and 'page_end' in h) + 1))
        missing = sorted(all_pages - occupied)
        if missing:
            # index hypotheses by page coverage
            for page in missing:
                candidates_cover = [h for h in hypotheses
                                    if h.get("page_start") is not None and h.get("page_end") is not None
                                    and h["page_start"] <= page <= h["page_end"]]
                if not candidates_cover:
                    # create placeholder
                    locked.append(LockedPortion(
                        portion_id=f"P{next_portion_idx:03d}",
                        page_start=page,
                        page_end=page,
                        title=None,
                        type=None,
                        confidence=0.0,
                        source_images=[]
                    ).dict())
                    next_portion_idx += 1
                    occupied.add(page)
                else:
                    best = max(candidates_cover, key=lambda h: h.get("confidence", 0))
                    ps, pe = best["page_start"], best["page_end"]
                    locked.append(LockedPortion(
                        portion_id=best.get("portion_id") or f"P{next_portion_idx:03d}",
                        page_start=ps,
                        page_end=pe,
                        title=best.get("title"),
                        type=best.get("type"),
                        confidence=best.get("confidence", 0.0),
                        source_images=[]
                    ).dict())
                    occupied |= set(range(ps, pe+1))
                    next_portion_idx += 1
    return locked


def main():
    parser = argparse.ArgumentParser(description="Consensus locking of portion hypotheses.")
    parser.add_argument("--hypotheses", required=True, help="window_hypotheses.jsonl")
    parser.add_argument("--out", required=True, help="portions_locked.jsonl")
    parser.add_argument("--min_conf", type=float, default=0.6)
    parser.add_argument("--range_start", type=int, help="Force coverage start page")
    parser.add_argument("--range_end", type=int, help="Force coverage end page (inclusive)")
    parser.add_argument("--progress-file", help="Path to pipeline_events.jsonl")
    parser.add_argument("--state-file", help="Path to pipeline_state.json")
    parser.add_argument("--run-id", help="Run identifier for logging")
    args = parser.parse_args()

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)

    hypos = [h for h in read_jsonl(args.hypotheses) if "error" not in h]
    forced = None
    if args.range_start and args.range_end:
        forced = (args.range_start, args.range_end)
    logger.log("consensus", "running", current=0, total=len(hypos),
               message="Computing votes", artifact=args.out)
    locked = vote_portions(hypos, min_conf=args.min_conf, forced_range=forced)
    save_jsonl(args.out, locked)
    logger.log("consensus", "done", current=len(hypos), total=len(hypos),
               message=f"Locked {len(locked)} portions", artifact=args.out)
    print(f"Locked {len(locked)} portions → {args.out}")


if __name__ == "__main__":
    main()
