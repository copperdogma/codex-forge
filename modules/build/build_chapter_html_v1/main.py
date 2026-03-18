#!/usr/bin/env python3
"""
Build chapter HTML files from pages and TOC-derived portions.

Produces proper HTML5 documents with embedded CSS, semantic structure
(<figure>/<figcaption>), chapter navigation, and responsive styling.
"""
import argparse
import re
import sys
from copy import deepcopy
from datetime import datetime
from difflib import SequenceMatcher
from functools import lru_cache
from html import escape as html_escape
from pathlib import Path
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

from modules.common.onward_genealogy_html import (
    merge_contiguous_genealogy_tables as _merge_contiguous_genealogy_tables,
)
from modules.common.utils import read_jsonl, save_jsonl, ensure_dir, ProgressLogger


def _utc() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _resolve_run_dir(out_path: Path) -> Path:
    cur = out_path.parent
    for parent in [cur] + list(cur.parents):
        if (parent / "pipeline_state.json").exists():
            return parent
    return cur


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

_CSS = """
/* Reset */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

/* Typography */
:root {
  --font-body: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  --font-serif: Georgia, "Times New Roman", serif;
  --max-width: 52rem;
  --color-bg: #fff;
  --color-text: #222;
  --color-muted: #666;
  --color-border: #ddd;
  --color-link: #1a5276;
  --color-nav-bg: #f8f8f8;
}

html { font-size: 100%; }
body {
  font-family: var(--font-serif);
  color: var(--color-text);
  background: var(--color-bg);
  line-height: 1.7;
  max-width: var(--max-width);
  margin: 0 auto;
  padding: 1.5rem 1rem;
}

h1, h2, h3, h4, h5, h6 {
  font-family: var(--font-body);
  line-height: 1.3;
  margin-top: 1.5em;
  margin-bottom: 0.5em;
}
h1 { font-size: 1.8rem; }
h2 { font-size: 1.4rem; }
h3 { font-size: 1.2rem; }

p { margin-bottom: 0.8em; }
a { color: var(--color-link); }

/* Navigation */
nav.chapter-nav {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.6rem 0;
  border-bottom: 1px solid var(--color-border);
  margin-bottom: 1.5rem;
  font-family: var(--font-body);
  font-size: 0.9rem;
}
nav.chapter-nav.bottom {
  border-bottom: none;
  border-top: 1px solid var(--color-border);
  margin-top: 2rem;
  margin-bottom: 0;
}
nav.chapter-nav a { text-decoration: none; }
nav.chapter-nav .nav-placeholder { min-width: 4rem; }

/* Tables */
table {
  border-collapse: collapse;
  width: 100%;
  margin: 1em 0;
  font-size: 0.95rem;
  overflow-x: auto;
  display: block;
}
th, td {
  border: 1px solid var(--color-border);
  padding: 0.4rem 0.6rem;
  text-align: left;
  vertical-align: top;
}
th {
  background: var(--color-nav-bg);
  font-weight: 600;
  font-family: var(--font-body);
}
tr:nth-child(even) td { background: #fafafa; }

/* Images / Figures */
figure {
  margin: 1.5em 0;
  text-align: center;
}
figure img {
  max-width: 100%;
  height: auto;
  display: inline-block;
}
figcaption {
  font-family: var(--font-body);
  font-size: 0.85rem;
  color: var(--color-muted);
  margin-top: 0.4em;
  font-style: italic;
}
img {
  max-width: 100%;
  height: auto;
}

/* Index page */
.book-header { margin-bottom: 2rem; }
.book-header h1 { margin-top: 0; }
.book-header .author { color: var(--color-muted); font-size: 1.1rem; }
.toc-list { list-style: none; padding: 0; }
.toc-list li {
  padding: 0.4rem 0;
  border-bottom: 1px solid var(--color-border);
}
.toc-list li:last-child { border-bottom: none; }
.toc-list a { text-decoration: none; font-family: var(--font-body); }
.toc-list .page-range {
  color: var(--color-muted);
  font-size: 0.85rem;
  margin-left: 0.5em;
}

/* Article */
article { margin-bottom: 2rem; }

/* Print */
@media print {
  body { max-width: none; padding: 0; }
  nav.chapter-nav { display: none; }
  table { display: table; }
  figure { break-inside: avoid; }
}
""".strip()


# ---------------------------------------------------------------------------
# HTML5 document wrapper
# ---------------------------------------------------------------------------

def _html5_wrap(body_html: str, title: str, nav_html_top: str = "",
                nav_html_bottom: str = "") -> str:
    """Wrap body content in a proper HTML5 document."""
    title_esc = html_escape(title)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title_esc}</title>
<style>
{_CSS}
</style>
</head>
<body>
{nav_html_top}
<article>
{body_html}
</article>
{nav_html_bottom}
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------

def _build_nav(prev_file: Optional[str], prev_title: Optional[str],
               next_file: Optional[str], next_title: Optional[str],
               is_bottom: bool = False) -> str:
    cls = 'chapter-nav bottom' if is_bottom else 'chapter-nav'
    prev_link = f'<a href="{prev_file}">&larr; {html_escape(prev_title or "Prev")}</a>' if prev_file else '<span class="nav-placeholder"></span>'
    next_link = f'<a href="{next_file}">{html_escape(next_title or "Next")} &rarr;</a>' if next_file else '<span class="nav-placeholder"></span>'
    return f'<nav class="{cls}">{prev_link}<a href="index.html">Index</a>{next_link}</nav>'


# ---------------------------------------------------------------------------
# Post-processing helpers
# ---------------------------------------------------------------------------

def _strip_headers_and_numbers(html: str) -> str:
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(class_="page-number"):
        tag.decompose()
    for tag in soup.find_all(class_="running-head"):
        tag.decompose()
    return soup.decode_contents()


def _add_table_scope(html: str) -> str:
    """Add scope attributes to <th> elements for accessibility."""
    if "<th" not in html:
        return html
    soup = BeautifulSoup(html, "html.parser")
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not rows:
            continue
        # First row with <th> gets scope="col"
        first_row = rows[0]
        for th in first_row.find_all("th"):
            if not th.get("scope"):
                th["scope"] = "col"
        # Remaining rows: first <th> in each row gets scope="row"
        for row in rows[1:]:
            ths = row.find_all("th")
            if ths and not ths[0].get("scope"):
                ths[0]["scope"] = "row"
    return soup.decode_contents()


# ---------------------------------------------------------------------------
# Image attachment (T3, T4, T5)
# ---------------------------------------------------------------------------

def _page_sort_key(row: Dict[str, Any]) -> tuple:
    pn = row.get("printed_page_number")
    if pn is None:
        pn = row.get("page_number") or row.get("page") or 0
    return (int(pn), int(row.get("page_number") or row.get("page") or 0))


def _normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _title_tokens(text: str) -> List[str]:
    normalized = _normalize_ws(text).casefold()
    normalized = normalized.replace("’", "'").replace("`", "'")
    normalized = re.sub(r"[^\w\s]", " ", normalized)
    return [tok for tok in normalized.split() if tok]


def _titles_related(a: Optional[str], b: Optional[str]) -> bool:
    tokens_a = _title_tokens(a or "")
    tokens_b = _title_tokens(b or "")
    if not tokens_a or not tokens_b:
        return False

    def _tokens_match(left: str, right: str) -> bool:
        if left == right:
            return True
        if min(len(left), len(right)) <= 1:
            return False
        if left.startswith(right) or right.startswith(left):
            return True
        return SequenceMatcher(a=left, b=right).ratio() >= 0.83

    def _all_tokens_match(shorter: List[str], longer: List[str]) -> bool:
        return all(any(_tokens_match(token, candidate) for candidate in longer) for token in shorter)

    if len(tokens_a) <= len(tokens_b):
        return _all_tokens_match(tokens_a, tokens_b)
    return _all_tokens_match(tokens_b, tokens_a)


_NON_OWNER_HEADING_MARKERS = (
    "family",
    "grandchildren",
    "great grandchildren",
    "great great grandchildren",
    "descendants",
)


def _is_strong_owner_heading(text: str) -> bool:
    normalized = _normalize_ws(text)
    if not normalized or len(normalized) < 3 or len(normalized) > 160:
        return False
    lowered = normalized.casefold()
    if any(marker in lowered for marker in _NON_OWNER_HEADING_MARKERS):
        return False
    letters = sum(1 for ch in normalized if ch.isalpha())
    if letters / max(1, len(normalized)) < 0.3:
        return False
    return True


def _normalize_heading_breaks(html: str) -> str:
    if "<br" not in html:
        return html
    soup = BeautifulSoup(html, "html.parser")
    for heading in soup.find_all(re.compile(r"^h[1-6]$")):
        if not heading.find("br"):
            continue
        text = _normalize_ws(heading.get_text(" ", strip=True))
        heading.clear()
        heading.append(text)
    return soup.decode_contents()


def _first_strong_owner_heading(html: str) -> Optional[str]:
    soup = BeautifulSoup(html or "", "html.parser")
    for heading in soup.find_all("h1"):
        text = _normalize_ws(heading.get_text(" ", strip=True))
        if _is_strong_owner_heading(text):
            return text
    return None


def _starts_with_strong_h1(html: str, heading: Optional[str]) -> bool:
    if not heading:
        return False
    soup = BeautifulSoup(html or "", "html.parser")
    first = _first_significant_tag(soup)
    if not first or first.name != "h1":
        return False
    text = _normalize_ws(first.get_text(" ", strip=True))
    return text == heading


def _first_significant_tag(soup: BeautifulSoup):
    for child in soup.contents:
        name = getattr(child, "name", None)
        if name:
            return child
    return None


def _last_significant_tag(soup: BeautifulSoup):
    for child in reversed(soup.contents):
        name = getattr(child, "name", None)
        if name:
            return child
    return None


_DANGLING_END_WORDS = {
    "a", "after", "and", "as", "at", "be", "because", "before", "for", "from",
    "if", "in", "into", "near", "of", "on", "or", "our", "the", "their", "to",
    "was", "with",
}
_SENTENCE_END_RE = re.compile(r"[.!?\"')\]]$")


def _should_stitch_page_break(prev_text: str, next_text: str) -> bool:
    prev_norm = _normalize_ws(prev_text)
    next_norm = _normalize_ws(next_text)
    if not prev_norm or not next_norm:
        return False
    if _SENTENCE_END_RE.search(prev_norm):
        return False
    if next_norm[:1].islower():
        return True
    prev_tokens = _title_tokens(prev_norm)
    if prev_tokens and prev_tokens[-1] in _DANGLING_END_WORDS:
        return True
    return False


def _append_paragraph_children(dst, src) -> None:
    dst.append(" ")
    while src.contents:
        dst.append(src.contents[0].extract())


def _trailing_paragraph_before_figures(soup) -> Optional[Any]:
    last = _last_significant_tag(soup)
    if not last or last.name != "figure":
        return None
    first = last
    prev = _previous_significant_tag(first)
    while getattr(prev, "name", None) == "figure":
        first = prev
        prev = _previous_significant_tag(first)
    if getattr(prev, "name", None) == "p":
        return prev
    return None


def _stitch_page_breaks(page_htmls: List[str]) -> str:
    soups = [BeautifulSoup(html or "", "html.parser") for html in page_htmls if html]
    if not soups:
        return ""
    for idx in range(1, len(soups)):
        prev = soups[idx - 1]
        current = soups[idx]
        prev_last = _last_significant_tag(prev)
        current_first = _first_significant_tag(current)
        if not current_first or current_first.name != "p":
            continue
        prev_anchor = None
        if prev_last and prev_last.name == "p":
            prev_anchor = prev_last
        elif prev_last and prev_last.name == "figure":
            prev_anchor = _trailing_paragraph_before_figures(prev)
        if not prev_anchor:
            continue
        prev_text = prev_anchor.get_text(" ", strip=True)
        current_text = current_first.get_text(" ", strip=True)
        if _should_stitch_page_break(prev_text, current_text):
            _append_paragraph_children(prev_anchor, current_first)
            current_first.decompose()
    return "\n".join(soup.decode_contents() for soup in soups if soup.decode_contents().strip())


def _related_title_index(heading: Optional[str], titles: List[str]) -> Optional[int]:
    if not heading:
        return None
    for idx, title in enumerate(titles):
        if _titles_related(heading, title):
            return idx
    return None


def _build_segment(
    title: str,
    portion_title: str,
    portion_page_start: int,
    pages: List[Dict[str, Any]],
    *,
    carry_back: bool = False,
) -> Dict[str, Any]:
    return {
        "title": title,
        "page_start": pages[0]["printed_page_number"],
        "page_end": pages[-1]["printed_page_number"],
        "source_pages": [p["page_number"] for p in pages if isinstance(p.get("page_number"), int)],
        "source_printed_pages": [
            p["printed_page_number"]
            for p in pages
            if isinstance(p.get("printed_page_number"), int)
        ],
        "body_html": _stitch_page_breaks([p["html"] for p in pages]),
        "source_portion_title": portion_title,
        "source_portion_page_start": portion_page_start,
        "source_portion_titles": [portion_title],
        "source_portion_page_starts": [portion_page_start],
        "carry_back": carry_back,
    }


def _refine_chapter_segments(
    portion_title: str,
    portion_page_start: int,
    prepared_pages: List[Dict[str, Any]],
    candidate_titles: List[str],
    *,
    previous_title: Optional[str] = None,
    stale_portion: bool = False,
) -> List[Dict[str, Any]]:
    if not prepared_pages:
        return []

    segments: List[Dict[str, Any]] = []
    remaining_pages = list(prepared_pages)
    current_title = portion_title
    current_heading = None

    if previous_title:
        first_prev_heading_idx = None
        next_owner_idx = None

        for idx, page in enumerate(remaining_pages):
            heading = page.get("owner_heading")
            if not heading:
                continue

            heading_matches_prev = _titles_related(heading, previous_title)
            heading_matches_known_title = _related_title_index(heading, candidate_titles) is not None
            heading_starts_page = _starts_with_strong_h1(page.get("html") or "", heading)

            if first_prev_heading_idx is None:
                if heading_matches_prev:
                    first_prev_heading_idx = idx
                    continue
                break

            if not heading_matches_prev and (heading_matches_known_title or heading_starts_page):
                next_owner_idx = idx
                break

        if first_prev_heading_idx is not None:
            if next_owner_idx is None:
                return [
                    _build_segment(
                        previous_title,
                        portion_title,
                        portion_page_start,
                        remaining_pages,
                        carry_back=True,
                    )
                ]

            carry_back_pages = remaining_pages[:next_owner_idx]
            segments.append(
                _build_segment(
                    previous_title,
                    portion_title,
                    portion_page_start,
                    carry_back_pages,
                    carry_back=True,
                )
            )
            remaining_pages = remaining_pages[next_owner_idx:]
            next_heading = remaining_pages[0].get("owner_heading")
            current_title = next_heading or portion_title
            current_heading = next_heading

    if stale_portion:
        same_title_idx = None
        first_new_heading_idx = None
        first_new_heading = None

        for idx, page in enumerate(remaining_pages):
            heading = page.get("owner_heading")
            if not heading:
                continue

            if same_title_idx is None and _titles_related(heading, portion_title):
                same_title_idx = idx

            if first_new_heading_idx is not None:
                continue

            heading_matches_known_title = _related_title_index(heading, candidate_titles) is not None
            heading_starts_page = _starts_with_strong_h1(page.get("html") or "", heading)
            if not _titles_related(heading, portion_title) and (heading_matches_known_title or heading_starts_page):
                first_new_heading_idx = idx
                first_new_heading = heading

        if first_new_heading_idx is not None and (
            same_title_idx is None or first_new_heading_idx < same_title_idx
        ):
            carry_back_pages = remaining_pages[:first_new_heading_idx]
            if carry_back_pages:
                segments.append(
                    _build_segment(
                        portion_title,
                        portion_title,
                        portion_page_start,
                        carry_back_pages,
                        carry_back=True,
                    )
                )
            remaining_pages = remaining_pages[first_new_heading_idx:]
            current_title = first_new_heading or portion_title
            current_heading = first_new_heading
        elif same_title_idx is None:
            return [
                _build_segment(
                    portion_title,
                    portion_title,
                    portion_page_start,
                    remaining_pages,
                    carry_back=True,
                )
            ]

    if not remaining_pages:
        return segments

    current_pages: List[Dict[str, Any]] = []

    for page in remaining_pages:
        heading = page.get("owner_heading")
        heading_matches_known_title = bool(
            heading and any(_titles_related(heading, title) for title in candidate_titles)
        )
        heading_starts_page = _starts_with_strong_h1(page.get("html") or "", heading)
        if (
            heading
            and heading_matches_known_title
            and current_pages
            and current_heading
            and not _titles_related(heading, current_heading)
        ):
            segments.append(_build_segment(current_title, portion_title, portion_page_start, current_pages))
            current_pages = []
            current_title = heading
            current_heading = heading

        if heading and current_heading is None and (heading_matches_known_title or (not current_pages and heading_starts_page)):
            current_title = heading
            current_heading = heading

        current_pages.append(page)

    if current_pages:
        segments.append(_build_segment(current_title, portion_title, portion_page_start, current_pages))

    return segments


def _extend_unique(existing: Optional[List[Any]], new_values: Optional[List[Any]]) -> List[Any]:
    merged = list(existing or [])
    for value in new_values or []:
        if value not in merged:
            merged.append(value)
    return merged


def _merge_carry_back_segment(entry: Dict[str, Any], segment: Dict[str, Any]) -> None:
    entry["body_html"] = _stitch_page_breaks([entry.get("body_html") or "", segment.get("body_html") or ""])
    if segment.get("page_end") is not None:
        entry["page_end"] = segment["page_end"]
    entry["source_pages"] = _extend_unique(entry.get("source_pages"), segment.get("source_pages"))
    entry["source_printed_pages"] = _extend_unique(
        entry.get("source_printed_pages"),
        segment.get("source_printed_pages"),
    )
    entry["source_portion_titles"] = _extend_unique(
        entry.get("source_portion_titles") or [entry.get("source_portion_title")],
        segment.get("source_portion_titles") or [segment.get("source_portion_title")],
    )
    entry["source_portion_page_starts"] = _extend_unique(
        entry.get("source_portion_page_starts") or [entry.get("source_portion_page_start")],
        segment.get("source_portion_page_starts") or [segment.get("source_portion_page_start")],
    )


def _group_manifest_by_page(manifest_path: str) -> Dict[int, List[Dict[str, Any]]]:
    grouped: Dict[int, List[Dict[str, Any]]] = {}
    for row in read_jsonl(manifest_path):
        page = row.get("source_page")
        if not isinstance(page, int):
            continue
        bbox = row.get("bbox") or {}
        row["_sort_key"] = (
            int(bbox.get("y0") or 0),
            int(bbox.get("x0") or 0),
            row.get("filename") or "",
        )
        grouped.setdefault(page, []).append(row)
    for rows in grouped.values():
        rows.sort(key=lambda r: r.get("_sort_key"))
        for r in rows:
            r.pop("_sort_key", None)
    return grouped


_MAX_CAPTION_WORDS = 30

# Patterns that strongly suggest a caption (names, dates, descriptive labels)
_CAPTION_PATTERNS = re.compile(
    r"""
    \b\d{4}\b                              # year (1920, 2024)
    | \b[Cc]irca\b                         # "circa 1920"
    | \b[Aa]bout\s+\d{4}\b                # "about 1910"
    | \b(?:[Bb]ack|[Ff]ront|[Ll]eft|[Rr]ight)\s+[Rr]ow\b  # "Back Row:"
    | \b[Ll]eft\s+to\s+[Rr]ight\b         # "Left to right:"
    """,
    re.VERBOSE,
)


def _is_likely_caption(text: str) -> bool:
    """Heuristic: short text near an image is likely a caption.

    Captions typically contain proper nouns (names), dates, or descriptive labels.
    Generic short prose ("More text.", "He walked on.") should not be absorbed.
    """
    text = text.strip()
    if not text:
        return False
    words = text.split()
    if len(words) > _MAX_CAPTION_WORDS:
        return False
    # Must have caption-like content (names, dates, descriptive labels)
    if _CAPTION_PATTERNS.search(text):
        return True
    # Short text with multiple capitalized words (proper nouns, not sentence-start)
    # e.g., "Moise and Sophie's Family" but not "More text."
    if len(words) <= 8:
        caps = [w for w in words if w and w[0].isupper() and len(w) > 1]
        if len(caps) >= 2:
            return True
    return False


def _peek_caption_siblings(node) -> List[str]:
    """Return caption-like <p> sibling text without mutating the tree."""
    from bs4 import NavigableString

    texts: List[str] = []
    sibling = node.next_sibling

    while isinstance(sibling, NavigableString) and not sibling.strip():
        sibling = sibling.next_sibling

    for _ in range(2):
        if sibling is None or sibling.name != "p":
            break
        text = sibling.get_text(" ", strip=True)
        if not _is_likely_caption(text):
            break
        texts.append(text)
        sibling = sibling.next_sibling
        while isinstance(sibling, NavigableString) and not sibling.strip():
            sibling = sibling.next_sibling

    return texts


def _crop_match_texts(crop: Dict[str, Any]) -> List[str]:
    """Prefer crop-pipeline descriptions; fall back to OCR alt only if needed."""
    texts = []
    image_description = _normalize_ws(crop.get("image_description") or "")
    caption_text = _normalize_ws(crop.get("caption_text") or "")
    alt = _normalize_ws(crop.get("alt") or "")
    if image_description:
        texts.append(image_description)
    if caption_text:
        texts.append(caption_text)
    if not texts and alt:
        texts.append(alt)
    return texts


def _block_match_texts(tag) -> List[str]:
    texts = []
    alt = _normalize_ws(tag.get("alt") or "")
    if alt:
        texts.append(alt)
    parent = tag.parent
    if parent and parent.name == "figure":
        figcaption = parent.find("figcaption")
        if figcaption:
            caption = _normalize_ws(figcaption.get_text(" ", strip=True))
            if caption:
                texts.append(caption)
    else:
        texts.extend(_peek_caption_siblings(tag))
    return texts


def _descriptor_similarity(a: str, b: str) -> float:
    a_norm = _normalize_ws(a).casefold()
    b_norm = _normalize_ws(b).casefold()
    if not a_norm or not b_norm:
        return 0.0
    if a_norm == b_norm:
        return 1.0
    ratio = SequenceMatcher(None, a_norm, b_norm).ratio()
    tokens_a = set(_title_tokens(a_norm))
    tokens_b = set(_title_tokens(b_norm))
    overlap = 0.0
    if tokens_a and tokens_b:
        overlap = len(tokens_a & tokens_b) / max(len(tokens_a), len(tokens_b))
    return max(ratio, overlap)


def _match_crops_to_img_tags(img_tags, crops: List[Dict[str, Any]]) -> Dict[int, int]:
    """Match crops to OCR image/caption blocks using descriptor similarity."""
    n_tags = len(img_tags)
    n_crops = len(crops)
    if not n_tags or not n_crops:
        return {}
    if max(n_tags, n_crops) > 8:
        return {idx: idx for idx in range(min(n_tags, n_crops))}

    block_texts = [_block_match_texts(tag) for tag in img_tags]
    crop_texts = [_crop_match_texts(crop) for crop in crops]
    scores: List[List[float]] = []
    for crop_idx, texts in enumerate(crop_texts):
        row = []
        for block_idx, block in enumerate(block_texts):
            best = 0.0
            for crop_text in texts:
                for block_text in block:
                    best = max(best, _descriptor_similarity(crop_text, block_text))
            if crop_idx == block_idx:
                best += 0.05
            row.append(best)
        scores.append(row)

    @lru_cache(maxsize=None)
    def solve(block_idx: int, used_mask: int):
        if block_idx >= n_tags:
            return 0.0, ()
        best_score, best_assignment = solve(block_idx + 1, used_mask)
        best_tuple = (-1,) + best_assignment
        for crop_idx in range(n_crops):
            if used_mask & (1 << crop_idx):
                continue
            score = scores[crop_idx][block_idx]
            tail_score, tail_assignment = solve(block_idx + 1, used_mask | (1 << crop_idx))
            total = score + tail_score
            if total > best_score:
                best_score = total
                best_tuple = (crop_idx,) + tail_assignment
        return best_score, best_tuple

    _, assignment = solve(0, 0)
    return {
        block_idx: crop_idx
        for block_idx, crop_idx in enumerate(assignment)
        if isinstance(crop_idx, int) and 0 <= crop_idx < n_crops
    }


def _previous_significant_tag(node):
    from bs4 import NavigableString

    sibling = node.previous_sibling
    while sibling is not None:
        if isinstance(sibling, NavigableString):
            if sibling.strip():
                return None
            sibling = sibling.previous_sibling
            continue
        return sibling
    return None


def _next_significant_tag(node):
    from bs4 import NavigableString

    sibling = node.next_sibling
    while sibling is not None:
        if isinstance(sibling, NavigableString):
            if sibling.strip():
                return None
            sibling = sibling.next_sibling
            continue
        return sibling
    return None


def _stitch_figure_interruptions(soup) -> None:
    """Merge prose fragments split only by a run of figures."""
    for figure in list(soup.find_all("figure")):
        if not figure.parent:
            continue
        prev_sig = _previous_significant_tag(figure)
        if getattr(prev_sig, "name", None) == "figure":
            continue
        last = figure
        next_sig = _next_significant_tag(last)
        while getattr(next_sig, "name", None) == "figure":
            last = next_sig
            next_sig = _next_significant_tag(last)
        if getattr(prev_sig, "name", None) != "p" or getattr(next_sig, "name", None) != "p":
            continue
        prev_text = prev_sig.get_text(" ", strip=True)
        next_text = next_sig.get_text(" ", strip=True)
        if not _should_stitch_page_break(prev_text, next_text):
            continue
        _append_paragraph_children(prev_sig, next_sig)
        next_sig.decompose()


def _expand_multi_count_img_tags(soup) -> None:
    """Expand OCR placeholders like <img data-count="2"> into multiple tags."""
    for tag in list(soup.find_all("img")):
        try:
            count = int(tag.get("data-count") or 1)
        except (TypeError, ValueError):
            count = 1
        if count <= 1:
            tag.attrs.pop("data-count", None)
            continue
        tag.attrs.pop("data-count", None)
        anchor = tag
        for _ in range(count - 1):
            clone = deepcopy(tag)
            clone.attrs.pop("src", None)
            clone.attrs.pop("data-crop-filename", None)
            anchor.insert_after(clone)
            anchor = clone


def _attach_images(html: str, crops: List[Dict[str, Any]], rel_src: str) -> str:
    """Attach cropped images to <img> placeholders with <figure>/<figcaption> wrapping.

    Handles two OCR output formats:
    - New format: <figure><img alt="..."><figcaption>...</figcaption></figure>
      → just sets src/alt/data-crop-filename on the existing structure.
    - Old format: <img alt="..."> followed optionally by a caption <p>
      → wraps in <figure>, detects adjacent caption <p> and converts to <figcaption>.

    Matching: descriptor-based against OCR alt/caption context, with positional
    fallback when the page is too large or descriptors are insufficient.
    """
    if not html or not crops:
        return html
    soup = BeautifulSoup(html, "html.parser")
    _expand_multi_count_img_tags(soup)
    img_tags = soup.find_all("img")
    crop_matches = _match_crops_to_img_tags(img_tags, crops)

    n_tags = len(img_tags)
    n_crops = len(crops)
    if n_tags != n_crops:
        print(f"  [build] Warning: {n_tags} <img> tags vs {n_crops} crops on page — matching by descriptors with fallback",
              file=sys.stderr)

    for idx, tag in enumerate(img_tags):
        crop_idx = crop_matches.get(idx)
        if crop_idx is None:
            continue
        crop = crops[crop_idx]
        filename = crop.get("filename")
        if not filename:
            continue

        # Rich alt text — prefer VLM image_description over OCR alt
        alt = crop.get("image_description") or crop.get("alt") or ""
        tag["src"] = f"{rel_src}/{filename}"
        tag["alt"] = alt
        tag["data-crop-filename"] = filename

        parent = tag.parent
        already_in_figure = parent and parent.name == "figure"

        if already_in_figure:
            # New OCR format: <figure> already wraps the <img>.
            # Add crop metadata; leave existing <figcaption> intact.
            figure = parent
            figure["data-placement"] = "ocr-figure"
            existing_figcap = figure.find("figcaption")
            caption_text = crop.get("caption_text")
            if existing_figcap:
                figure["data-caption-source"] = "ocr"
            elif caption_text:
                figcaption = soup.new_tag("figcaption")
                figcaption.string = caption_text
                figure.append(figcaption)
                figure["data-caption-source"] = "crop-pipeline"
        else:
            # Old OCR format: bare <img> — wrap in <figure>.
            figure = soup.new_tag("figure")
            tag.wrap(figure)
            figure["data-placement"] = "ocr-inline"

            # Try to find a caption: crop pipeline caption or adjacent <p>
            caption_text = crop.get("caption_text")
            if caption_text:
                figcaption = soup.new_tag("figcaption")
                figcaption.string = caption_text
                figure.append(figcaption)
                figure["data-caption-source"] = "crop-pipeline"
            else:
                # Heuristic: check next sibling(s) for caption-like <p> tags
                if _absorb_caption_siblings(figure, soup):
                    figure["data-caption-source"] = "heuristic"

    _stitch_figure_interruptions(soup)
    return soup.decode_contents()


def _absorb_caption_siblings(figure, soup) -> bool:
    """Move short caption-like <p> siblings after a <figure> into <figcaption>.

    Absorbs one or two consecutive short <p> tags (e.g., a title line
    followed by a "Back Row: ..." list). Stops at the first non-caption.

    Returns True if any captions were absorbed.
    """
    from bs4 import NavigableString

    absorbed = []
    sibling = figure.next_sibling

    # Skip whitespace text nodes
    while isinstance(sibling, NavigableString) and not sibling.strip():
        sibling = sibling.next_sibling

    # Check up to 2 consecutive caption-like <p> tags
    for _ in range(2):
        if sibling is None or sibling.name != "p":
            break
        text = sibling.get_text(strip=True)
        if not _is_likely_caption(text):
            break
        absorbed.append(sibling)
        next_sib = sibling.next_sibling
        # Skip whitespace
        while isinstance(next_sib, NavigableString) and not next_sib.strip():
            next_sib = next_sib.next_sibling
        sibling = next_sib

    if not absorbed:
        return False

    figcaption = soup.new_tag("figcaption")
    for p_tag in absorbed:
        # Move content into figcaption (preserve <br> etc.)
        for child in list(p_tag.children):
            figcaption.append(child.extract())
        # Add line break between absorbed paragraphs
        if p_tag is not absorbed[-1]:
            figcaption.append(soup.new_tag("br"))
        p_tag.decompose()

    figure.append(figcaption)
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Build per-chapter HTML files from pages + portions.")
    parser.add_argument("--pages", required=True, help="page_html_v1 JSONL (with printed_page_number)")
    parser.add_argument("--portions", required=True, help="portion_hyp_v1 JSONL")
    parser.add_argument("--out", required=True, help="Output manifest JSONL path")
    parser.add_argument("--output-dir", dest="output_dir", default=None,
                        help="Directory to write HTML files (default: output/html under run dir)")
    parser.add_argument("--illustration-manifest", dest="illustration_manifest", default=None,
                        help="Optional illustration_manifest.jsonl to attach img src tags")
    parser.add_argument("--images-subdir", dest="images_subdir", default="images",
                        help="Subdir under output/html for cropped images (default: images)")
    parser.add_argument("--book-title", dest="book_title", default="",
                        help="Book title for index page and HTML <title>")
    parser.add_argument("--book-author", dest="book_author", default="",
                        help="Book author for index page")
    parser.add_argument(
        "--merge-contiguous-genealogy-tables",
        dest="merge_contiguous_genealogy_tables",
        action="store_true",
        default=False,
        help="Collapse contiguous same-schema genealogy tables into one table with subgroup heading rows.",
    )
    parser.add_argument("--run-id", dest="run_id", default=None, help="Run ID for progress logging")
    parser.add_argument("--state-file", dest="state_file", default=None, help="Pipeline state JSON path")
    parser.add_argument("--progress-file", dest="progress_file", default=None, help="Pipeline progress JSONL path")
    args = parser.parse_args()

    pages = list(read_jsonl(args.pages))
    portions = list(read_jsonl(args.portions))
    if not pages:
        raise SystemExit(f"Input pages empty: {args.pages}")
    if not portions:
        raise SystemExit(f"Input portions empty: {args.portions}")

    book_title = args.book_title or "Book"
    book_author = args.book_author or ""

    out_path = Path(args.out)
    run_dir = _resolve_run_dir(out_path)
    html_dir = Path(args.output_dir) if args.output_dir else (run_dir / "output" / "html")
    ensure_dir(str(html_dir))
    images_dir = html_dir / args.images_subdir

    # Load illustration manifest and copy image files
    crops_by_page: Dict[int, List[Dict[str, Any]]] = {}
    if args.illustration_manifest:
        crops_by_page = _group_manifest_by_page(args.illustration_manifest)
        ensure_dir(str(images_dir))
        manifest_dir = Path(args.illustration_manifest).parent
        crops_dir = manifest_dir / "images"
        for rows in crops_by_page.values():
            for row in rows:
                filename = row.get("filename")
                if not filename:
                    continue
                src_path = crops_dir / filename
                if not src_path.exists():
                    continue
                dst_path = images_dir / filename
                if not dst_path.exists():
                    dst_path.write_bytes(src_path.read_bytes())

    pages_sorted = sorted(pages, key=_page_sort_key)
    pages_scan = sorted(pages, key=lambda r: int(r.get("page_number") or r.get("page") or 0))
    manifest_rows = []
    toc_entries = []
    covered_pages = set()
    chapters_by_start = {}
    portion_titles = [p.get("title") or p.get("portion_id") or "" for p in portions]

    # ── Build chapters ──────────────────────────────────────────────────
    chapter_files: List[Dict[str, Any]] = []  # For navigation pass

    chapter_counter = 0
    for portion_idx, portion in enumerate(portions):
        page_start = portion.get("page_start")
        page_end = portion.get("page_end") or page_start
        title = portion.get("title") or portion.get("portion_id") or f"Chapter {portion_idx + 1}"
        if not isinstance(page_start, int):
            continue
        if not isinstance(page_end, int):
            page_end = page_start

        chapter_pages = [
            p for p in pages_sorted
            if isinstance(p.get("printed_page_number"), int)
            and page_start <= p["printed_page_number"] <= page_end
        ]
        for p in chapter_pages:
            covered_pages.add(p.get("printed_page_number"))

        prepared_pages = []
        for page in chapter_pages:
            html = page.get("html") or page.get("raw_html") or ""
            page_num = page.get("page_number") or page.get("page")
            crops = crops_by_page.get(page_num, []) if isinstance(page_num, int) else []
            if crops:
                html = _attach_images(html, crops, args.images_subdir.rstrip("/"))
            html = _strip_headers_and_numbers(html)
            html = _add_table_scope(html)
            html = _normalize_heading_breaks(html)
            prepared_pages.append({
                "html": html,
                "page_number": page_num,
                "printed_page_number": page.get("printed_page_number"),
                "owner_heading": _first_strong_owner_heading(html),
            })

        candidate_titles = portion_titles[portion_idx:]
        stale_portion = any(
            entry.get("kind") == "chapter" and _titles_related(title, entry.get("title"))
            for entry in chapter_files
        )
        refined_segments = _refine_chapter_segments(
            title,
            page_start,
            prepared_pages,
            candidate_titles,
            previous_title=chapter_files[-1]["title"] if chapter_files else None,
            stale_portion=stale_portion,
        )

        for segment in refined_segments:
            if segment.get("carry_back") and chapter_files:
                prev_entry = chapter_files[-1]
                _merge_carry_back_segment(prev_entry, segment)
                prev_toc = chapters_by_start.get(prev_entry["page_start"])
                if prev_toc:
                    prev_toc["page_end"] = prev_entry["page_end"]
                if toc_entries:
                    toc_entries[-1]["page_end"] = prev_entry["page_end"]
                continue

            chapter_counter += 1
            filename = f"chapter-{chapter_counter:03d}.html"
            body_html = segment["body_html"]
            if args.merge_contiguous_genealogy_tables:
                body_html = _merge_contiguous_genealogy_tables(body_html)
            toc_entries.append({
                "title": segment["title"],
                "file": filename,
                "page_start": segment["page_start"],
                "page_end": segment["page_end"],
            })
            chapters_by_start[segment["page_start"]] = {
                "title": segment["title"],
                "file": filename,
                "page_start": segment["page_start"],
                "page_end": segment["page_end"],
            }

            chapter_files.append({
                "filename": filename,
                "title": segment["title"],
                "body_html": body_html,
                "page_start": segment["page_start"],
                "page_end": segment["page_end"],
                "kind": "chapter",
                "chapter_index": chapter_counter,
                "source_pages": segment["source_pages"],
                "source_printed_pages": segment["source_printed_pages"],
                "source_portion_title": segment["source_portion_title"],
                "source_portion_page_start": segment["source_portion_page_start"],
                "source_portion_titles": segment.get("source_portion_titles") or [segment["source_portion_title"]],
                "source_portion_page_starts": segment.get("source_portion_page_starts") or [segment["source_portion_page_start"]],
            })

    # ── Build fallback pages (uncovered by chapters) ────────────────────
    fallback_entries = []
    fallback_page_files: List[Dict[str, Any]] = []
    fallback_count = 0
    for page in pages_sorted:
        printed_num = page.get("printed_page_number")
        printed_text = page.get("printed_page_number_text")
        page_num = page.get("page_number") or page.get("page")
        if isinstance(printed_num, int) and printed_num in covered_pages:
            continue
        fallback_count += 1
        filename = f"page-{fallback_count:03d}.html"
        if printed_text:
            title = f"Page {printed_text}"
        elif isinstance(printed_num, int):
            title = f"Page {printed_num}"
        elif page_num is not None:
            title = f"Image {page_num}"
        else:
            title = "Page"
        html = page.get("html") or page.get("raw_html") or ""
        page_num = page.get("page_number") or page.get("page")
        crops = crops_by_page.get(page_num, []) if isinstance(page_num, int) else []
        if crops:
            html = _attach_images(html, crops, args.images_subdir.rstrip("/"))
        body_html = _strip_headers_and_numbers(html)
        body_html = _add_table_scope(body_html)
        if args.merge_contiguous_genealogy_tables:
            body_html = _merge_contiguous_genealogy_tables(body_html)

        fallback_entries.append({
            "title": title,
            "file": filename,
            "page_number": page_num,
            "printed_page_number": printed_num,
            "printed_page_number_text": printed_text,
        })

        fallback_page_files.append({
            "filename": filename,
            "title": title,
            "body_html": body_html,
            "page_start": printed_num if isinstance(printed_num, int) else None,
            "page_end": printed_num if isinstance(printed_num, int) else None,
            "kind": "page",
            "chapter_index": None,
        })

    # Front matter pages come before chapters in navigation order
    chapter_files = fallback_page_files + chapter_files

    # ── Write all files with navigation ─────────────────────────────────
    for i, entry in enumerate(chapter_files):
        prev_file = chapter_files[i - 1]["filename"] if i > 0 else None
        prev_title = chapter_files[i - 1]["title"] if i > 0 else None
        next_file = chapter_files[i + 1]["filename"] if i < len(chapter_files) - 1 else None
        next_title = chapter_files[i + 1]["title"] if i < len(chapter_files) - 1 else None

        nav_top = _build_nav(prev_file, prev_title, next_file, next_title)
        nav_bottom = _build_nav(prev_file, prev_title, next_file, next_title, is_bottom=True)
        page_title = f"{entry['title']} — {book_title}" if book_title else entry["title"]
        body_html = entry["body_html"]
        if args.merge_contiguous_genealogy_tables:
            body_html = _merge_contiguous_genealogy_tables(body_html)
            entry["body_html"] = body_html

        full_html = _html5_wrap(body_html, page_title, nav_top, nav_bottom)
        file_path = html_dir / entry["filename"]
        file_path.write_text(full_html, encoding="utf-8")

        manifest_rows.append({
            "schema_version": "chapter_html_manifest_v1",
            "module_id": "build_chapter_html_v1",
            "run_id": args.run_id,
            "created_at": _utc(),
            "chapter_index": entry["chapter_index"],
            "title": entry["title"],
            "page_start": entry["page_start"],
            "page_end": entry["page_end"],
            "file": str(file_path),
            "kind": entry["kind"],
            "source_pages": entry.get("source_pages"),
            "source_printed_pages": entry.get("source_printed_pages"),
            "source_portion_title": entry.get("source_portion_title"),
            "source_portion_page_start": entry.get("source_portion_page_start"),
            "source_portion_titles": entry.get("source_portion_titles"),
            "source_portion_page_starts": entry.get("source_portion_page_starts"),
        })

    # ── Build index page ────────────────────────────────────────────────
    index_entries = []
    emitted_chapters = set()
    fallback_by_page = {}
    for entry in fallback_entries:
        key = entry.get("page_number")
        if key is not None and key not in fallback_by_page:
            fallback_by_page[key] = entry

    for page in pages_scan:
        printed_num = page.get("printed_page_number")
        page_num = page.get("page_number") or page.get("page")
        if isinstance(printed_num, int) and printed_num in chapters_by_start and printed_num not in emitted_chapters:
            entry = chapters_by_start[printed_num]
            label = entry["title"]
            page_range = f"p. {entry['page_start']}" if entry["page_start"] == entry["page_end"] else f"p. {entry['page_start']}&ndash;{entry['page_end']}"
            index_entries.append({"label": label, "file": entry["file"], "page_range": page_range})
            emitted_chapters.add(printed_num)
        if not (isinstance(printed_num, int) and printed_num in covered_pages):
            fe = fallback_by_page.get(page_num)
            if fe:
                index_entries.append({"label": fe["title"], "file": fe["file"], "page_range": ""})

    # Build index body
    author_line = f'<p class="author">{html_escape(book_author)}</p>' if book_author else ""
    toc_items = []
    for entry in index_entries:
        range_span = f' <span class="page-range">({entry["page_range"]})</span>' if entry.get("page_range") else ""
        toc_items.append(f'  <li><a href="{entry["file"]}">{html_escape(entry["label"])}</a>{range_span}</li>')
    index_body = f"""<div class="book-header">
<h1>{html_escape(book_title)}</h1>
{author_line}
</div>
<h2>Contents</h2>
<ul class="toc-list">
{chr(10).join(toc_items)}
</ul>
"""
    index_html = _html5_wrap(index_body, book_title or "Index")
    index_path = html_dir / "index.html"
    index_path.write_text(index_html, encoding="utf-8")

    save_jsonl(args.out, manifest_rows)
    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    logger.log("build", "done", current=len(manifest_rows), total=len(manifest_rows),
               message=f"Wrote {len(manifest_rows)} chapters to {html_dir}")


if __name__ == "__main__":
    main()
