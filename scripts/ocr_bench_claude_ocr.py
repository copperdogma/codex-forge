#!/usr/bin/env python3
"""Run Claude vision OCR on benchmark pages, enforce minimal HTML output."""
import argparse
import base64
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import List, Optional

import anthropic


ALLOWED_TAGS = {
    "h1", "h2", "p", "strong", "em", "ol", "ul", "li",
    "table", "thead", "tbody", "tr", "th", "td", "caption",
    "img", "dl", "dt", "dd",
}

RUNNING_HEAD_CLASS = "running-head"
PAGE_NUMBER_CLASS = "page-number"

SYSTEM_PROMPT = """You are an OCR engine for scanned book pages.\n\nReturn ONLY minimal HTML that preserves text and basic structure.\n\nAllowed tags (only):\n- Structural: <h1>, <h2>, <p>, <dl>, <dt>, <dd>\n- Emphasis: <strong>, <em>\n- Lists: <ol>, <ul>, <li>\n- Tables: <table>, <thead>, <tbody>, <tr>, <th>, <td>, <caption>\n- Running head / page number: <p class=\"running-head\">, <p class=\"page-number\">\n- Images: <img alt=\"...\"> (placeholder only, no src)\n\nRules:\n- Preserve exact wording, punctuation, and numbers.\n- Reflow paragraphs (no hard line breaks within a paragraph).\n- Keep running heads and page numbers if present (use the classed <p> tags above).\n- Use <h2> for section numbers when they are clearly section headers.\n- Use <h1> only for true page titles/headings.\n- Use <dl> with <dt>/<dd> for inline label/value blocks (e.g., creature name + SKILL/STAMINA).\n- Do not invent <section>, <div>, or <span>.\n- Use <img alt=\"...\"> when an illustration appears (short, factual description).\n- Tables must be represented as a single <table> with headers/rows (no splitting).\n- If uncertain, default to <p> with plain text.\n\nOutput ONLY HTML, no Markdown, no code fences, no extra commentary."""


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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="claude-3-5-sonnet-latest")
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
    usage_path = out_dir / "claude_usage.jsonl"

    import os
    api_key = os.environ.get("ANTHROPIC_CODEX_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit("Missing ANTHROPIC_CODEX_API_KEY or ANTHROPIC_API_KEY in environment.")
    client = anthropic.Anthropic(api_key=api_key)

    for name, path in resolved.items():
        out_path = out_dir / f"{Path(name).stem}.html"
        if out_path.exists():
            continue
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        media_type = "image/jpeg" if path.suffix.lower() in {".jpg", ".jpeg"} else "image/png"

        print(f"Claude OCR: {name}")
        msg = client.messages.create(
            model=args.model,
            max_tokens=4096,
            temperature=0,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
                        {"type": "text", "text": "Return HTML only."},
                    ],
                }
            ],
        )
        raw = msg.content[0].text if msg.content else ""
        cleaned = sanitize_html(raw)
        out_path.write_text(cleaned, encoding="utf-8")

        usage = getattr(msg, "usage", None)
        row = {
            "page": name,
            "model": args.model,
            "id": getattr(msg, "id", None),
            "usage": usage.model_dump() if usage else None,
        }
        with open(usage_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
