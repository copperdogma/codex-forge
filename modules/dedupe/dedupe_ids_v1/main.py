import argparse
import sys
import pathlib
from typing import Dict, List
from collections import defaultdict

repo_root = pathlib.Path(__file__).resolve().parents[3]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from utils import read_jsonl, save_jsonl


def dedupe(portions: List[Dict]) -> List[Dict]:
    # Keep first occurrence of a portion_id; renumber duplicates with suffixes
    seen = defaultdict(int)
    result = []
    for p in portions:
        pid = p["portion_id"]
        if pid is None:
            result.append(p)
            continue
        seen[pid] += 1
        if seen[pid] == 1:
            result.append(p)
        else:
            new_id = f"{pid}_{seen[pid]}"
            q = dict(p)
            q["portion_id"] = new_id
            result.append(q)
    return result


def main():
    parser = argparse.ArgumentParser(description="Deduplicate portion_ids by appending suffixes to repeats.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    portions = list(read_jsonl(args.input))
    cleaned = dedupe(portions)
    save_jsonl(args.out, cleaned)
    print(f"Wrote {len(cleaned)} portions to {args.out}")


if __name__ == "__main__":
    main()
