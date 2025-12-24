import argparse
import json
import os
from typing import Any, Dict, List
from modules.common.utils import read_jsonl, save_jsonl

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pages")
    parser.add_argument("--inputs", nargs="*")
    parser.add_argument("--out", required=True)
    parser.add_argument("--run-id")
    parser.add_argument("--state-file")
    parser.add_argument("--progress-file")
    args, unknown = parser.parse_known_args()

    pages_path = args.pages
    if not pages_path and args.inputs:
        pages_path = args.inputs[0]
    
    if not pages_path:
        parser.error("Missing --pages (or --inputs)")

    out_path = args.out
    # If the driver passed --outdir, make sure we use it if out is relative
    # Actually, driver usually passes absolute path in --out for adapter
    
    rows = []
    global_element_count = 1
    for row in read_jsonl(pages_path):
        text = row.get("clean_text") or row.get("raw_text") or ""
        # The stub pages might use 'page' instead of 'page_number'
        pn = row.get("page_number") or row.get("page")
        page_number = _coerce_int(pn)
        
        blocks = []
        paragraphs = text.split("\n")
        order = 1
        for p in paragraphs:
            p = p.strip()
            if not p:
                continue
            element_id = f"E{global_element_count}"
            blocks.append({
                "block_type": "p",
                "text": p,
                "order": order,
                "attrs": None,
                "element_id": element_id
            })
            global_element_count += 1
            order += 1
            
            blocks.append({
                "block_type": "/p",
                "text": "",
                "order": order,
                "attrs": None
            })
            order += 1

        out_row = {
            "schema_version": "page_html_blocks_v1",
            "page": row.get("page") or page_number,
            "page_number": page_number,
            "original_page_number": row.get("original_page_number") or page_number,
            "image": row.get("image"),
            "spread_side": row.get("spread_side"),
            "is_blank": not bool(blocks),
            "blocks": blocks
        }
        rows.append(out_row)
    
    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    save_jsonl(out_path, rows)
    print(f"Converted {len(rows)} pages to blocks -> {out_path}")

def _coerce_int(val: Any) -> int:
    if isinstance(val, int):
        return val
    try:
        return int(val)
    except:
        return 0

if __name__ == "__main__":
    main()
