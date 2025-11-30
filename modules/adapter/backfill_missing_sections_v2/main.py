import argparse
import json
import re
from typing import Dict, List, Optional

from modules.common.utils import read_jsonl, save_jsonl, ProgressLogger


def load_elements(path: str) -> List[Dict]:
    return list(read_jsonl(path))


def load_boundaries(path: str) -> List[Dict]:
    return list(read_jsonl(path))


def find_element_ids_for_number(elements: List[Dict], number: str) -> List[str]:
    """Return element ids whose text contains the target number (exact or normalized)."""
    hits = []
    target = number.strip()
    for el in elements:
        txt = str(el.get("text", ""))
        if not txt:
            continue
        stripped = txt.strip()
        if stripped == target:
            hits.append(el.get("id"))
            continue
        # normalize: remove non-digits and compare
        digits = "".join(ch for ch in stripped if ch.isdigit())
        if digits == target:
            hits.append(el.get("id"))
            continue
        # extract any short digit groups within text
        groups = [g for g in re.findall(r"\d{1,3}", stripped)]
        if target in groups:
            hits.append(el.get("id"))
    return hits


def build_boundary(section_id: str, start_id: str, end_id: Optional[str]) -> Dict:
    return {
        "schema_version": "section_boundary_v1",
        "module_id": "backfill_missing_sections_v2",
        "section_id": section_id,
        "start_element_id": start_id,
        "end_element_id": end_id,
        "confidence": 0.4,
        "evidence": "digit-only element match in elements_core",
    }


def main():
    parser = argparse.ArgumentParser(description="Backfill missing section boundaries using elements_core digit hits.")
    parser.add_argument("--boundaries", required=True, help="Input section_boundaries.jsonl")
    parser.add_argument("--elements", required=True, help="Input elements_core.jsonl")
    parser.add_argument("--out", required=True, help="Output boundaries JSONL with backfilled entries")
    parser.add_argument("--expected-range-start", type=int, default=1)
    parser.add_argument("--expected-range-end", type=int, default=400)
    parser.add_argument("--target-ids", help="Optional comma-separated list or file path of specific missing section ids to backfill")
    parser.add_argument("--progress-file", help="Path to pipeline_events.jsonl")
    parser.add_argument("--state-file", help="Path to pipeline_state.json")
    parser.add_argument("--run-id", help="Run identifier for logging")
    args = parser.parse_args()

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)

    boundaries = load_boundaries(args.boundaries)
    elements = load_elements(args.elements)

    existing_ids = {b.get("section_id") for b in boundaries if b.get("section_id")}

    # derive missing set
    if args.target_ids:
        if "," in args.target_ids or args.target_ids.strip().isdigit():
            targets = [t.strip() for t in args.target_ids.split(",") if t.strip()]
        else:
            # treat as file path
            with open(args.target_ids, "r", encoding="utf-8") as f:
                targets = [ln.strip() for ln in f if ln.strip()]
        expected = set(targets)
    else:
        expected = {str(i) for i in range(args.expected_range_start, args.expected_range_end + 1)}

    missing = sorted(list(expected - existing_ids), key=lambda x: int(x))

    # Precompute element hits for missing numbers
    hits: Dict[str, List[str]] = {}
    for num in missing:
        ids = find_element_ids_for_number(elements, num)
        if ids:
            hits[num] = ids

    # Build quick lookup for next boundary start per section ordering
    numeric_sorted = sorted([b for b in boundaries if str(b.get("section_id", "")).isdigit()], key=lambda b: int(b["section_id"]))
    next_start_map: Dict[str, Optional[str]] = {}
    for idx, b in enumerate(numeric_sorted):
        next_id = numeric_sorted[idx + 1]["start_element_id"] if idx + 1 < len(numeric_sorted) else None
        next_start_map[b["section_id"]] = next_id

    added: List[Dict] = []
    for num, ids in hits.items():
        start_id = ids[0]
        # find next existing boundary after this number
        next_after = None
        for b in numeric_sorted:
            if int(b["section_id"]) > int(num):
                next_after = b["start_element_id"]
                break
        boundary = build_boundary(num, start_id, next_after)
        added.append(boundary)

    all_boundaries = boundaries + added
    all_boundaries_sorted = sorted(all_boundaries, key=lambda b: int(b.get("section_id", 999999)))

    save_jsonl(args.out, all_boundaries_sorted)

    still_missing = len(missing) - len(added)
    logger.log("adapter", "done", current=len(all_boundaries_sorted), total=len(all_boundaries_sorted),
               message=f"Added {len(added)} boundaries; {still_missing} still missing", artifact=args.out,
               module_id="backfill_missing_sections_v2", schema_version="section_boundary_v1")

    print(f"Added {len(added)} boundaries; {still_missing} still missing → {args.out}")


if __name__ == "__main__":
    main()
