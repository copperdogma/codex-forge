import argparse
import glob
import json
import os
from typing import List, Set, Dict, Any

from modules.common.utils import read_jsonl, ensure_dir


def load_enriched(paths: List[str]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for p in paths:
        for row in read_jsonl(p):
            rows.append(row)
    return rows


def save_jsonl(path: str, rows: List[Dict[str, Any]]):
    ensure_dir(os.path.dirname(path) or ".")
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def coverage(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    ids: Set[str] = set()
    targets: Set[str] = set()
    for r in rows:
        pid = r.get("portion_id")
        if pid:
            ids.add(str(pid))
        sid = r.get("section_id")
        if sid:
            ids.add(str(sid))
        for t in r.get("targets") or []:
            targets.add(str(t))
        for ch in r.get("choices") or []:
            tgt = ch.get("target")
            if tgt:
                targets.add(str(tgt))
    missing = sorted(list(targets - ids), key=lambda x: int(x) if x.isdigit() else x)
    return {
        "ids_count": len(ids),
        "targets_count": len(targets),
        "targets_present": len(targets - set(missing)),
        "targets_missing": len(missing),
        "missing_sample": missing[:20],
    }


def main():
    parser = argparse.ArgumentParser(description="Merge section-enriched outputs and report coverage.")
    parser.add_argument("--inputs", nargs="+", required=True, help="Enriched JSONL paths or globs (section_enrich output)")
    parser.add_argument("--out-enriched", required=True, help="Output merged enriched JSONL")
    parser.add_argument("--out-data", required=True, help="Output app data JSON (nodes list)")
    parser.add_argument("--run-id", default="sections-merged")
    parser.add_argument("--dedupe", action="store_true", help="Dedupe by portion_id (default keep all)")
    args = parser.parse_args()

    expanded: List[str] = []
    for pat in args.inputs:
        expanded.extend(glob.glob(pat))
    if not expanded:
        raise SystemExit("No inputs matched")

    rows = load_enriched(expanded)
    if args.dedupe:
        seen = set()
        deduped = []
        for r in rows:
            pid = r.get("portion_id")
            if pid in seen:
                continue
            seen.add(pid)
            deduped.append(r)
        rows = deduped

    save_jsonl(args.out_enriched, rows)

    nodes = []
    for r in rows:
        nodes.append({
            "id": r.get("portion_id"),
            "section_id": r.get("section_id"),
            "text": r.get("raw_text"),
            "targets": r.get("targets") or [],
            "page_start": r.get("page_start"),
            "page_end": r.get("page_end"),
            "type": r.get("type"),
        })
    ensure_dir(os.path.dirname(args.out_data) or ".")
    with open(args.out_data, "w", encoding="utf-8") as f:
        json.dump({
            "schema_version": "app_data_v1",
            "run_id": args.run_id,
            "nodes": nodes,
        }, f, ensure_ascii=False, indent=2)

    cov = coverage(rows)
    print(json.dumps(cov, indent=2))


if __name__ == "__main__":
    main()
