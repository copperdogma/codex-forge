import argparse
import json
import os
import sys
from typing import Set

from modules.common.utils import read_jsonl, ensure_dir


def collect_ids_and_targets(paths: list[str]) -> tuple[Set[str], Set[str]]:
    section_ids: Set[str] = set()
    targets: Set[str] = set()
    for path in paths:
        for row in read_jsonl(path):
            pid = row.get("portion_id")
            if pid is not None:
                section_ids.add(str(pid))
            sid = row.get("section_id")
            if sid is not None:
                section_ids.add(str(sid))
            for t in row.get("targets") or []:
                if t is not None:
                    targets.add(str(t))
            for ch in row.get("choices") or []:
                tgt = ch.get("target")
                if tgt is not None:
                    targets.add(str(tgt))
    return section_ids, targets


def main():
    parser = argparse.ArgumentParser(description="Fail if any targets are missing matching section_ids/portion_ids.")
    parser.add_argument("--inputs", nargs="+", required=True, help="enriched_portion JSONL files")
    parser.add_argument("--out", required=True, help="Where to write a JSON summary report")
    parser.add_argument("--allow-missing", action="store_true", help="Do not exit non-zero when missing targets exist")
    args = parser.parse_args()

    section_ids, targets = collect_ids_and_targets(args.inputs)
    missing = sorted(list(targets - section_ids), key=lambda x: int(x) if x.isdigit() else x)

    report = {
        "section_count": len(section_ids),
        "targets_count": len(targets),
        "targets_present": len(targets) - len(missing),
        "missing_count": len(missing),
        "missing_sample": missing[:50],
    }

    ensure_dir(os.path.dirname(args.out) or ".")
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    if missing and not args.allow_missing:
        print(json.dumps(report, indent=2))
        sys.exit(1)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
