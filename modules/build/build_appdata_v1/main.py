import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

from modules.common.utils import read_jsonl, ensure_dir


def convert_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert an enriched_portion row into a compact app node.
    """
    choices = row.get("choices") or []
    targets = [c.get("target") for c in choices if isinstance(c, dict) and c.get("target")]
    is_terminal = len(choices) == 0

    return {
        "id": row.get("portion_id"),
        "title": row.get("title"),
        "type": row.get("type"),
        "page_start": row.get("page_start"),
        "page_end": row.get("page_end"),
        "text": row.get("raw_text") or "",
        "choices": choices,
        "targets": targets,
        "is_terminal": is_terminal,
        "combat": row.get("combat"),
        "test_luck": row.get("test_luck"),
        "item_effects": row.get("item_effects") or [],
        "source_images": row.get("source_images") or [],
    }


def main():
    parser = argparse.ArgumentParser(description="Build app-ready data.json from enriched portions.")
    parser.add_argument("--enriched", help="Path to portions_enriched.jsonl")
    parser.add_argument("--input", dest="enriched", help="Alias for --enriched")
    parser.add_argument("--out", default="data.json", help="Output path for app data JSON")
    parser.add_argument("--run-id", dest="run_id", help="Run identifier to embed in metadata")
    parser.add_argument("--run_id", dest="run_id", help="Alias for --run-id")
    parser.add_argument("--state-file", help="Ignored pipeline plumbing flag")
    parser.add_argument("--progress-file", help="Ignored pipeline plumbing flag")
    args = parser.parse_args()

    if not args.enriched:
        raise SystemExit("Missing --enriched input")

    rows: List[Dict[str, Any]] = list(read_jsonl(args.enriched))
    nodes = [convert_row(r) for r in rows]

    payload = {
        "schema_version": "app_data_v1",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "run_id": args.run_id,
        "source_enriched": args.enriched,
        "nodes": nodes,
    }

    ensure_dir(Path(args.out).parent.as_posix() or ".")
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"Wrote {len(nodes)} nodes → {args.out}")


if __name__ == "__main__":
    main()
