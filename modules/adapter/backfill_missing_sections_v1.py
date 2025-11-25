import argparse
import os
from typing import Set, List, Dict, Any

from modules.common.utils import read_jsonl, append_jsonl, ensure_dir


def collect_ids_and_targets(paths: List[str]) -> (Set[str], Set[str]):
    ids: Set[str] = set()
    targets: Set[str] = set()
    for path in paths:
        for row in read_jsonl(path):
            pid = row.get("portion_id")
            if pid and str(pid).isdigit():
                ids.add(str(pid))
            sid = row.get("section_id")
            if sid and str(sid).isdigit():
                ids.add(str(sid))
            for t in row.get("targets") or []:
                if t and str(t).isdigit():
                    targets.add(str(t))
            for ch in row.get("choices") or []:
                tgt = ch.get("target")
                if tgt and str(tgt).isdigit():
                    targets.add(str(tgt))
    return ids, targets


def main():
    parser = argparse.ArgumentParser(description="Backfill missing sections for targets without a section_id/portion.")
    parser.add_argument("--inputs", nargs="+", required=True, help="Source enriched_portion JSONL files")
    parser.add_argument("--out", required=True, help="Output JSONL with backfilled sections appended")
    args = parser.parse_args()

    ids, targets = collect_ids_and_targets(args.inputs)
    missing = sorted(list(targets - ids), key=lambda x: int(x))

    ensure_dir(os.path.dirname(args.out) or ".")
    # copy originals
    for path in args.inputs:
        for row in read_jsonl(path):
            append_jsonl(args.out, row)

    for tgt in missing:
        stub = {
            "schema_version": "enriched_portion_v1",
            "module_id": "backfill_missing_sections_v1",
            "run_id": "backfill",
            "portion_id": tgt,
            "section_id": tgt,
            "page_start": 0,
            "page_end": 0,
            "title": None,
            "type": "section",
            "confidence": 0.0,
            "source_images": [],
            "raw_text": "",
            "choices": [],
            "combat": None,
            "test_luck": None,
            "item_effects": [],
            "targets": [],
        }
        append_jsonl(args.out, stub)
    print(f"Backfilled {len(missing)} sections → {args.out}")


if __name__ == "__main__":
    main()
