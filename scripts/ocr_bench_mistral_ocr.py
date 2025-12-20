#!/usr/bin/env python3
"""Run Mistral OCR on benchmark pages, convert Markdown to HTML, sanitize tags."""
import argparse
import base64
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import List, Optional

import markdown
from mistralai import Mistral


ALLOWED_TAGS = {
    "h1", "h2", "p", "strong", "em", "ol", "ul", "li",
    "table", "thead", "tbody", "tr", "th", "td", "caption",
    "img", "dl", "dt", "dd",
}

RUNNING_HEAD_CLASS = "running-head"
PAGE_NUMBER_CLASS = "page-number"


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
            # keep running head/page number classes if present
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
        # Add line breaks between tags for readability
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="mistral-ocr-latest")
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

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
    usage_path = out_dir / "mistral_ocr_usage.jsonl"

    import os
    client = Mistral(api_key=os.environ.get("MISTRAL_API_KEY"))

    for name, path in resolved.items():
        out_path = out_dir / f"{Path(name).stem}.html"
        if out_path.exists():
            continue
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        mime = "image/jpeg" if path.suffix.lower() in {".jpg", ".jpeg"} else "image/png"
        doc = {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}
        print(f"Mistral OCR: {name}")
        resp = client.ocr.process(
            model=args.model,
            document=doc,
            table_format="html",
            extract_header=True,
            extract_footer=True,
        )
        # Use markdown from first page and inline table HTML
        markdown_text = resp.pages[0].markdown if resp.pages else ""
        if resp.pages and resp.pages[0].tables:
            for table in resp.pages[0].tables:
                table_id = table.id
                content = table.content or ""
                # Replace markdown links like [tbl-0.html](tbl-0.html) with inline HTML table
                markdown_text = markdown_text.replace(f"[{table_id}]({table_id})", content)
        html = markdown.markdown(markdown_text, extensions=["tables"])
        cleaned = sanitize_html(html)
        out_path.write_text(cleaned, encoding="utf-8")

        usage = getattr(resp, "usage", None)
        row = {
            "page": name,
            "model": args.model,
            "pages_processed": getattr(usage, "pages_processed", None),
            "doc_size_bytes": getattr(usage, "doc_size_bytes", None),
        }
        with open(usage_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print("done")
    return 0


if __name__ == "__main__":
    import json
    raise SystemExit(main())
