#!/usr/bin/env python3
"""
Build chapter HTML files from pages and TOC-derived portions.
Removes running heads and page numbers from final HTML output.
"""
import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

from modules.common.utils import read_jsonl, save_jsonl, ensure_dir, ProgressLogger


def _resolve_run_dir(out_path: Path) -> Path:
    cur = out_path.parent
    for parent in [cur] + list(cur.parents):
        if (parent / "pipeline_state.json").exists():
            return parent
    return cur


def _strip_headers_and_numbers(html: str) -> str:
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(class_="page-number"):
        tag.decompose()
    for tag in soup.find_all(class_="running-head"):
        tag.decompose()
    # Return inner HTML without wrapping <html>/<body>
    return soup.decode_contents()


def _page_sort_key(row: Dict[str, Any]) -> tuple:
    pn = row.get("printed_page_number")
    if pn is None:
        pn = row.get("page_number") or row.get("page") or 0
    return (int(pn), int(row.get("page_number") or row.get("page") or 0))


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


def _attach_img_src(html: str, crops: List[Dict[str, Any]], rel_src: str) -> str:
    if not html or not crops:
        return html
    soup = BeautifulSoup(html, "html.parser")
    img_tags = soup.find_all("img")
    for idx, tag in enumerate(img_tags):
        if idx >= len(crops):
            break
        crop = crops[idx]
        filename = crop.get("filename")
        if not filename:
            continue
        tag["src"] = f"{rel_src}/{filename}"
        tag["data-crop-filename"] = filename
        if not tag.get("alt"):
            tag["alt"] = crop.get("alt") or ""
    return soup.decode_contents()


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

    out_path = Path(args.out)
    run_dir = _resolve_run_dir(out_path)
    html_dir = Path(args.output_dir) if args.output_dir else (run_dir / "output" / "html")
    ensure_dir(str(html_dir))
    images_dir = html_dir / args.images_subdir

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

    for idx, portion in enumerate(portions, start=1):
        page_start = portion.get("page_start")
        page_end = portion.get("page_end") or page_start
        title = portion.get("title") or portion.get("portion_id") or f"Chapter {idx}"
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

        combined_html = []
        for page in chapter_pages:
            html = page.get("html") or page.get("raw_html") or ""
            page_num = page.get("page_number") or page.get("page")
            crops = crops_by_page.get(page_num, []) if isinstance(page_num, int) else []
            if crops:
                html = _attach_img_src(html, crops, args.images_subdir.rstrip("/"))
            combined_html.append(_strip_headers_and_numbers(html))
        body_html = "\n".join([h for h in combined_html if h])

        filename = f"chapter-{idx:03d}.html"
        toc_entries.append({"title": title, "file": filename, "page_start": page_start, "page_end": page_end})
        chapters_by_start[page_start] = {"title": title, "file": filename, "page_start": page_start, "page_end": page_end}
        chapter_path = html_dir / filename
        with chapter_path.open("w", encoding="utf-8") as f:
            f.write('<p><a href="index.html">Index</a></p>\n')
            f.write(body_html)

        manifest_rows.append({
            "chapter_index": idx,
            "title": title,
            "page_start": page_start,
            "page_end": page_end,
            "file": str(chapter_path),
            "kind": "chapter",
        })

    fallback_entries = []
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
            label = printed_text
            title = f"Page {label}"
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
            html = _attach_img_src(html, crops, args.images_subdir.rstrip("/"))
        body_html = _strip_headers_and_numbers(html)
        page_path = html_dir / filename
        with page_path.open("w", encoding="utf-8") as f:
            f.write('<p><a href="index.html">Index</a></p>\n')
            f.write(body_html)
        fallback_entries.append({
            "title": title,
            "file": filename,
            "page_number": page_num,
            "printed_page_number": printed_num,
            "printed_page_number_text": printed_text,
        })
        manifest_rows.append({
            "chapter_index": None,
            "title": title,
            "page_start": printed_num if isinstance(printed_num, int) else None,
            "page_end": printed_num if isinstance(printed_num, int) else None,
            "file": str(page_path),
            "kind": "page",
        })

    # Build index in physical order: insert chapters at their start page; include uncovered pages inline.
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
            label = f"{entry['title']} (p. {entry['page_start']})"
            index_entries.append({"label": label, "file": entry["file"]})
            emitted_chapters.add(printed_num)
        # Add fallback page if not covered by any chapter range.
        if not (isinstance(printed_num, int) and printed_num in covered_pages):
            fe = fallback_by_page.get(page_num)
            if fe:
                label = fe["title"]
                filename = fe["file"]
            else:
                label = "Page"
                filename = None
            if filename:
                index_entries.append({"label": label, "file": filename})

    index_path = html_dir / "index.html"
    with index_path.open("w", encoding="utf-8") as f:
        f.write("<h1>Index</h1>\n<ul>\n")
        for entry in index_entries:
            f.write(f'  <li><a href="{entry["file"]}">{entry["label"]}</a></li>\n')
        f.write("</ul>\n")

    save_jsonl(args.out, manifest_rows)
    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    logger.log("build", "done", current=len(manifest_rows), total=len(manifest_rows),
               message=f"Wrote {len(manifest_rows)} chapters to {html_dir}")


if __name__ == "__main__":
    main()
