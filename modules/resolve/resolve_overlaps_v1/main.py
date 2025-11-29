import argparse
from typing import List, Dict, Set

from modules.common.utils import read_jsonl, save_jsonl, ProgressLogger


def pages_set(p):
    return set(range(p["page_start"], p["page_end"] + 1))


def resolve(portions: List[Dict], forced_range=None) -> List[Dict]:
    # Detect element-based portionization: high confidence, many unique portion_ids
    # For element-based, allow same-page sections (they're distinct sections, not overlaps)
    unique_portions = len(set(p.get("portion_id") for p in portions if p.get("portion_id")))
    avg_conf = sum(p.get("confidence", 0) for p in portions) / len(portions) if portions else 0
    is_element_based = unique_portions > len(portions) * 0.9 and avg_conf >= 0.8
    
    # Sort by confidence desc, then shorter span, then lower page_start
    portions_sorted = sorted(
        portions,
        key=lambda p: (
            -p.get("confidence", 0),
            (p["page_end"] - p["page_start"]),
            p["page_start"],
        ),
    )

    kept: List[Dict] = []
    occupied: Set[int] = set()
    seen_portion_ids: Set[str] = set()

    for p in portions_sorted:
        span = pages_set(p)
        portion_id = p.get("portion_id")
        
        # For element-based portionization: check portion_id uniqueness instead of page overlap
        if is_element_based and portion_id:
            if portion_id in seen_portion_ids:
                continue  # Skip duplicate portion_id
            seen_portion_ids.add(portion_id)
            kept.append(p)
            # Don't mark pages as occupied - allow same-page sections
        elif occupied & span:
            # Traditional overlap filtering for sliding-window portionization
            continue
        else:
            kept.append(p)
            occupied |= span

    # Ensure coverage if forced_range is provided
    if forced_range:
        all_needed = set(range(forced_range[0], forced_range[1] + 1))
        missing = all_needed - occupied
        if missing:
            # try to add discarded portions that don't overlap kept, covering missing
            discarded = [p for p in portions_sorted if p not in kept]
            for page in sorted(missing):
                candidates = [
                    p for p in discarded
                    if p["page_start"] <= page <= p["page_end"]
                    and not (pages_set(p) & occupied)
                ]
                if candidates:
                    best = candidates[0]  # already sorted by confidence/length/start
                    kept.append(best)
                    occupied |= pages_set(best)
                    discarded.remove(best)
                else:
                    # try overlapping candidate trimmed to this page
                    all_cands = [p for p in portions if p["page_start"] <= page <= p["page_end"]]
                    if all_cands:
                        best = sorted(
                            all_cands,
                            key=lambda p: (-p.get("confidence", 0),
                                           (p["page_end"] - p["page_start"]),
                                           p["page_start"])
                        )[0]
                        kept.append({
                            **best,
                            "page_start": page,
                            "page_end": page,
                            "portion_id": best.get("portion_id", f"FILL_{page}"),
                            "continuation_of": best.get("continuation_of"),
                            "continuation_confidence": best.get("continuation_confidence"),
                        })
                        occupied.add(page)
                    else:
                        kept.append({
                            "portion_id": f"FILL_{page}",
                            "page_start": page,
                            "page_end": page,
                            "title": None,
                            "type": None,
                            "confidence": 0.0,
                            "source_images": [],
                            "orig_portion_id": None,
                            "continuation_of": None,
                            "continuation_confidence": None,
                        })
                        occupied.add(page)

    # Final sort by page order
    return sorted(kept, key=lambda p: (p["page_start"], p["page_end"]))


def main():
    parser = argparse.ArgumentParser(description="Resolve overlapping portions by confidence; ensure coverage if range is given.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--range_start", type=int)
    parser.add_argument("--range_end", type=int)
    parser.add_argument("--progress-file", help="Path to pipeline_events.jsonl")
    parser.add_argument("--state-file", help="Path to pipeline_state.json")
    parser.add_argument("--run-id", help="Run identifier for logging")
    args = parser.parse_args()

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)

    portions = list(read_jsonl(args.input))
    logger.log("resolve", "running", current=0, total=len(portions),
               message="Resolving overlaps", artifact=args.out)
    forced = None
    if args.range_start and args.range_end:
        forced = (args.range_start, args.range_end)
    cleaned = resolve(portions, forced_range=forced)
    save_jsonl(args.out, cleaned)
    logger.log("resolve", "done", current=len(portions), total=len(portions),
               message=f"Resolved → {len(cleaned)} rows", artifact=args.out)
    print(f"Wrote {len(cleaned)} non-overlapping portions to {args.out}")


if __name__ == "__main__":
    main()
