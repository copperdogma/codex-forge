from __future__ import annotations

import re
from datetime import datetime
from html import escape as html_escape
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from bs4 import BeautifulSoup

from modules.common.utils import ensure_dir, save_json, save_jsonl


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

_SOURCE_BLOCK_IDS_ATTR = "data-source-block-ids"
_SIGNIFICANT_TAGS = {
    "p",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "figure",
    "table",
    "ul",
    "ol",
    "dl",
    "blockquote",
}
_WHITESPACE_RE = re.compile(r"\s+")
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _utc() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _normalize_ws(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", (text or "").strip())


def _unique_preserve(values: Iterable[str]) -> List[str]:
    seen = set()
    ordered: List[str] = []
    for value in values:
        if not value or value in seen:
            continue
        ordered.append(value)
        seen.add(value)
    return ordered


def _related_text(a: str, b: str) -> bool:
    if not a or not b:
        return False
    if a == b or a in b or b in a:
        return True
    a_tokens = set(_TOKEN_RE.findall(a.casefold()))
    b_tokens = set(_TOKEN_RE.findall(b.casefold()))
    if not a_tokens or not b_tokens:
        return False
    overlap = len(a_tokens & b_tokens) / min(len(a_tokens), len(b_tokens))
    return overlap >= 0.8


def html5_wrap(body_html: str, title: str, nav_html_top: str = "",
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


def build_nav(prev_file: Optional[str], prev_title: Optional[str],
              next_file: Optional[str], next_title: Optional[str],
              is_bottom: bool = False) -> str:
    cls = "chapter-nav bottom" if is_bottom else "chapter-nav"
    prev_link = (
        f'<a href="{prev_file}">&larr; {html_escape(prev_title or "Prev")}</a>'
        if prev_file
        else '<span class="nav-placeholder"></span>'
    )
    next_link = (
        f'<a href="{next_file}">{html_escape(next_title or "Next")} &rarr;</a>'
        if next_file
        else '<span class="nav-placeholder"></span>'
    )
    return f'<nav class="{cls}">{prev_link}<a href="index.html">Index</a>{next_link}</nav>'


def _iter_bundle_blocks(soup: BeautifulSoup):
    for child in soup.contents:
        if getattr(child, "name", None) in _SIGNIFICANT_TAGS:
            yield child


def _block_kind_for_tag(tag: Any) -> str:
    name = getattr(tag, "name", "") or ""
    if name == "p":
        return "paragraph"
    if name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
        return "heading"
    if name == "figure":
        return "figure"
    if name == "table":
        return "table"
    if name in {"li", "dt", "dd"}:
        return "list_item"
    return "other"


def get_source_block_ids(tag: Any) -> List[str]:
    value = tag.get(_SOURCE_BLOCK_IDS_ATTR)
    if not value:
        return []
    if isinstance(value, list):
        return _unique_preserve(str(item) for item in value)
    return _unique_preserve(str(value).split())


def set_source_block_ids(tag: Any, source_block_ids: List[str]) -> None:
    ordered = _unique_preserve(source_block_ids)
    if ordered:
        tag[_SOURCE_BLOCK_IDS_ATTR] = " ".join(ordered)
    elif _SOURCE_BLOCK_IDS_ATTR in tag.attrs:
        del tag.attrs[_SOURCE_BLOCK_IDS_ATTR]


def merge_source_block_ids(dst: Any, src: Any) -> None:
    set_source_block_ids(dst, get_source_block_ids(dst) + get_source_block_ids(src))


def annotate_source_blocks(
    html: str,
    *,
    page_number: Optional[int],
    printed_page_number: Optional[int],
) -> tuple[str, Dict[str, Dict[str, Any]]]:
    soup = BeautifulSoup(html or "", "html.parser")
    source_blocks: Dict[str, Dict[str, Any]] = {}
    if not isinstance(page_number, int):
        return soup.decode_contents(), source_blocks

    for order, tag in enumerate(_iter_bundle_blocks(soup), start=1):
        source_block_id = f"p{page_number:03d}-b{order}"
        set_source_block_ids(tag, [source_block_id])
        source_blocks[source_block_id] = {
            "source_page_number": page_number,
            "source_printed_page_number": printed_page_number if isinstance(printed_page_number, int) else None,
            "block_kind": _block_kind_for_tag(tag),
            "text_quote": _normalize_ws(tag.get_text(" ", strip=True)) or None,
        }
    return soup.decode_contents(), source_blocks


def restore_top_level_source_block_ids(original_html: str, merged_html: str) -> str:
    """
    Reattach top-level source block ids after a deterministic HTML transform.

    This is intentionally conservative and order-based. It is used for the
    genealogy merge path, which can rebuild HTML and strip custom attrs even
    though the surviving top-level block order remains meaningful.
    """

    original_soup = BeautifulSoup(original_html or "", "html.parser")
    merged_soup = BeautifulSoup(merged_html or "", "html.parser")
    original_blocks = list(_iter_bundle_blocks(original_soup))
    pointer = 0

    for merged_block in _iter_bundle_blocks(merged_soup):
        existing_ids = get_source_block_ids(merged_block)
        if existing_ids:
            existing_id_set = set(existing_ids)
            scan = pointer
            matched_any = False
            while scan < len(original_blocks):
                original_ids = get_source_block_ids(original_blocks[scan])
                if not original_ids:
                    scan += 1
                    continue
                if existing_id_set.intersection(original_ids):
                    matched_any = True
                    scan += 1
                    continue
                if matched_any:
                    pointer = scan
                    break
                scan += 1
            else:
                if matched_any:
                    pointer = scan
            continue

        merged_text = _normalize_ws(merged_block.get_text(" ", strip=True))
        matched_ids: List[str] = []
        scan = pointer

        while scan < len(original_blocks):
            original_block = original_blocks[scan]
            original_ids = get_source_block_ids(original_block)
            original_text = _normalize_ws(original_block.get_text(" ", strip=True))
            if not original_ids:
                scan += 1
                continue

            same_block = (
                merged_block.name == original_block.name
                and merged_text == original_text
            )
            text_folded_in = _related_text(merged_text, original_text)

            if not matched_ids:
                if same_block or text_folded_in:
                    matched_ids.extend(original_ids)
                    scan += 1
                    if same_block:
                        break
                    continue
                break

            if text_folded_in:
                matched_ids.extend(original_ids)
                scan += 1
                continue
            break

        if matched_ids:
            set_source_block_ids(merged_block, matched_ids)
            pointer = scan

    return merged_soup.decode_contents()


def _slugify_identifier(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").casefold()).strip("-")
    return slug or "book"


def emit_doc_web_bundle(
    *,
    html_dir: Path,
    manifest_path: Path,
    entries: List[Dict[str, Any]],
    index_entries: List[Dict[str, Any]],
    book_title: str,
    book_author: str,
    source_artifact: str,
    source_block_index: Dict[str, Dict[str, Any]],
    images_subdir: Optional[str],
    run_id: Optional[str],
    module_id: str,
) -> List[Dict[str, Any]]:
    ensure_dir(str(html_dir))
    ensure_dir(str(html_dir / "provenance"))

    manifest_rows: List[Dict[str, Any]] = []
    doc_web_entries: List[Dict[str, Any]] = []
    provenance_rows: List[Dict[str, Any]] = []
    created_at = _utc()
    document_id = _slugify_identifier(book_title or run_id or "book")

    for index, entry in enumerate(entries):
        prev_entry = entries[index - 1] if index > 0 else None
        next_entry = entries[index + 1] if index + 1 < len(entries) else None

        body_soup = BeautifulSoup(entry["body_html"] or "", "html.parser")
        entry_id = Path(entry["filename"]).stem

        for ordinal, tag in enumerate(_iter_bundle_blocks(body_soup), start=1):
            source_block_ids = get_source_block_ids(tag)
            if not source_block_ids:
                raise ValueError(
                    f"missing source block ids on emitted block {ordinal} in {entry['filename']}"
                )
            unresolved_ids = [block_id for block_id in source_block_ids if block_id not in source_block_index]
            if unresolved_ids:
                raise ValueError(
                    f"unresolved source block ids {unresolved_ids} in {entry['filename']}"
                )

            primary_source = source_block_index[source_block_ids[0]]
            block_id = f"blk-{entry_id}-{ordinal:04d}"
            tag["id"] = block_id
            if _SOURCE_BLOCK_IDS_ATTR in tag.attrs:
                del tag.attrs[_SOURCE_BLOCK_IDS_ATTR]

            block_kind = _block_kind_for_tag(tag)
            text_quote = _normalize_ws(tag.get_text(" ", strip=True)) or None
            provenance_rows.append({
                "schema_version": "doc_web_provenance_block_v1",
                "module_id": module_id,
                "run_id": run_id,
                "created_at": created_at,
                "block_id": block_id,
                "entry_id": entry_id,
                "block_kind": block_kind,
                "source_page_number": primary_source["source_page_number"],
                "source_element_ids": source_block_ids,
                "source_printed_page_number": primary_source.get("source_printed_page_number"),
                "source_printed_page_label": (
                    str(primary_source["source_printed_page_number"])
                    if primary_source.get("source_printed_page_number") is not None
                    else None
                ),
                "text_quote": text_quote if block_kind in {"paragraph", "heading", "list_item"} else None,
            })

        prev_file = prev_entry["filename"] if prev_entry else None
        prev_title = prev_entry["title"] if prev_entry else None
        next_file = next_entry["filename"] if next_entry else None
        next_title = next_entry["title"] if next_entry else None

        nav_top = build_nav(prev_file, prev_title, next_file, next_title)
        nav_bottom = build_nav(prev_file, prev_title, next_file, next_title, is_bottom=True)
        page_title = f"{entry['title']} — {book_title}" if book_title else entry["title"]
        full_html = html5_wrap(body_soup.decode_contents(), page_title, nav_top, nav_bottom)
        file_path = html_dir / entry["filename"]
        file_path.write_text(full_html, encoding="utf-8")

        manifest_rows.append({
            "schema_version": "chapter_html_manifest_v1",
            "module_id": module_id,
            "run_id": run_id,
            "created_at": created_at,
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
        doc_web_entries.append({
            "entry_id": entry_id,
            "kind": entry["kind"],
            "title": entry["title"],
            "path": entry["filename"],
            "order": index + 1,
            "prev_entry_id": Path(prev_file).stem if prev_file else None,
            "next_entry_id": Path(next_file).stem if next_file else None,
            "source_pages": list(entry.get("source_pages") or []),
            "printed_pages": list(entry.get("source_printed_pages") or []),
            "printed_page_start": entry.get("page_start"),
            "printed_page_end": entry.get("page_end"),
        })

    author_line = f'<p class="author">{html_escape(book_author)}</p>' if book_author else ""
    toc_items = []
    for entry in index_entries:
        page_range = entry.get("page_range") or ""
        range_span = f' <span class="page-range">({page_range})</span>' if page_range else ""
        toc_items.append(
            f'  <li><a href="{entry["file"]}">{html_escape(entry["label"])}</a>{range_span}</li>'
        )
    index_body = f"""<div class="book-header">
<h1>{html_escape(book_title)}</h1>
{author_line}
</div>
<h2>Contents</h2>
<ul class="toc-list">
{chr(10).join(toc_items)}
</ul>
"""
    index_html = html5_wrap(index_body, book_title or "Index")
    (html_dir / "index.html").write_text(index_html, encoding="utf-8")

    save_jsonl(str(manifest_path), manifest_rows)
    provenance_path = html_dir / "provenance" / "blocks.jsonl"
    save_jsonl(str(provenance_path), provenance_rows)
    save_json(
        str(html_dir / "manifest.json"),
        {
            "schema_version": "doc_web_bundle_manifest_v1",
            "module_id": module_id,
            "run_id": run_id,
            "created_at": created_at,
            "document_id": document_id,
            "title": book_title or "Book",
            "creator": book_author or None,
            "source_artifact": source_artifact,
            "index_path": "index.html",
            "entries": doc_web_entries,
            "reading_order": [entry["entry_id"] for entry in doc_web_entries],
            "asset_roots": [images_subdir] if images_subdir else [],
            "provenance_path": "provenance/blocks.jsonl",
        },
    )

    return manifest_rows
