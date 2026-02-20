#!/usr/bin/env python3
"""
Portionize chapters from HTML by parsing TOC entries.
Uses printed page numbers (from extract_page_numbers_html_v1) to set page ranges.
"""
import argparse
import re
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

from modules.common.utils import read_jsonl, save_jsonl, ProgressLogger


TOC_TITLE_PATTERNS = {"index", "table of contents", "contents"}


def _normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _looks_like_toc_entry(text: str) -> bool:
    t = _normalize_ws(text)
    if not t or len(t) > 160:
        return False
    if re.search(r"\.{3,}\s*\d+\s*$", t):
        return True
    if re.search(r"\s{2,}\d+\s*$", text) and re.search(r"[A-Za-z]", text):
        return True
    return False


def _extract_entry_from_line(text: str) -> Optional[Dict[str, Any]]:
    raw = text or ""
    if not raw.strip():
        return None
    m = re.match(r"^(.*?)\.{3,}\s*(\d{1,4})\s*$", raw)
    if not m:
        m = re.match(r"^(.*?\S)\s{2,}(\d{1,4})\s*$", raw)
    if not m:
        return None
    title = _normalize_ws(m.group(1))
    title = re.sub(r"\.{2,}", "", title).strip()
    if not title:
        return None
    page_num = int(m.group(2))
    return {"title": title, "page_start": page_num}


def _is_toc_page(lines: List[str], min_entries: int) -> bool:
    if not lines:
        return False
    for line in lines[:5]:
        if _normalize_ws(line).lower() in TOC_TITLE_PATTERNS:
            return True
    entry_count = sum(1 for line in lines if _looks_like_toc_entry(line))
    return entry_count >= max(1, min_entries)


def _extract_table_entries(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    entries = []
    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])]
            if len(cells) < 2:
                continue
            title = _normalize_ws(cells[0])
            title = re.sub(r"\.{2,}", "", title).strip()
            if not title or title.lower() in {"children", "total"}:
                continue
            last = _normalize_ws(cells[-1])
            digits = re.findall(r"\d{1,4}", last)
            if not digits:
                continue
            page_num = int(digits[-1])
            entries.append({"title": title, "page_start": page_num})
    return entries


def _dedupe_entries(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = {}
    for ent in entries:
        key = ent["title"].lower()
        if key not in seen or ent["page_start"] < seen[key]["page_start"]:
            seen[key] = ent
    return list(seen.values())


def _slugify(text: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"_+", "_", text)
    return text or "chapter"


def main() -> None:
    parser = argparse.ArgumentParser(description="Portionize chapters using TOC entries from HTML pages.")
    parser.add_argument("--pages", required=True, help="page_html_v1 JSONL (with printed_page_number)")
    parser.add_argument("--out", required=True, help="Output portion_hyp_v1 JSONL")
    parser.add_argument("--min-entries", type=int, default=3, help="Minimum TOC-like lines to treat a page as TOC")
    parser.add_argument("--run-id", dest="run_id", default=None, help="Ignored (driver compatibility)")
    parser.add_argument("--state-file", dest="state_file", default=None, help="Ignored (driver compatibility)")
    parser.add_argument("--progress-file", dest="progress_file", default=None, help="Ignored (driver compatibility)")
    args = parser.parse_args()

    rows = list(read_jsonl(args.pages))
    if not rows:
        raise SystemExit(f"Input is empty: {args.pages}")

    max_printed = max((r.get("printed_page_number") for r in rows if isinstance(r.get("printed_page_number"), int)), default=None)
    entries: List[Dict[str, Any]] = []

    for row in rows:
        html = row.get("html") or row.get("raw_html") or ""
        soup = BeautifulSoup(html, "html.parser")
        lines = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
        if not _is_toc_page(lines, args.min_entries):
            continue
        for line in lines:
            ent = _extract_entry_from_line(line)
            if ent:
                entries.append(ent)
        entries.extend(_extract_table_entries(soup))

    entries = _dedupe_entries(entries)
    entries = [e for e in entries if isinstance(e.get("page_start"), int)]
    entries.sort(key=lambda e: e["page_start"])

    if not entries:
        raise SystemExit("No TOC entries found; cannot build chapters.")

    portions = []
    for idx, ent in enumerate(entries):
        page_start = ent["page_start"]
        page_end = None
        if idx + 1 < len(entries):
            next_start = entries[idx + 1]["page_start"]
            if next_start > page_start:
                page_end = next_start - 1
        elif isinstance(max_printed, int) and max_printed >= page_start:
            page_end = max_printed
        if page_end is None:
            page_end = page_start
        title = ent.get("title")
        portion_id = _slugify(title)
        portions.append({
            "schema_version": "portion_hyp_v1",
            "module_id": "portionize_toc_html_v1",
            "portion_id": portion_id,
            "page_start": page_start,
            "page_end": page_end,
            "title": title,
            "type": "chapter",
            "confidence": 0.7,
            "notes": "toc-derived",
            "source_pages": list(range(page_start, page_end + 1)),
        })

    save_jsonl(args.out, portions)
    logger = ProgressLogger("portionize_toc_html_v1")
    logger.log("portionize", "done", current=len(portions), total=len(portions),
               message=f"Wrote {len(portions)} portions to {args.out}")


if __name__ == "__main__":
    main()
