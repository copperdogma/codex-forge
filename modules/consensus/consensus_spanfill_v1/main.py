import argparse
from typing import List, Dict, Set

from modules.common.utils import read_jsonl, save_jsonl, ProgressLogger
from schemas import LockedPortion


def span_pages(portion: Dict) -> Set[int]:
    return set(range(portion["page_start"], portion["page_end"] + 1))


def spanfill(hypotheses: List[Dict], min_conf: float = 0.5, forced_range=None) -> List[Dict]:
    # Sort high-confidence first, then shorter spans, then earlier start
    candidates = sorted(
        [h for h in hypotheses if h.get("page_start") is not None and h.get("page_end") is not None],
        key=lambda h: (-h.get("confidence", 0), (h["page_end"] - h["page_start"]), h["page_start"])
    )

    locked: List[Dict] = []
    occupied: Set[int] = set()
    next_idx = 1

    for h in candidates:
        if h.get("confidence", 0) < min_conf:
            continue
        span = span_pages(h)
        if occupied & span:
            continue
        locked.append(LockedPortion(
            portion_id=h.get("portion_id") or f"L{next_idx:03d}",
            page_start=h["page_start"],
            page_end=h["page_end"],
            title=h.get("title"),
            type=h.get("type"),
            confidence=h.get("confidence", 0.0),
            source_images=[]
        ).dict())
        occupied |= span
        next_idx += 1

    # Fill gaps to cover range
    if locked:
        if forced_range:
            all_pages = set(range(forced_range[0], forced_range[1] + 1))
        else:
            all_pages = set(range(min(h["page_start"] for h in hypotheses),
                                  max(h["page_end"] for h in hypotheses) + 1))
        missing = sorted(all_pages - occupied)
        for page in missing:
            covers = [h for h in candidates if h["page_start"] <= page <= h["page_end"]]
            if covers:
                best = covers[0]  # already sorted by confidence then length/start
                locked.append(LockedPortion(
                    portion_id=best.get("portion_id") or f"L{next_idx:03d}",
                    page_start=best["page_start"],
                    page_end=best["page_end"],
                    title=best.get("title"),
                    type=best.get("type"),
                    confidence=best.get("confidence", 0.0),
                    source_images=[]
                ).dict())
                occupied |= span_pages(best)
            else:
                locked.append(LockedPortion(
                    portion_id=f"L{next_idx:03d}",
                    page_start=page,
                    page_end=page,
                    title=None,
                    type=None,
                    confidence=0.0,
                    source_images=[]
                ).dict())
                occupied.add(page)
            next_idx += 1

    return sorted(locked, key=lambda p: (p["page_start"], p["page_end"]))


def main():
    parser = argparse.ArgumentParser(description="Greedy span-fill consensus (no voting).")
    parser.add_argument("--hypotheses", required=True, help="Input portion hypotheses JSONL")
    parser.add_argument("--out", required=True, help="Output locked portions JSONL")
    parser.add_argument("--min_conf", type=float, default=0.5, help="Minimum confidence to seed spans")
    parser.add_argument("--range_start", type=int, help="Force coverage start page")
    parser.add_argument("--range_end", type=int, help="Force coverage end page (inclusive)")
    parser.add_argument("--progress-file", help="Path to pipeline_events.jsonl")
    parser.add_argument("--state-file", help="Path to pipeline_state.json")
    parser.add_argument("--run-id", help="Run identifier for logging")
    args = parser.parse_args()

    hypos = [h for h in read_jsonl(args.hypotheses) if "error" not in h]
    if not hypos:
        raise SystemExit("No hypotheses to process.")
    forced = None
    if args.range_start and args.range_end:
        forced = (args.range_start, args.range_end)

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    logger.log("consensus", "running", current=0, total=len(hypos),
               message="Span-fill consensus", artifact=args.out)
    locked = spanfill(hypos, min_conf=args.min_conf, forced_range=forced)
    save_jsonl(args.out, locked)
    logger.log("consensus", "done", current=len(hypos), total=len(hypos),
               message=f"Locked {len(locked)} portions", artifact=args.out)
    print(f"Locked {len(locked)} portions → {args.out}")


if __name__ == "__main__":
    main()
