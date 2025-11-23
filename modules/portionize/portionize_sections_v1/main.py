import argparse
import os
import sys
import re
from typing import List, Dict, Tuple

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
    # Some scans list multiple section numbers in the header line (e.g., "130 131-132");
    # capture those extras so we don't miss legitimate section ids that share the same body.
    header_line = (text or "").splitlines()[0] if text else ""
    header_nums = re.findall(r"\b(\d{1,4})\b", header_line)
    extra_header_ids = []
    if len(header_nums) > 1:
        seen_ids = {m.group(1) for m in matches}
        for num in header_nums:
            if num not in seen_ids:
                extra_header_ids.append(num)
    if extra_header_ids and matches:
        # prepend synthetic matches for the extra header ids sharing the first block
        first_start = matches[0].start()
        matches = [matches[0]] + matches[1:]
        # we will add extra ids after slicing body below
    if not matches and extra_header_ids:
        # No anchors found but header had numbers; treat whole page as one chunk shared across ids.
        body = (text or "")[:max_len]
        for sid in header_nums:
            sections.append({"id": sid, "text": body})
        return dedupe_sections(sections)
    if not matches:
        inline_ids = list({m.group(1) for m in INLINE_RE.finditer(text or "")})
        for sid in inline_ids:
            sections.append({"id": sid, "text": text[:max_len]})
        return dedupe_sections(sections)
    for idx, m in enumerate(matches):
        start = m.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        body = text[start:end]
        if len(body) > max_len:
            body = body[:max_len]
        sections.append({"id": m.group(1), "text": body})
        # If the header advertised extra ids, attach them to the first body chunk so they exist for mapping.
        if idx == 0 and extra_header_ids:
            for sid in extra_header_ids:
                sections.append({"id": sid, "text": body})
    # If inline references include ids we never anchored, add lightweight stubs from the page chunk.
    inline_ids = list({m.group(1) for m in INLINE_RE.finditer(text or "")})
    known_ids = {s["id"] for s in sections}
    for sid in inline_ids:
        if sid not in known_ids:
            stub_body = (text or "")[:max_len]
            sections.append({"id": sid, "text": stub_body})
    return dedupe_sections(sections)


def dedupe_sections(sections: List[Dict]) -> List[Dict]:
    """
    Drop duplicate ids per page, preferring the first occurrence (earliest anchor).
    This keeps ids unique while allowing header/inline fills to cover gaps.
    """
    seen = set()
    deduped: List[Dict] = []
    for sec in sections:
        sid = sec["id"]
        if sid in seen:
            continue
        seen.add(sid)
        deduped.append(sec)
    return deduped


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
