#!/usr/bin/env python3
"""
Fix common continuation-row issues in OCR'd HTML tables.
Generic heuristic: if a row is a continuation (empty key columns, spouse-only),
and the previous row has a DIED value plus BOY/GIRL values, shift the DIED value
to the continuation row. This prevents dates from being attached to the wrong row.
"""
import argparse
import re
from typing import Dict, List, Optional

from bs4 import BeautifulSoup

from modules.common.utils import read_jsonl, save_jsonl, ProgressLogger


HEADER_KEYS = ["name", "born", "married", "spouse", "boy", "girl", "died"]
DATE_LIKE = re.compile(r"\d")


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _is_date_like(text: str) -> bool:
    return bool(DATE_LIKE.search(text or ""))


def _header_index(table) -> Optional[Dict[str, int]]:
    headers = table.find_all("th")
    if not headers:
        return None
    mapping: Dict[str, int] = {}
    for idx, th in enumerate(headers):
        key = _norm(th.get_text(" ", strip=True))
        if key:
            mapping[key] = idx
    # Require core headers to reduce false positives.
    for required in ["name", "spouse", "died"]:
        if required not in mapping:
            return None
    # Normalize BOY/GIRL header variants (e.g., "boy girl")
    if "boy girl" in mapping and "boy" not in mapping and "girl" not in mapping:
        mapping["boy"] = mapping["boy girl"]
        mapping["girl"] = mapping["boy girl"] + 1
    return mapping


def _cells_for_row(row) -> List[str]:
    cells = row.find_all("td")
    return [c.get_text(" ", strip=True) for c in cells]


def _set_cell_text(row, idx: int, value: str):
    cells = row.find_all("td")
    if idx < 0 or idx >= len(cells):
        return
    cells[idx].string = value


def _fix_table(table) -> int:
    fixes = 0
    header_idx = _header_index(table)
    if not header_idx:
        return fixes

    idx_name = header_idx.get("name")
    idx_born = header_idx.get("born")
    idx_married = header_idx.get("married")
    idx_spouse = header_idx.get("spouse")
    idx_boy = header_idx.get("boy")
    idx_girl = header_idx.get("girl")
    idx_died = header_idx.get("died")

    if idx_name is None or idx_spouse is None or idx_died is None:
        return fixes

    rows = table.find_all("tr")
    for i in range(1, len(rows)):
        prev = rows[i - 1]
        cur = rows[i]
        prev_cells = _cells_for_row(prev)
        cur_cells = _cells_for_row(cur)

        # Ensure cell arrays are long enough.
        if max(idx_name, idx_spouse, idx_died) >= len(prev_cells):
            continue
        if max(idx_name, idx_spouse, idx_died) >= len(cur_cells):
            continue

        prev_name = prev_cells[idx_name]
        prev_died = prev_cells[idx_died]
        cur_name = cur_cells[idx_name]
        cur_spouse = cur_cells[idx_spouse]
        cur_died = cur_cells[idx_died]

        # Continuation row: empty key columns but spouse text present.
        cur_born = cur_cells[idx_born] if idx_born is not None and idx_born < len(cur_cells) else ""
        cur_married = cur_cells[idx_married] if idx_married is not None and idx_married < len(cur_cells) else ""
        cur_boy = cur_cells[idx_boy] if idx_boy is not None and idx_boy < len(cur_cells) else ""
        cur_girl = cur_cells[idx_girl] if idx_girl is not None and idx_girl < len(cur_cells) else ""
        prev_boy = prev_cells[idx_boy] if idx_boy is not None and idx_boy < len(prev_cells) else ""
        prev_girl = prev_cells[idx_girl] if idx_girl is not None and idx_girl < len(prev_cells) else ""

        continuation = (
            not cur_name and not cur_born and not cur_married and cur_spouse
        )
        if not continuation:
            continue
        if cur_died:
            continue
        if not prev_died or not _is_date_like(prev_died):
            continue

        # Heuristic: if previous row has BOY/GIRL values and continuation row doesn't,
        # move DIED to the continuation row.
        if (prev_boy or prev_girl) and not (cur_boy or cur_girl):
            _set_cell_text(prev, idx_died, "")
            _set_cell_text(cur, idx_died, prev_died)
            fixes += 1

    return fixes


def main() -> None:
    parser = argparse.ArgumentParser(description="Fix continuation rows in HTML tables.")
    parser.add_argument("--pages", required=False, help="page_html_v1 JSONL path")
    parser.add_argument("--inputs", nargs="+", help="Alias for --pages (driver adapter input)")
    parser.add_argument("--out", required=True, help="Output JSONL path")
    parser.add_argument("--run-id", dest="run_id", default=None, help="Ignored (driver compatibility)")
    parser.add_argument("--state-file", dest="state_file", default=None, help="Ignored (driver compatibility)")
    parser.add_argument("--progress-file", dest="progress_file", default=None, help="Ignored (driver compatibility)")
    args = parser.parse_args()

    input_path = args.pages
    if not input_path and args.inputs:
        input_path = args.inputs[0]
    if not input_path:
        raise SystemExit("Missing --pages or --inputs")

    rows = list(read_jsonl(input_path))
    if not rows:
        raise SystemExit(f"Input is empty: {input_path}")

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    logger.log("adapter", "running", current=0, total=len(rows),
               message="Table continuation fix started", artifact=args.out,
               module_id="table_fix_continuations_v1", schema_version="page_html_v1")

    total_fixes = 0
    for idx, row in enumerate(rows, start=1):
        html = row.get("html") or row.get("raw_html") or ""
        if not html or "<table" not in html.lower():
            continue
        soup = BeautifulSoup(html, "html.parser")
        page_fixes = 0
        for table in soup.find_all("table"):
            page_fixes += _fix_table(table)
        if page_fixes:
            total_fixes += page_fixes
            row["html"] = str(soup)
        if idx % 20 == 0:
            logger.log("adapter", "running", current=idx, total=len(rows),
                       message=f"Processed {idx}/{len(rows)} pages (fixes={total_fixes})",
                       artifact=args.out, module_id="table_fix_continuations_v1",
                       schema_version="page_html_v1")

    save_jsonl(args.out, rows)
    logger.log("adapter", "done", current=len(rows), total=len(rows),
               message=f"Table continuation fix complete: fixes={total_fixes}",
               artifact=args.out, module_id="table_fix_continuations_v1",
               schema_version="page_html_v1",
               extra={"summary_metrics": {"continuation_fixes": total_fixes}})


if __name__ == "__main__":
    main()
