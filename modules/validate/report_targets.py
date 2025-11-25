import argparse
import json
from typing import Set, List

from modules.common.utils import read_jsonl


def main():
    parser = argparse.ArgumentParser(description="Report target coverage vs available portion_ids.")
    parser.add_argument("--enriched", nargs="+", required=True, help="enriched_portion JSONL files")
    args = parser.parse_args()

    ids: Set[str] = set()
    targets: Set[str] = set()
    for path in args.enriched:
        for row in read_jsonl(path):
            pid = str(row.get("portion_id"))
            if pid:
                ids.add(pid)
            for ch in row.get("choices") or []:
                tgt = ch.get("target")
                if tgt:
                    targets.add(str(tgt))
            for tgt in row.get("targets") or []:
                if tgt:
                    targets.add(str(tgt))

    missing = sorted(list(targets - ids), key=lambda x: (len(x), x))
    present = targets & ids

    def stats(nums: Set[str]):
        ints: List[int] = []
        for n in nums:
            try:
                ints.append(int(n))
            except Exception:
                pass
        return {"count": len(nums), "min": min(ints) if ints else None, "max": max(ints) if ints else None}

    print(json.dumps({
        "ids_count": len(ids),
        "targets_count": len(targets),
        "targets_present": len(present),
        "targets_missing": len(missing),
        "targets_stats": stats(targets),
        "missing_sample": missing[:50],
    }, indent=2))


if __name__ == "__main__":
    main()
