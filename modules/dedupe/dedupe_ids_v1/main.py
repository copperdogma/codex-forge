import argparse
from typing import Dict, List
from collections import defaultdict

from modules.common.utils import read_jsonl, save_jsonl, ProgressLogger


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
    parser.add_argument("--progress-file", help="Path to pipeline_events.jsonl")
    parser.add_argument("--state-file", help="Path to pipeline_state.json")
    parser.add_argument("--run-id", help="Run identifier for logging")
    args = parser.parse_args()

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)

    portions = list(read_jsonl(args.input))
    logger.log("dedupe", "running", current=0, total=len(portions),
               message="Deduping portion ids", artifact=args.out)
    cleaned = dedupe(portions)
    save_jsonl(args.out, cleaned)
    logger.log("dedupe", "done", current=len(portions), total=len(portions),
               message=f"Deduped → {len(cleaned)} rows", artifact=args.out)
    print(f"Wrote {len(cleaned)} portions to {args.out}")


if __name__ == "__main__":
    main()
