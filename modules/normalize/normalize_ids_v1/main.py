import argparse
import sys
import pathlib
from typing import List, Dict

repo_root = pathlib.Path(__file__).resolve().parents[3]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from utils import read_jsonl, save_jsonl


def normalize(portions: List[Dict]) -> List[Dict]:
    # Sort by page_start then page_end for stable ordering
    portions = sorted(portions, key=lambda p: (p.get("page_start", 0), p.get("page_end", 0)))

    section_counter = 1
    portion_counter = 1
    seen_ids = set()
    normalized = []

    for p in portions:
        p = dict(p)  # shallow copy
        orig_id = p.get("portion_id")

        if p.get("type") == "section":
            new_id = f"S{section_counter:03d}"
            section_counter += 1
        else:
            if orig_id is None or orig_id in seen_ids:
                new_id = f"P{portion_counter:03d}"
                portion_counter += 1
            else:
                new_id = orig_id

        if new_id in seen_ids:
            # ensure uniqueness by suffixing
            suffix = 2
            candidate = f"{new_id}_{suffix}"
            while candidate in seen_ids:
                suffix += 1
                candidate = f"{new_id}_{suffix}"
            new_id = candidate

        p["orig_portion_id"] = orig_id
        p["portion_id"] = new_id
        seen_ids.add(new_id)
        normalized.append(p)

    return normalized


def main():
    parser = argparse.ArgumentParser(description="Normalize portion IDs (sections S### in order; other portions P### if missing/duplicate).")
    parser.add_argument("--input", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    portions = list(read_jsonl(args.input))
    normalized = normalize(portions)
    save_jsonl(args.out, normalized)
    print(f"Wrote {len(normalized)} normalized portions to {args.out}")


if __name__ == "__main__":
    main()
