#!/usr/bin/env python3
"""Run Qwen2.5-VL via Hugging Face Inference API (OpenAI-compatible) on benchmark pages."""
import argparse
import base64
import json
import os
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import List, Optional

import requests

ALLOWED_TAGS = {
    "h1", "h2", "p", "strong", "em", "ol", "ul", "li",
    "table", "thead", "tbody", "tr", "th", "td", "caption",
    "img", "dl", "dt", "dd",
}

RUNNING_HEAD_CLASS = "running-head"
PAGE_NUMBER_CLASS = "page-number"

SYSTEM_PROMPT = """You are an OCR engine for scanned book pages.\n\nReturn ONLY minimal HTML that preserves text and basic structure.\n\nAllowed tags (only):\n- Structural: <h1>, <h2>, <p>, <dl>, <dt>, <dd>\n- Emphasis: <strong>, <em>\n- Lists: <ol>, <ul>, <li>\n- Tables: <table>, <thead>, <tbody>, <tr>, <th>, <td>, <caption>\n- Running head / page number: <p class=\"running-head\">, <p class=\"page-number\">\n- Images: <img alt=\"...\"> (placeholder only, no src)\n\nRules:\n- Preserve exact wording, punctuation, and numbers.\n- Reflow paragraphs (no hard line breaks within a paragraph).\n- Keep running heads and page numbers if present (use the classed <p> tags above).\n- Use <h2> for section numbers when they are clearly section headers.\n- Use <h1> only for true page titles/headings.\n- Use <dl> with <dt>/<dd> for inline label/value blocks (e.g., creature name + SKILL/STAMINA).\n- Do not invent <section>, <div>, or <span>.\n- Use <img alt=\"...\"> when an illustration appears (short, factual description).\n- Tables must be represented as a single <table> with headers/rows (no splitting).\n- If uncertain, default to <p> with plain text.\n\nOutput ONLY HTML, no Markdown, no code fences, no extra commentary."""


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
            self.out.append(f"</{tag}>\n")

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
    parser.add_argument("--model", default="Qwen/Qwen2.5-VL-72B-Instruct")
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    load_dotenv(Path(".env"))
    token = os.environ.get("HF_TOKEN")
    if not token:
        raise SystemExit("Missing HF_TOKEN")

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
    usage_path = out_dir / "hf_usage.jsonl"

    url = "https://router.huggingface.co/v1/chat/completions"
    headers = {"Authorization": f"Bearer {token}"}

    for name, path in resolved.items():
        out_path = out_dir / f"{Path(name).stem}.html"
        if out_path.exists():
            continue
        mime = "image/jpeg" if path.suffix.lower() in {".jpg", ".jpeg"} else "image/png"
        b64 = base64.b64encode(path.read_bytes()).decode("utf-8")
        print(f"HF Qwen OCR: {name}")
        payload = {
            "model": args.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Return HTML only."},
                        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                    ],
                },
            ],
            "temperature": 0,
            "max_tokens": 4096,
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=120)
        if resp.status_code != 200:
            raise SystemExit(f"HF error {resp.status_code}: {resp.text}")
        data = resp.json()
        choice = data.get("choices", [{}])[0]
        raw = choice.get("message", {}).get("content", "")
        cleaned = sanitize_html(raw)
        out_path.write_text(cleaned, encoding="utf-8")
        row = {
            "page": name,
            "model": args.model,
            "request_id": data.get("id"),
            "usage": data.get("usage"),
        }
        with open(usage_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
