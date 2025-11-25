import argparse
import json
from pathlib import Path
from typing import Dict, Any, List, Set

from modules.common.utils import read_jsonl, ensure_dir
from modules.build.build_appdata_v1.main import convert_row


def load_enriched(paths: List[str], rekey_by_page: bool = False, dedupe: bool = False) -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = []
    seen: Set[str] = set()
    for p in paths:
        for row in read_jsonl(p):
            if rekey_by_page and row.get("page_start") is not None:
                row = dict(row)
                row["portion_id"] = f"P{int(row['page_start']):03d}"
            pid = row.get("portion_id")
            if dedupe:
                if pid in seen:
                    continue
                seen.add(pid)
            merged.append(row)
    return merged


def write_jsonl(path: str, rows: List[Dict[str, Any]]):
    ensure_dir(Path(path).parent.as_posix())
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def build_app_data(enriched_rows: List[Dict[str, Any]], source_paths: List[str], run_id: str, out_path: str):
    nodes = [convert_row(r) for r in enriched_rows]
    payload = {
        "schema_version": "app_data_v1",
        "generated_at": None,
        "run_id": run_id,
        "source_enriched": source_paths,
        "nodes": nodes,
    }
    ensure_dir(Path(out_path).parent.as_posix() or ".")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(description="Merge multiple enriched_portion JSONLs and build app data.")
    parser.add_argument("--enriched", nargs="+", required=True, help="List of enriched_portion JSONL files")
    parser.add_argument("--out-enriched", required=True, help="Merged enriched JSONL path")
    parser.add_argument("--out-data", required=True, help="Merged app data JSON path")
    parser.add_argument("--run-id", default="merged-enrich", help="Run id to embed in app data")
    parser.add_argument("--rekey-by-page", action="store_true", help="Rewrite portion_id to page-based key to avoid collisions across chunks")
    parser.add_argument("--dedupe", action="store_true", help="Dedupe by portion_id (default off for section merging)")
    args = parser.parse_args()

    rows = load_enriched(args.enriched, rekey_by_page=args.rekey_by_page, dedupe=args.dedupe)
    write_jsonl(args.out_enriched, rows)
    build_app_data(rows, args.enriched, args.run_id, args.out_data)
    print(f"Merged {len(rows)} enriched rows → {args.out_enriched}")
    print(f"Wrote app data → {args.out_data}")


if __name__ == "__main__":
    main()
