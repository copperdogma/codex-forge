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
from html import escape as html_escape
from pathlib import Path
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

from modules.common.utils import read_jsonl, save_jsonl, ensure_dir, ProgressLogger

try:
    from modules.adapter.table_rescue_onward_tables_v1.main import (
        _normalize_rescue_html as _normalize_genealogy_rescue_html,
    )
except Exception:  # pragma: no cover - optional downstream reuse
    _normalize_genealogy_rescue_html = None


_GENEALOGY_EXPECTED_HEADERS = ["name", "born", "married", "spouse", "boy", "girl", "died"]
_GENEALOGY_HEADER_TOKEN_SETS = {
    tuple(_GENEALOGY_EXPECTED_HEADERS),
    ("name", "born", "married", "spouse", "boygirl", "died"),
}
_GENEALOGY_FAMILY_HEADING_RE = re.compile(r"\b[A-Z][A-Z'’\-]+(?:\s+[A-Z][A-Z'’\-]+)*\s+FAMILY\b")
_GENEALOGY_GENERATION_CONTEXT_RE = re.compile(
    r"\b(?:great\s+grandchildren|grandchildren|children)\b",
    re.IGNORECASE,
)
_GENEALOGY_CONTEXT_LINE_RE = re.compile(
    r"(?:[A-Z][\w'’\-]*\s+)*?[A-Z][\w'’\-]*['’](?:s)?\s+(?:Great\s+Grandchildren|Grandchildren|Children)\b"
)


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


def _normalize_genealogy_token(text: str) -> str:
    return re.sub(r"[^a-z]", "", (text or "").lower())


def _genealogy_heading_lines(tag: Any) -> List[str]:
    if tag is None:
        return []
    raw_lines = [
        line.strip()
        for line in tag.get_text("\n", strip=True).split("\n")
        if line.strip()
    ]
    lines: List[str] = []
    for line in raw_lines:
        lines.extend(_split_flattened_genealogy_heading_line(line))
    return lines


def _split_flattened_genealogy_heading_line(line: str) -> List[str]:
    normalized = _normalize_ws(line)
    if not normalized:
        return []

    family_line = None
    prefix = normalized
    family_matches = list(_GENEALOGY_FAMILY_HEADING_RE.finditer(normalized))
    if family_matches and family_matches[-1].end() == len(normalized):
        family_line = family_matches[-1].group(0).strip()
        prefix = normalized[:family_matches[-1].start()].strip()

    parts: List[str] = []
    if prefix:
        pos = 0
        for match in _GENEALOGY_CONTEXT_LINE_RE.finditer(prefix):
            if prefix[pos:match.start()].strip():
                parts = []
                break
            parts.append(match.group(0).strip())
            pos = match.end()
        if parts and prefix[pos:].strip():
            parts = []
    if family_line:
        parts.append(family_line)

    if parts and all(
        _extract_genealogy_family_labels(part) or _is_genealogy_generation_context(part)
        for part in parts
    ):
        return parts
    return [normalized]


def _extract_genealogy_family_labels(text: str) -> List[str]:
    normalized = _normalize_ws(text).replace("’", "'").upper()
    return list(dict.fromkeys(_GENEALOGY_FAMILY_HEADING_RE.findall(normalized)))


def _is_genealogy_generation_context(text: str) -> bool:
    normalized = _normalize_ws(text).replace("’", "'")
    if not normalized or len(normalized) > 120:
        return False
    if _extract_genealogy_family_labels(normalized):
        return False
    return bool(_GENEALOGY_GENERATION_CONTEXT_RE.search(normalized))


def _is_genealogy_heading_tag(tag: Any) -> bool:
    if getattr(tag, "name", None) not in {"h1", "h2", "h3", "p"}:
        return False
    lines = _genealogy_heading_lines(tag)
    if not lines:
        return False
    return all(
        _extract_genealogy_family_labels(line) or _is_genealogy_generation_context(line)
        for line in lines
    )


def _genealogy_table_header_tokens(table: Any) -> List[str]:
    thead = table.find("thead", recursive=False)
    header_row = thead.find("tr", recursive=False) if thead is not None else None
    if header_row is None:
        header_row = table.find("tr", recursive=False)
    if header_row is None:
        return []
    return [
        _normalize_genealogy_token(cell.get_text(" ", strip=True))
        for cell in header_row.find_all(["th", "td"], recursive=False)
    ]


def _is_genealogy_table_header(table: Any) -> bool:
    return tuple(_genealogy_table_header_tokens(table)) in _GENEALOGY_HEADER_TOKEN_SETS


def _genealogy_table_column_count(table: Any) -> int:
    counts = [len(_genealogy_table_header_tokens(table))]
    tbody = table.find("tbody", recursive=False)
    rows = tbody.find_all("tr", recursive=False) if tbody is not None else table.find_all("tr", recursive=False)
    for row in rows:
        cells = row.find_all(["th", "td"], recursive=False)
        if cells:
            counts.append(len(cells))
    return max(counts) if counts else len(_GENEALOGY_EXPECTED_HEADERS)


def _is_compatible_genealogy_table(table: Any, expected_cols: int) -> bool:
    if _is_genealogy_table_header(table):
        return True
    if table.find("thead", recursive=False) is not None:
        return False

    tbody = table.find("tbody", recursive=False)
    rows = tbody.find_all("tr", recursive=False) if tbody is not None else table.find_all("tr", recursive=False)
    if not rows:
        return False

    saw_cells = False
    for row in rows:
        cells = row.find_all(["th", "td"], recursive=False)
        if not cells:
            continue
        saw_cells = True
        if len(cells) > expected_cols:
            return False
    return saw_cells


def _next_significant_sibling(node: Any) -> Any:
    sibling = node.next_sibling
    while sibling is not None:
        if getattr(sibling, "name", None) is not None:
            return sibling
        if str(sibling).strip():
            return sibling
        sibling = sibling.next_sibling
    return None


def _build_genealogy_subgroup_row(line: str, colspan: int, soup: BeautifulSoup) -> Any:
    row = soup.new_tag("tr")
    row["class"] = "genealogy-subgroup-heading"
    cell = soup.new_tag("th", colspan=str(colspan))
    cell.string = line
    row.append(cell)
    return row


def _clone_genealogy_row(row: Any, col_count: int, soup: BeautifulSoup) -> Any:
    cloned = deepcopy(row)
    cells = cloned.find_all(["td", "th"], recursive=False)
    if "genealogy-subgroup-heading" in (cloned.get("class") or []):
        if len(cells) == 1:
            cells[0]["colspan"] = str(col_count)
        return cloned

    while len(cells) < col_count:
        cell = soup.new_tag("td")
        cloned.append(cell)
        cells.append(cell)
    return cloned


def _append_genealogy_heading_and_rows(base_table: Any, heading_tags: List[Any], source_table: Any,
                                       soup: BeautifulSoup) -> None:
    base_tbody = base_table.find("tbody", recursive=False)
    if base_tbody is None:
        base_tbody = soup.new_tag("tbody")
        base_table.append(base_tbody)

    col_count = _genealogy_table_column_count(base_table)
    for tag in heading_tags:
        for line in _genealogy_heading_lines(tag):
            base_tbody.append(_build_genealogy_subgroup_row(line, col_count, soup))

    source_tbody = source_table.find("tbody", recursive=False)
    rows = source_tbody.find_all("tr", recursive=False) if source_tbody is not None else source_table.find_all("tr", recursive=False)
    if source_table.find("thead", recursive=False) is None and _is_genealogy_table_header(source_table) and rows:
        rows = rows[1:]
    for row in rows:
        base_tbody.append(_clone_genealogy_row(row, col_count, soup))


def _preserve_figure_and_image_attrs(original_html: str, merged_html: str) -> str:
    original_soup = BeautifulSoup(original_html or "", "html.parser")
    merged_soup = BeautifulSoup(merged_html or "", "html.parser")

    original_imgs = original_soup.find_all("img")
    merged_imgs = merged_soup.find_all("img")
    if len(original_imgs) != len(merged_imgs):
        return merged_html

    for original_img, merged_img in zip(original_imgs, merged_imgs):
        merged_img.attrs = dict(original_img.attrs)

        original_parent = original_img.parent
        merged_parent = merged_img.parent
        if getattr(original_parent, "name", None) == "figure" and getattr(merged_parent, "name", None) == "figure":
            merged_parent.attrs = dict(original_parent.attrs)

    return merged_soup.decode_contents()


def _merge_contiguous_genealogy_tables(html: str) -> str:
    if "<table" not in (html or "").lower():
        return html or ""

    normalized = html or ""
    if _normalize_genealogy_rescue_html is not None:
        normalized = _normalize_genealogy_rescue_html(normalized)

    soup = BeautifulSoup(normalized, "html.parser")
    for base_table in list(soup.find_all("table")):
        if base_table.parent is None or not _is_genealogy_table_header(base_table):
            continue

        expected_cols = _genealogy_table_column_count(base_table)
        cursor = base_table
        pending_headings: List[Any] = []

        while True:
            next_node = _next_significant_sibling(cursor)
            if next_node is None:
                break
            if _is_genealogy_heading_tag(next_node):
                pending_headings.append(next_node)
                cursor = next_node
                continue
            if getattr(next_node, "name", None) == "table" and pending_headings and _is_compatible_genealogy_table(next_node, expected_cols):
                _append_genealogy_heading_and_rows(base_table, pending_headings, next_node, soup)
                for heading in pending_headings:
                    heading.decompose()
                pending_headings = []
                next_node.decompose()
                cursor = base_table
                continue
            break

    return _preserve_figure_and_image_attrs(html, soup.decode_contents())


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


def _stitch_page_breaks(page_htmls: List[str]) -> str:
    soups = [BeautifulSoup(html or "", "html.parser") for html in page_htmls if html]
    if not soups:
        return ""
    for idx in range(1, len(soups)):
        prev = soups[idx - 1]
        current = soups[idx]
        prev_last = _last_significant_tag(prev)
        current_first = _first_significant_tag(current)
        if not prev_last or not current_first:
            continue
        if prev_last.name != "p" or current_first.name != "p":
            continue
        prev_text = prev_last.get_text(" ", strip=True)
        current_text = current_first.get_text(" ", strip=True)
        if _should_stitch_page_break(prev_text, current_text):
            _append_paragraph_children(prev_last, current_first)
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


def _attach_images(html: str, crops: List[Dict[str, Any]], rel_src: str) -> str:
    """Attach cropped images to <img> placeholders with <figure>/<figcaption> wrapping.

    Handles two OCR output formats:
    - New format: <figure><img alt="..."><figcaption>...</figcaption></figure>
      → just sets src/alt/data-crop-filename on the existing structure.
    - Old format: <img alt="..."> followed optionally by a caption <p>
      → wraps in <figure>, detects adjacent caption <p> and converts to <figcaption>.

    Matching: sequential by position (crops sorted by y-position, img tags in document order).
    """
    if not html or not crops:
        return html
    soup = BeautifulSoup(html, "html.parser")
    img_tags = soup.find_all("img")

    n_tags = len(img_tags)
    n_crops = len(crops)
    if n_tags != n_crops:
        print(f"  [build] Warning: {n_tags} <img> tags vs {n_crops} crops on page — matching by position",
              file=sys.stderr)

    for idx, tag in enumerate(img_tags):
        if idx >= n_crops:
            break
        crop = crops[idx]
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

        full_html = _html5_wrap(entry["body_html"], page_title, nav_top, nav_bottom)
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
