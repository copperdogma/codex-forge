import argparse
import re
from typing import List, Dict

from modules.common.utils import read_jsonl, save_jsonl

HEADING_RE = re.compile(r"(?m)^(?P<num>\d{1,4})\b[ \t\.:)]")
INLINE_RE = re.compile(r"\n(?P<num>\d{1,4})\b[ \t\.:)]")


def split_portions(text: str) -> List[Dict]:
    portions: List[Dict] = []
    matches = list(HEADING_RE.finditer(text or ""))
    if not matches:
        # fall back to inline anchors
        matches = list(INLINE_RE.finditer("\n" + (text or "")))
        if not matches:
            return []
    for idx, m in enumerate(matches):
        start = m.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        heading_num = m.group("num")
        portions.append({"id": heading_num, "text": body})
    return portions


def main():
    parser = argparse.ArgumentParser(description="Portionize clean pages into numbered sections.")
    parser.add_argument("--pages", required=True, help="clean_pages JSONL")
    parser.add_argument("--out", required=True, help="portion hypotheses JSONL")
    parser.add_argument("--confidence", type=float, default=0.6)
    parser.add_argument("--state-file", help="ignored")
    parser.add_argument("--progress-file", help="ignored")
    parser.add_argument("--run-id", help="ignored")
    args = parser.parse_args()

    rows_out = []
    for page in read_jsonl(args.pages):
        text = page.get("clean_text") or page.get("raw_text") or ""
        parts = split_portions(text)
        for part in parts:
            rows_out.append({
                "schema_version": "portion_hyp_v1",
                "portion_id": part["id"],
                "page_start": page["page"],
                "page_end": page["page"],
                "title": None,
                "type": "section",
                "confidence": args.confidence,
                "notes": "numbered heading",
                "source_window": [page["page"]],
                "source_pages": [page["page"]],
                "continuation_of": None,
                "continuation_confidence": None,
            })

    save_jsonl(args.out, rows_out)
    print(f"Wrote {len(rows_out)} portions → {args.out}")


if __name__ == "__main__":
    main()
