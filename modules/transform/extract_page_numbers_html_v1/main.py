#!/usr/bin/env python3
"""
Extract printed page numbers from OCR HTML and store them in JSON fields.
Leaves HTML unchanged (page-number tags can be stripped later).
"""
import argparse
import re
from typing import Any, Dict, Optional, List

from bs4 import BeautifulSoup

from modules.common.utils import read_jsonl, save_jsonl, ProgressLogger


PAGE_NUMBER_CLASS = "page-number"


def _strip_tags(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _extract_printed_page_number(html: str) -> Dict[str, Optional[Any]]:
    if not html:
        return {"printed_page_number": None, "printed_page_number_text": None}
    matches = re.findall(
        r'<p[^>]*class=["\']%s["\'][^>]*>(.*?)</p>' % PAGE_NUMBER_CLASS,
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not matches:
        # Fallback: find trailing standalone numeric or roman numeral lines outside tables.
        soup = BeautifulSoup(html, "html.parser")
        candidates: List[str] = []
        for p in soup.find_all("p"):
            if p.find_parent("table") is not None:
                continue
            text = _strip_tags(str(p))
            if not text:
                continue
            text = text.strip()
            if re.fullmatch(r"\d{1,4}", text) or re.fullmatch(r"[ivxlcdm]+", text.lower()):
                candidates.append(text)
        if not candidates:
            return {"printed_page_number": None, "printed_page_number_text": None}
        cleaned = candidates[-1]
        digits = re.findall(r"\d+", cleaned)
        if not digits:
            return {"printed_page_number": None, "printed_page_number_text": cleaned or None}
        return {"printed_page_number": int(digits[-1]), "printed_page_number_text": cleaned or None}
    # Prefer the last occurrence (footers are typically last).
    raw = matches[-1]
    cleaned = _strip_tags(raw)
    digits = re.findall(r"\d+", cleaned)
    if not digits:
        return {"printed_page_number": None, "printed_page_number_text": cleaned or None}
    return {"printed_page_number": int(digits[-1]), "printed_page_number_text": cleaned or None}


def _infer_missing_page_numbers(rows: List[Dict[str, Any]]) -> None:
    def page_key(row: Dict[str, Any]) -> int:
        return int(row.get("page_number") or row.get("page") or 0)

    ordered = sorted(enumerate(rows), key=lambda ir: page_key(ir[1]))
    idxs = [i for i, (_, r) in enumerate(ordered) if isinstance(r.get("printed_page_number"), int)]
    if not idxs:
        return

    # Fill gaps between known numeric page numbers when perfectly sequential.
    for a, b in zip(idxs, idxs[1:]):
        _, ra = ordered[a]
        _, rb = ordered[b]
        pa = ra.get("printed_page_number")
        pb = rb.get("printed_page_number")
        if not isinstance(pa, int) or not isinstance(pb, int):
            continue
        if pb > pa and (pb - pa) == (b - a):
            for k in range(a + 1, b):
                _, rk = ordered[k]
                if rk.get("printed_page_number") is None:
                    rk["printed_page_number"] = pa + (k - a)
                    rk["printed_page_number_inferred"] = True

    # Backfill before first known numeric (only if >= 1).
    first = idxs[0]
    _, r_first = ordered[first]
    p_first = r_first.get("printed_page_number")
    if isinstance(p_first, int):
        for k in range(first - 1, -1, -1):
            inferred = p_first - (first - k)
            if inferred < 1:
                break
            _, rk = ordered[k]
            if rk.get("printed_page_number") is None:
                rk["printed_page_number"] = inferred
                rk["printed_page_number_inferred"] = True

    # Forward fill after last known numeric.
    last = idxs[-1]
    _, r_last = ordered[last]
    p_last = r_last.get("printed_page_number")
    if isinstance(p_last, int):
        for k in range(last + 1, len(ordered)):
            inferred = p_last + (k - last)
            _, rk = ordered[k]
            if rk.get("printed_page_number") is None:
                rk["printed_page_number"] = inferred
                rk["printed_page_number_inferred"] = True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract printed page numbers from OCR HTML into JSON fields."
    )
    parser.add_argument("--pages", required=True, help="page_html_v1 JSONL path")
    parser.add_argument("--out", required=True, help="Output JSONL path")
    parser.add_argument("--infer-missing", dest="infer_missing", action="store_true", default=True,
                        help="Infer missing numeric page numbers from sequential order")
    parser.add_argument("--no-infer-missing", dest="infer_missing", action="store_false")
    parser.add_argument("--run-id", dest="run_id", default=None, help="Ignored (driver compatibility)")
    parser.add_argument("--state-file", dest="state_file", default=None, help="Ignored (driver compatibility)")
    parser.add_argument("--progress-file", dest="progress_file", default=None, help="Ignored (driver compatibility)")
    args = parser.parse_args()

    logger = ProgressLogger("extract_page_numbers_html_v1")
    logger.log("extract_page_numbers", "running", message=f"Loading {args.pages}")

    rows = []
    for row in read_jsonl(args.pages):
        html = row.get("html") or row.get("raw_html") or ""
        extracted = _extract_printed_page_number(html)
        row["printed_page_number"] = extracted["printed_page_number"]
        row["printed_page_number_text"] = extracted["printed_page_number_text"]
        row["printed_page_number_inferred"] = False
        rows.append(row)

    if args.infer_missing:
        _infer_missing_page_numbers(rows)

    save_jsonl(args.out, rows)
    logger.log(
        "extract_page_numbers",
        "done",
        current=len(rows),
        total=len(rows),
        message=f"Wrote {len(rows)} rows to {args.out}",
    )


if __name__ == "__main__":
    main()
