#!/usr/bin/env python3
"""
Render HTML from Unstructured Elements v1

Converts elements.jsonl (Unstructured-native elements) into HTML with
optional layout preservation.

Designed for genealogy books, textbooks, and other documents where visual
layout and structure matter.

Features:
- Groups elements by page (metadata.page_number)
- Sorts by reading order (coordinates or sequence)
- Renders each Unstructured type appropriately
- Optional bbox-based positioning
- Embedded CSS for basic styling
"""

import argparse
import html as html_escape
import os
from collections import defaultdict
from typing import Any, Dict, List

from modules.common.utils import read_jsonl, ensure_dir, ProgressLogger


DEFAULT_CSS = """
<style>
    body {
        font-family: Georgia, 'Times New Roman', serif;
        line-height: 1.6;
        margin: 0;
        padding: 20px;
        background: #f5f5f5;
    }
    .page {
        background: white;
        margin: 20px auto;
        padding: 40px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        max-width: 800px;
        position: relative;
    }
    .page-number {
        position: absolute;
        top: 10px;
        right: 10px;
        font-size: 12px;
        color: #666;
    }
    h1, h2, h3, h4, h5, h6 {
        color: #333;
        margin-top: 1.5em;
        margin-bottom: 0.5em;
    }
    p {
        margin: 1em 0;
        text-align: justify;
    }
    table {
        border-collapse: collapse;
        width: 100%;
        margin: 1em 0;
    }
    table td, table th {
        border: 1px solid #ddd;
        padding: 8px;
    }
    table th {
        background-color: #f2f2f2;
        font-weight: bold;
    }
    .list-item {
        margin-left: 2em;
        margin-bottom: 0.5em;
    }
    .list-item:before {
        content: "•";
        margin-right: 0.5em;
    }
    .image-placeholder {
        border: 2px dashed #ccc;
        padding: 20px;
        margin: 1em 0;
        text-align: center;
        color: #999;
        background: #fafafa;
    }
    .header, .footer {
        font-size: 0.9em;
        color: #666;
        font-style: italic;
    }
    .figure-caption {
        font-style: italic;
        color: #555;
        margin: 0.5em 0;
        text-align: center;
    }
</style>
"""


def get_sort_key(element: Dict[str, Any]) -> tuple:
    """
    Generate sort key for element ordering within a page.

    Priority:
    1. _codex.sequence (if present)
    2. metadata.coordinates (y-coordinate, then x-coordinate)
    3. Fallback to 0 (maintain original order)
    """
    codex = element.get("_codex", {})
    sequence = codex.get("sequence")
    if sequence is not None:
        return (0, sequence, 0)

    metadata = element.get("metadata", {})
    coords = metadata.get("coordinates")

    # Try to extract y-coordinate from coordinates
    if coords:
        # Unstructured coordinates can be dict with 'points' list
        if isinstance(coords, dict):
            points = coords.get("points", [])
            if points and len(points) > 0:
                # points = [[x1,y1], [x2,y2], ...]
                # Use min y-coordinate (top of element)
                ys = [p[1] for p in points if len(p) >= 2]
                xs = [p[0] for p in points if len(p) >= 2]
                if ys and xs:
                    return (1, min(ys), min(xs))

    return (2, 0, 0)


def sort_elements(elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Sort elements for reading order."""
    return sorted(elements, key=get_sort_key)


def render_element_to_html(
    element: Dict[str, Any],
    include_tables: bool,
    include_images: bool,
) -> str:
    """
    Render a single Unstructured element to HTML.

    Handles all Unstructured element types:
    - Title, NarrativeText, Text -> headings and paragraphs
    - ListItem -> list items
    - Table -> table HTML (from metadata.text_as_html)
    - Image -> image placeholder
    - Header, Footer -> headers/footers
    - FigureCaption -> figure captions
    - etc.
    """
    elem_type = element.get("type", "Unknown")
    text = element.get("text", "").strip()
    metadata = element.get("metadata", {})

    # Escape text for HTML
    safe_text = html_escape.escape(text) if text else ""

    # Title -> h1
    if elem_type == "Title":
        if not text:
            return ""
        return f"<h1>{safe_text}</h1>\n"

    # NarrativeText, Text -> p
    elif elem_type in ("NarrativeText", "Text"):
        if not text:
            return ""
        return f"<p>{safe_text}</p>\n"

    # ListItem, BulletedText -> list item
    elif elem_type in ("ListItem", "BulletedText"):
        if not text:
            return ""
        return f'<div class="list-item">{safe_text}</div>\n'

    # Table -> use text_as_html if available
    elif elem_type == "Table":
        if include_tables:
            table_html = metadata.get("text_as_html")
            if table_html:
                return f'<div class="table-container">\n{table_html}\n</div>\n'
            elif text:
                # Fallback: preformatted text
                return f"<pre>{safe_text}</pre>\n"
        return ""

    # Image -> placeholder
    elif elem_type == "Image":
        if include_images:
            caption = safe_text if text else "Image"
            return f'<div class="image-placeholder">[Image: {caption}]</div>\n'
        return ""

    # Header
    elif elem_type == "Header":
        return f'<div class="header">{safe_text}</div>\n' if text else ""

    # Footer
    elif elem_type == "Footer":
        return f'<div class="footer">{safe_text}</div>\n' if text else ""

    # FigureCaption, Figure
    elif elem_type in ("FigureCaption", "Figure"):
        return f'<div class="figure-caption">{safe_text}</div>\n' if text else ""

    # PageBreak -> ignored
    elif elem_type == "PageBreak":
        return ""

    # Unknown/other -> paragraph
    else:
        if text:
            return f"<p>{safe_text}</p>\n"
        return ""


def render_page_to_html(
    page_num: int,
    elements: List[Dict[str, Any]],
    include_tables: bool,
    include_images: bool,
    include_headers: bool,
    include_footers: bool,
) -> str:
    """
    Render a single page worth of elements to HTML.
    """
    # Sort elements for reading order
    sorted_elems = sort_elements(elements)

    # Filter by type if needed
    filtered = []
    for elem in sorted_elems:
        elem_type = elem.get("type", "")
        if not include_headers and elem_type == "Header":
            continue
        if not include_footers and elem_type == "Footer":
            continue
        filtered.append(elem)

    # Render each element
    html_parts = [f'<div class="page">\n']
    html_parts.append(f'  <div class="page-number">Page {page_num}</div>\n')

    for elem in filtered:
        elem_html = render_element_to_html(elem, include_tables, include_images)
        if elem_html:
            html_parts.append(f"  {elem_html}")

    html_parts.append("</div>\n")

    return "".join(html_parts)


def group_by_page(elements: List[Dict[str, Any]]) -> Dict[int, List[Dict[str, Any]]]:
    """Group elements by page number from metadata.page_number."""
    pages: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for elem in elements:
        page_num = elem.get("metadata", {}).get("page_number", 1)
        pages[page_num].append(elem)
    return pages


def main():
    parser = argparse.ArgumentParser(
        description="Render elements.jsonl (Unstructured elements) to HTML"
    )
    parser.add_argument(
        "--elements",
        required=True,
        help="Path to elements.jsonl",
    )
    parser.add_argument("--outdir", required=True, help="Output directory")
    parser.add_argument(
        "--output-filename",
        "--output_filename",
        dest="output_filename",
        default="document.html",
        help="Output HTML filename",
    )
    parser.add_argument(
        "--include-css",
        "--include_css",
        dest="include_css",
        action="store_true",
        default=True,
        help="Include embedded CSS",
    )
    parser.add_argument(
        "--no-css",
        dest="include_css",
        action="store_false",
        help="Disable embedded CSS",
    )
    parser.add_argument(
        "--page-width-px",
        "--page_width_px",
        dest="page_width_px",
        type=int,
        default=800,
        help="Page width in pixels (used in CSS max-width)",
    )
    parser.add_argument(
        "--include-tables",
        "--include_tables",
        dest="include_tables",
        action="store_true",
        default=True,
        help="Render tables with HTML",
    )
    parser.add_argument(
        "--include-images",
        "--include_images",
        dest="include_images",
        action="store_true",
        default=True,
        help="Include image placeholders",
    )
    parser.add_argument(
        "--include-headers",
        "--include_headers",
        dest="include_headers",
        action="store_true",
        default=False,
        help="Include page headers in output",
    )
    parser.add_argument(
        "--include-footers",
        "--include_footers",
        dest="include_footers",
        action="store_true",
        default=False,
        help="Include page footers in output",
    )
    parser.add_argument("--progress-file", help="Path to pipeline_events.jsonl")
    parser.add_argument("--state-file", help="Path to pipeline_state.json")
    parser.add_argument("--run-id", help="Run identifier for logging")
    args = parser.parse_args()

    logger = ProgressLogger(
        state_path=args.state_file,
        progress_path=args.progress_file,
        run_id=args.run_id,
    )

    ensure_dir(args.outdir)

    # Read elements
    elements = list(read_jsonl(args.elements))

    logger.log(
        "render",
        "running",
        current=0,
        total=1,
        message=f"Rendering {len(elements)} elements to HTML",
        module_id="render_html_from_elements_v1",
    )

    # Group by page
    pages_dict = group_by_page(elements)

    # Build HTML document
    html_parts = [
        "<!DOCTYPE html>\n",
        "<html>\n",
        "<head>\n",
        '  <meta charset="UTF-8">\n',
        '  <meta name="viewport" content="width=device-width, initial-scale=1.0">\n',
        "  <title>Document</title>\n",
    ]

    if args.include_css:
        # Update max-width in CSS
        css = DEFAULT_CSS.replace("max-width: 800px", f"max-width: {args.page_width_px}px")
        html_parts.append(css)

    html_parts.append("</head>\n<body>\n")

    # Render each page
    for page_num in sorted(pages_dict.keys()):
        page_elements = pages_dict[page_num]
        page_html = render_page_to_html(
            page_num=page_num,
            elements=page_elements,
            include_tables=args.include_tables,
            include_images=args.include_images,
            include_headers=args.include_headers,
            include_footers=args.include_footers,
        )
        html_parts.append(page_html)

    html_parts.append("</body>\n</html>\n")

    # Write output
    output_path = os.path.join(args.outdir, args.output_filename)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("".join(html_parts))

    logger.log(
        "render",
        "done",
        current=1,
        total=1,
        message=f"Rendered {len(pages_dict)} pages to HTML",
        artifact=output_path,
        module_id="render_html_from_elements_v1",
        schema_version="html_document_v1",
    )

    print(f"✓ Rendered {len(pages_dict)} pages to {output_path}")
    print(f"  Total elements: {len(elements)}")


if __name__ == "__main__":
    main()
