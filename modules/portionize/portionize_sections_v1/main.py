import argparse
import os
import sys
import re
from typing import List, Dict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if os.getcwd() not in sys.path:
    sys.path.insert(0, os.getcwd())

from modules.common.utils import read_jsonl, save_jsonl  # noqa: E402

ANCHOR_RE = re.compile(r"(?m)^\s*(\d{1,4})\b")
INLINE_RE = re.compile(r"\b(?:Section|Paragraph|Turn to|Go to)\s+(\d{1,4})\b", re.IGNORECASE)


def find_sections(text: str, max_len: int) -> List[Dict]:
    sections: List[Dict] = []
    matches = list(ANCHOR_RE.finditer(text or ""))
    if not matches:
        inline_ids = list({m.group(1) for m in INLINE_RE.finditer(text or "")})
        for sid in inline_ids:
            sections.append({"id": sid, "text": text[:max_len]})
        return sections
    for idx, m in enumerate(matches):
        start = m.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        body = text[start:end]
        if len(body) > max_len:
            body = body[:max_len]
        sections.append({"id": m.group(1), "text": body})
    return sections


def main():
    parser = argparse.ArgumentParser(description="Portionize by inline numeric anchors (section numbers).")
    parser.add_argument("--pages", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--confidence", type=float, default=0.7)
    parser.add_argument("--max_section_len", type=int, default=3000)
    parser.add_argument("--state-file", help="ignored")
    parser.add_argument("--progress-file", help="ignored")
    parser.add_argument("--run-id", help="ignored")
    args = parser.parse_args()

    rows_out = []
    for page in read_jsonl(args.pages):
        text = page.get("clean_text") or page.get("raw_text") or ""
        sections = find_sections(text, args.max_section_len)
        for sec in sections:
            rows_out.append({
                "schema_version": "portion_hyp_v1",
                "portion_id": sec["id"],
                "page_start": page["page"],
                "page_end": page["page"],
                "title": None,
                "type": "section",
                "confidence": args.confidence,
                "notes": "inline section anchor",
                "source_window": [page["page"]],
                "source_pages": [page["page"]],
                "continuation_of": None,
                "continuation_confidence": None,
            })
    save_jsonl(args.out, rows_out)
    print(f"Wrote {len(rows_out)} sections → {args.out}")


if __name__ == "__main__":
    main()
