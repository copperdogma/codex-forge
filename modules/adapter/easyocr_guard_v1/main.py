import argparse
import json
import os
import sys
from typing import List, Dict, Any

from modules.common.utils import read_jsonl, append_jsonl, ensure_dir


def has_easyocr_text(row: Dict[str, Any]) -> bool:
    engines = row.get("engines_raw") or {}
    if not isinstance(engines, dict):
        return False
    txt = engines.get("easyocr")
    return isinstance(txt, str) and bool(txt.strip())


def has_any_text(row: Dict[str, Any]) -> bool:
    engines = row.get("engines_raw") or {}
    if not isinstance(engines, dict):
        return False
    for v in engines.values():
        if isinstance(v, str) and v.strip():
            return True
    return False


def is_blank_page(row: Dict[str, Any]) -> bool:
    """
    Treat as blank if no engine produced any text (tesseract/apple/easyocr all empty).
    """
    engines = row.get("engines_raw") or {}
    if not isinstance(engines, dict):
        return False
    return not any(isinstance(v, str) and v.strip() for v in engines.values())


def main():
    parser = argparse.ArgumentParser(description="Fail if easyocr text is missing/empty for too many pages.")
    parser.add_argument("--inputs", nargs="+", required=True, help="pagelines_v1 JSONL(s) to check")
    parser.add_argument("--out", required=True, help="Output JSONL (pass-through of primary input)")
    parser.add_argument("--min-coverage", dest="min_coverage", type=float, default=1.0,
                        help="Required fraction of pages with non-empty easyocr text (default: 1.0)")
    parser.add_argument("--min_coverage", dest="min_coverage", type=float, default=1.0,
                        help=argparse.SUPPRESS)  # alias for driver defaults
    parser.add_argument("--allow-missing", dest="allow_missing", action="store_true",
                        help="Exit 0 even if coverage is below threshold")
    parser.add_argument("--allow_missing", dest="allow_missing", action="store_true",
                        help=argparse.SUPPRESS)  # alias for driver params
    parser.add_argument("--report", help="Optional JSON report path")
    args = parser.parse_args()

    primary = args.inputs[0]
    pages: Dict[Any, Dict[str, Any]] = {}
    missing_pages: List[Any] = []

    # Pass-through rows to output while tracking easyocr coverage per logical page
    ensure_dir(os.path.dirname(args.out) or ".")
    for row in read_jsonl(primary):
        append_jsonl(args.out, row)
        page_num = row.get("page")
        meta = pages.setdefault(page_num, {"has_text": False, "easy_text": False, "blank": True})
        if has_any_text(row):
            meta["has_text"] = True
            meta["blank"] = False
        if has_easyocr_text(row):
            meta["easy_text"] = True

    total = 0
    with_easy = 0
    skipped_no_content = 0
    for page_num, meta in pages.items():
        if meta["blank"]:
            skipped_no_content += 1
            continue  # don't count true-blank pages against coverage
        total += 1
        if meta["easy_text"]:
            with_easy += 1
        else:
            missing_pages.append(page_num)

    coverage = (with_easy / total) if total else 1.0
    report = {
        "inputs": args.inputs,
        "out": args.out,
        "total_pages": total,
        "skipped_no_content": skipped_no_content,
        "easyocr_pages": with_easy,
        "coverage": coverage,
        "min_coverage": args.min_coverage,
        "missing_pages": missing_pages[:50],
    }

    if args.report:
        ensure_dir(os.path.dirname(args.report) or ".")
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

    print(json.dumps(report, indent=2))

    if coverage < args.min_coverage and not args.allow_missing:
        sys.exit(1)


if __name__ == "__main__":
    main()
