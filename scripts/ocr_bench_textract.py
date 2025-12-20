#!/usr/bin/env python3
"""Run AWS Textract DetectDocumentText on benchmark pages and map to minimal HTML."""
import argparse
import json
import os
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import List, Optional, Tuple

import boto3

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


def block_top(block: dict) -> float:
    geom = block.get("Geometry", {})
    bbox = geom.get("BoundingBox", {})
    return bbox.get("Top", 0.0)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--region", default=os.environ.get("AWS_REGION", "us-east-1"))
    args = parser.parse_args()

    load_dotenv(Path(".env"))

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
    usage_path = out_dir / "textract_usage.jsonl"

    client = boto3.client("textract", region_name=args.region)

    for name, path in resolved.items():
        out_path = out_dir / f"{Path(name).stem}.html"
        if out_path.exists():
            continue
        print(f"Textract: {name}")
        img_bytes = path.read_bytes()
        resp = client.detect_document_text(Document={"Bytes": img_bytes})

        blocks = resp.get("Blocks", [])
        lines = [b for b in blocks if b.get("BlockType") == "LINE" and b.get("Text")]
        # sort by top then left
        lines.sort(key=lambda b: (block_top(b), b.get("Geometry", {}).get("BoundingBox", {}).get("Left", 0.0)))

        parts = []
        for line in lines:
            text = line.get("Text", "").strip()
            if not text:
                continue
            parts.append(f"<p>{text}</p>")

        html = "".join(parts)
        cleaned = sanitize_html(html)
        out_path.write_text(cleaned, encoding="utf-8")

        row = {
            "page": name,
            "region": args.region,
            "request_id": resp.get("ResponseMetadata", {}).get("RequestId"),
            "status_code": resp.get("ResponseMetadata", {}).get("HTTPStatusCode"),
        }
        with open(usage_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
