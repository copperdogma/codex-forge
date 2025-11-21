import argparse
from typing import List, Dict, Set
from utils import read_jsonl, save_jsonl


def pages_set(p):
    return set(range(p["page_start"], p["page_end"] + 1))


def resolve(portions: List[Dict], forced_range=None) -> List[Dict]:
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

    for p in portions_sorted:
        span = pages_set(p)
        if occupied & span:
            continue
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
                            "portion_id": best.get("portion_id", f"FILL_{page}")
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
    args = parser.parse_args()

    portions = list(read_jsonl(args.input))
    forced = None
    if args.range_start and args.range_end:
        forced = (args.range_start, args.range_end)
    cleaned = resolve(portions, forced_range=forced)
    save_jsonl(args.out, cleaned)
    print(f"Wrote {len(cleaned)} non-overlapping portions to {args.out}")


if __name__ == "__main__":
    main()
