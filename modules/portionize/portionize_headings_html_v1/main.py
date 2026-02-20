#!/usr/bin/env python3
"""
Portionize chapters by detecting top-level HTML headings (e.g., <h1>) per page.
Uses printed page numbers for chapter boundaries; unnumbered pages fall back to
page-level outputs in build_chapter_html_v1.
"""
import argparse
import re
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

from modules.common.utils import read_jsonl, save_jsonl, ProgressLogger


def _normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _alpha_ratio(text: str) -> float:
    if not text:
        return 0.0
    letters = sum(1 for c in text if c.isalpha())
    return letters / max(1, len(text))


def _normalize_title(text: str) -> str:
    text = _normalize_ws(text).lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _slugify(text: str) -> str:
    text = _normalize_title(text)
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"_+", "_", text)
    return text or "chapter"


def _parse_heading_tags(raw: str) -> List[str]:
    if not raw:
        return ["h1"]
    tags = [t.strip().lower() for t in raw.split(",") if t.strip()]
    return tags or ["h1"]


def _extract_heading(html: str, heading_tags: List[str], min_len: int, max_len: int, min_alpha: float) -> Optional[str]:
    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(heading_tags):
        text = tag.get_text(" ", strip=True)
        text = _normalize_ws(text)
        if not text:
            continue
        if len(text) < min_len or len(text) > max_len:
            continue
        if _alpha_ratio(text) < min_alpha:
            continue
        return text
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Portionize chapters using HTML headings + printed page numbers.")
    parser.add_argument("--pages", required=True, help="page_html_v1 JSONL (with printed_page_number)")
    parser.add_argument("--out", required=True, help="Output portion_hyp_v1 JSONL")
    parser.add_argument("--heading-tags", default="h1", help="Comma-separated heading tags to scan (default: h1)")
    parser.add_argument("--min-printed-page", type=int, default=1, help="Minimum printed page number to start chapters")
    parser.add_argument("--allow-unnumbered", action="store_true",
                        help="Allow headings on pages without printed_page_number")
    parser.add_argument("--min-title-len", type=int, default=3, help="Minimum heading length")
    parser.add_argument("--max-title-len", type=int, default=140, help="Maximum heading length")
    parser.add_argument("--min-alpha", type=float, default=0.3, help="Minimum alpha ratio for heading text")
    parser.add_argument("--run-id", dest="run_id", default=None, help="Ignored (driver compatibility)")
    parser.add_argument("--state-file", dest="state_file", default=None, help="Ignored (driver compatibility)")
    parser.add_argument("--progress-file", dest="progress_file", default=None, help="Ignored (driver compatibility)")
    args = parser.parse_args()

    rows = list(read_jsonl(args.pages))
    if not rows:
        raise SystemExit(f"Input is empty: {args.pages}")

    heading_tags = _parse_heading_tags(args.heading_tags)
    max_printed = max((r.get("printed_page_number") for r in rows if isinstance(r.get("printed_page_number"), int)), default=None)

    # Preserve stable order by image/page sequence.
    rows_sorted = sorted(rows, key=lambda r: int(r.get("page_number") or r.get("page") or 0))

    boundaries: List[Dict[str, Any]] = []
    for row in rows_sorted:
        printed = row.get("printed_page_number")
        if not isinstance(printed, int) and not args.allow_unnumbered:
            continue
        if isinstance(printed, int) and printed < args.min_printed_page:
            continue
        html = row.get("html") or row.get("raw_html") or ""
        heading = _extract_heading(html, heading_tags, args.min_title_len, args.max_title_len, args.min_alpha)
        if not heading:
            continue
        heading_norm = _normalize_title(heading)
        boundaries.append({
            "title": heading,
            "title_norm": heading_norm,
            "printed_page_number": printed,
            "page_number": row.get("page_number") or row.get("page"),
        })

    if not boundaries:
        raise SystemExit("No headings found for chapter boundaries.")

    # Sort by printed page number (fallback to page_number for unnumbered).
    boundaries.sort(key=lambda b: (
        int(b["printed_page_number"]) if isinstance(b.get("printed_page_number"), int) else 10**9,
        int(b.get("page_number") or 0),
    ))

    portions: List[Dict[str, Any]] = []
    slug_counts: Dict[str, int] = {}
    current = None

    for boundary in boundaries:
        if current and boundary["title_norm"] == current["title_norm"]:
            # Same heading as current; ignore duplicate boundary.
            continue
        if current:
            portions.append(current)
        slug = _slugify(boundary["title"])
        slug_counts[slug] = slug_counts.get(slug, 0) + 1
        portion_id = slug if slug_counts[slug] == 1 else f"{slug}_{slug_counts[slug]}"
        current = {
            "schema_version": "portion_hyp_v1",
            "module_id": "portionize_headings_html_v1",
            "portion_id": portion_id,
            "page_start": boundary["printed_page_number"] if isinstance(boundary.get("printed_page_number"), int) else None,
            "page_end": None,
            "title": boundary["title"],
            "title_norm": boundary["title_norm"],
            "type": "chapter",
            "confidence": 0.6,
            "notes": "heading-derived",
        }

    if current:
        portions.append(current)

    # Fill page_end using next page_start; clamp to max_printed when available.
    for idx, portion in enumerate(portions):
        page_start = portion.get("page_start")
        if not isinstance(page_start, int):
            continue
        if idx + 1 < len(portions):
            next_start = portions[idx + 1].get("page_start")
            if isinstance(next_start, int) and next_start > page_start:
                portion["page_end"] = next_start - 1
        if portion.get("page_end") is None:
            if isinstance(max_printed, int) and max_printed >= page_start:
                portion["page_end"] = max_printed
            else:
                portion["page_end"] = page_start
        portion["source_pages"] = list(range(portion["page_start"], portion["page_end"] + 1))
        portion.pop("title_norm", None)

    save_jsonl(args.out, portions)
    logger = ProgressLogger("portionize_headings_html_v1")
    logger.log("portionize", "done", current=len(portions), total=len(portions),
               message=f"Wrote {len(portions)} portions to {args.out}")


if __name__ == "__main__":
    main()
