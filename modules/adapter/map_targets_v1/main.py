import argparse
import os
import sys
from typing import Dict, Any

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if os.getcwd() not in sys.path:
    sys.path.insert(0, os.getcwd())

from modules.common.utils import read_jsonl, append_jsonl, ensure_dir  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Mark targets as resolved if they match known section_ids.")
    parser.add_argument("--inputs", nargs="+", required=True, help="Enriched_portion JSONLs (first is source, rest optional)")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    # Build section_id set from all inputs
    section_ids = set()
    for path in args.inputs:
        for row in read_jsonl(path):
            sid = row.get("section_id")
            if sid:
                section_ids.add(str(sid))

    ensure_dir(os.path.dirname(args.out) or ".")
    for row in read_jsonl(args.inputs[0]):
        targets = row.get("targets") or []
        resolved = [t for t in targets if str(t) in section_ids]
        unresolved = [t for t in targets if str(t) not in section_ids]
        row = dict(row)
        row["target_hits"] = resolved
        row["target_misses"] = unresolved
        append_jsonl(args.out, row)
    print(f"Mapped targets → {args.out} (sections known: {len(section_ids)})")


if __name__ == "__main__":
    main()
