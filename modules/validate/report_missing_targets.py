import argparse
import json
from typing import Set

from modules.common.utils import read_jsonl


def main():
    parser = argparse.ArgumentParser(description="List missing targets against known section_ids.")
    parser.add_argument("--enriched", nargs="+", required=True, help="enriched_portion JSONL files")
    args = parser.parse_args()

    section_ids: Set[str] = set()
    targets: Set[str] = set()
    for path in args.enriched:
        for row in read_jsonl(path):
            pid = row.get("portion_id")
            if pid:
                section_ids.add(str(pid))
            sid = row.get("section_id")
            if sid:
                section_ids.add(str(sid))
            for t in row.get("targets") or []:
                targets.add(str(t))
            for ch in row.get("choices") or []:
                tgt = ch.get("target")
                if tgt:
                    targets.add(str(tgt))

    missing = sorted(list(targets - section_ids), key=lambda x: int(x) if x.isdigit() else x)
    print(json.dumps({
        "section_count": len(section_ids),
        "targets_count": len(targets),
        "missing_count": len(missing),
        "missing": missing,
    }, indent=2))


if __name__ == "__main__":
    main()
