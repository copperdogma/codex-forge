import argparse
import json
import re
from pathlib import Path

from modules.common.utils import read_jsonl, save_jsonl, ensure_dir, save_json


def main():
    parser = argparse.ArgumentParser(description="Flag missing section IDs against an expected range; optionally emit presence/debug bundles.")
    parser.add_argument("--headers", required=True, help="portion_hyp jsonl (after resolver).")
    parser.add_argument("--expected-start", type=int, default=1)
    parser.add_argument("--expected-end", type=int, default=400)
    parser.add_argument("--out", required=True, help="JSONL of missing section ids (one per line).")
    parser.add_argument("--inputs", nargs="*", help="(ignored; driver compatibility)")
    parser.add_argument("--note", help="Optional note to attach to each missing entry (e.g., 'not detected after cleaning').")
    parser.add_argument("--pages-clean", help="Optional pages_clean.jsonl to trace presence in cleaned text.")
    parser.add_argument("--ocr-index", help="Optional pagelines_index.json to trace presence in raw OCR lines.")
    parser.add_argument("--bundle-dir", help="If set, write per-ID debug bundles (json) with presence flags.")
    args = parser.parse_args()

    num_re = re.compile(r"\b(\d{1,3})\b")

    present_headers = set()
    for h in read_jsonl(args.headers):
        try:
            sid = int(h.get("portion_id"))
        except Exception:
            continue
        present_headers.add(sid)

    present_clean = set()
    if args.pages_clean:
        for p in read_jsonl(args.pages_clean):
            text = (p.get("clean_text") or p.get("raw_text") or "")
            for m in num_re.finditer(text):
                try:
                    sid = int(m.group(1))
                except Exception:
                    continue
                if 1 <= sid <= 400:
                    present_clean.add(sid)

    present_ocr = set()
    if args.ocr_index:
        index = json.load(open(args.ocr_index, "r", encoding="utf-8"))
        for _, path in index.items():
            try:
                page = json.load(open(path, "r", encoding="utf-8"))
            except Exception:
                continue
            text = "\n".join([l.get("text", "") for l in page.get("lines", [])])
            for m in num_re.finditer(text):
                try:
                    sid = int(m.group(1))
                except Exception:
                    continue
                if 1 <= sid <= 400:
                    present_ocr.add(sid)

    expected = set(range(args.expected_start, args.expected_end + 1))
    missing = sorted(list(expected - present_headers))
    ensure_dir(Path(args.out).parent)
    payload = []
    bundles = {}
    for sid in missing:
        row = {"section_id": sid}
        if args.note:
            row["note"] = args.note
        row["seen_in_ocr"] = sid in present_ocr
        row["seen_in_clean"] = sid in present_clean
        row["seen_in_headers"] = False
        payload.append(row)
        if args.bundle_dir:
            bundles[sid] = {
                "section_id": sid,
                "seen": {
                    "ocr": row["seen_in_ocr"],
                    "clean": row["seen_in_clean"],
                    "headers": False,
                },
                "note": args.note,
            }
    save_jsonl(args.out, payload)
    if args.bundle_dir and bundles:
        ensure_dir(args.bundle_dir)
        for sid, bundle in bundles.items():
            save_json(Path(args.bundle_dir) / f"missing_{sid}.json", bundle)
    print(f"Missing {len(missing)} sections → {args.out}")


if __name__ == "__main__":
    main()
