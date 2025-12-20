#!/usr/bin/env python3
"""Run Azure Document Intelligence (prebuilt-layout) OCR on benchmark pages."""
import argparse
import json
import os
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import List, Optional, Tuple

from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient

ALLOWED_TAGS = {
    "h1", "h2", "p", "strong", "em", "ol", "ul", "li",
    "table", "thead", "tbody", "tr", "th", "td", "caption",
    "img", "dl", "dt", "dd",
}

RUNNING_HEAD_CLASS = "running-head"
PAGE_NUMBER_CLASS = "page-number"


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip().strip('"')
        os.environ.setdefault(key, val)


class TagSanitizer(HTMLParser):
    def __init__(self):
        super().__init__()
        self.out: List[str] = []

    def handle_starttag(self, tag: str, attrs):
        tag = tag.lower()
        if tag not in ALLOWED_TAGS:
            return
        if tag == "img":
            alt = ""
            for k, v in attrs:
                if k.lower() == "alt":
                    alt = v or ""
                    break
            if alt:
                self.out.append(f"<img alt=\"{alt}\">")
            else:
                self.out.append("<img alt=\"\">")
            return
        if tag == "p":
            cls = None
            for k, v in attrs:
                if k.lower() == "class":
                    cls = v
                    break
            if cls in (RUNNING_HEAD_CLASS, PAGE_NUMBER_CLASS):
                self.out.append(f"<p class=\"{cls}\">")
            else:
                self.out.append("<p>")
            return
        self.out.append(f"<{tag}>")

    def handle_endtag(self, tag: str):
        tag = tag.lower()
        if tag in ALLOWED_TAGS and tag != "img":
            self.out.append(f"</{tag}>")

    def handle_data(self, data: str):
        if data:
            self.out.append(data)

    def get_html(self) -> str:
        html = "".join(self.out)
        html = re.sub(r"\s+", " ", html)
        html = re.sub(r">\s+<", ">\n<", html)
        return html.strip() + "\n"


def sanitize_html(html: str) -> str:
    parser = TagSanitizer()
    parser.feed(html)
    return parser.get_html()


def find_images(pages: List[str]) -> dict:
    search_roots = [
        Path("output/runs/ff-canonical-dual-full-20251219p/01_extract_ocr_ensemble_v1/images"),
        Path("output/runs/ff-canonical-dual-full-20251219o/01_extract_ocr_ensemble_v1/images"),
        Path("output/runs/ff-canonical-dual-full-20251219n/01_extract_ocr_ensemble_v1/images"),
        Path("output/runs/ff-canonical-dual-full-20251219m/01_extract_ocr_ensemble_v1/images"),
        Path("output/runs/ff-canonical-dual-full-20251219/01_extract_ocr_ensemble_v1/images"),
        Path("input/images"),
        Path("input"),
    ]
    resolved = {}
    for name in pages:
        found: Optional[Path] = None
        for root in search_roots:
            candidate = root / name
            if candidate.exists():
                found = candidate
                break
        if not found:
            for root in search_roots:
                if root.exists():
                    matches = list(root.rglob(name))
                    if matches:
                        found = matches[0]
                        break
        if not found:
            raise SystemExit(f"Missing image: {name}")
        resolved[name] = found
    return resolved


def polygon_min_y(polygon: List[float]) -> float:
    ys = polygon[1::2]
    return min(ys) if ys else 0.0


def element_top(item) -> float:
    regions = getattr(item, "bounding_regions", None)
    if not regions:
        return 0.0
    poly = regions[0].polygon or []
    return polygon_min_y(poly)


def build_table_html(table) -> str:
    # Build table grid
    rows = max((cell.row_index for cell in table.cells), default=-1) + 1
    cols = max((cell.column_index for cell in table.cells), default=-1) + 1
    grid = [[{"content": "", "is_header": False} for _ in range(cols)] for _ in range(rows)]
    for cell in table.cells:
        r, c = cell.row_index, cell.column_index
        grid[r][c] = {
            "content": cell.content or "",
            "is_header": cell.kind == "columnHeader",
        }
    # Determine header rows
    header_rows = set()
    for r in range(rows):
        if any(grid[r][c]["is_header"] for c in range(cols)):
            header_rows.add(r)
    parts: List[str] = ["<table>"]
    if header_rows:
        parts.append("<thead>")
        for r in range(rows):
            if r in header_rows:
                parts.append("<tr>")
                for c in range(cols):
                    parts.append(f"<th>{grid[r][c]['content']}</th>")
                parts.append("</tr>")
        parts.append("</thead>")
    parts.append("<tbody>")
    for r in range(rows):
        if r in header_rows:
            continue
        parts.append("<tr>")
        for c in range(cols):
            parts.append(f"<td>{grid[r][c]['content']}</td>")
        parts.append("</tr>")
    parts.append("</tbody>")
    parts.append("</table>")
    return "".join(parts)


def paragraph_tag(text: str, role: Optional[str]) -> str:
    if role == "pageHeader":
        return f"<p class=\"{RUNNING_HEAD_CLASS}\">{text}</p>"
    if role == "pageFooter":
        if text.strip().isdigit():
            return f"<p class=\"{PAGE_NUMBER_CLASS}\">{text}</p>"
        return f"<p>{text}</p>"
    if role in {"title", "sectionHeading"}:
        return f"<h2>{text}</h2>"
    return f"<p>{text}</p>"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="prebuilt-layout")
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    load_dotenv(Path(".env"))
    endpoint = os.environ.get("AZURE_DOCUMENT_ENDPOINT")
    key = os.environ.get("AZURE_DOCUMENT_KEY")
    if not endpoint or not key:
        raise SystemExit("Missing AZURE_DOCUMENT_ENDPOINT or AZURE_DOCUMENT_KEY")

    pages = [
        "page-004L.png",
        "page-007R.png",
        "page-009L.png",
        "page-011.jpg",
        "page-017L.png",
        "page-017R.png",
        "page-019R.png",
        "page-020R.png",
        "page-026L.png",
        "page-035R.png",
        "page-054R.png",
    ]

    resolved = find_images(pages)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    usage_path = out_dir / "azure_usage.jsonl"

    client = DocumentIntelligenceClient(endpoint, AzureKeyCredential(key))

    for name, path in resolved.items():
        out_path = out_dir / f"{Path(name).stem}.html"
        if out_path.exists():
            continue
        print(f"Azure DI: {name}")
        with open(path, "rb") as f:
            poller = client.begin_analyze_document(
                model_id=args.model,
                body=f,
            )
        result = poller.result()

        items: List[Tuple[float, str]] = []
        # paragraphs
        if result.paragraphs:
            for p in result.paragraphs:
                text = (p.content or "").strip()
                if not text:
                    continue
                items.append((element_top(p), paragraph_tag(text, p.role)))
        # tables
        if result.tables:
            for t in result.tables:
                items.append((element_top(t), build_table_html(t)))

        items.sort(key=lambda x: x[0])
        html = "".join([it[1] for it in items])
        cleaned = sanitize_html(html)
        out_path.write_text(cleaned, encoding="utf-8")

        row = {
            "page": name,
            "model": args.model,
            "content_length": len(cleaned),
        }
        with open(usage_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
