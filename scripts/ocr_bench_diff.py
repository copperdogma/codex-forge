#!/usr/bin/env python3
"""OCR benchmark diff: compare model HTML output vs gold HTML and gold text-only."""
import argparse
import json
import re
import sys
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from difflib import SequenceMatcher, unified_diff
from typing import Dict, List, Tuple


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: List[str] = []
        self._in_td = False
        self._in_th = False

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"p", "h1", "h2", "li", "tr", "dt", "dd", "caption"}:
            self.parts.append("\n")
        if tag == "td":
            self._in_td = True
        if tag == "th":
            self._in_th = True
        if tag == "img":
            # represent images as a newline marker with alt if present
            alt = ""
            for k, v in attrs:
                if k == "alt":
                    alt = v or ""
                    break
            if alt:
                self.parts.append(f"\n[image: {alt}]\n")
            else:
                self.parts.append("\n[image]\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"p", "h1", "h2", "li", "tr", "dt", "dd", "caption"}:
            self.parts.append("\n")
        if tag == "td":
            self._in_td = False
            self.parts.append("\t")
        if tag == "th":
            self._in_th = False
            self.parts.append("\t")

    def handle_data(self, data: str) -> None:
        if data:
            self.parts.append(data)

    def get_text(self) -> str:
        return "".join(self.parts)


class _HtmlNormalizer(HTMLParser):
    def __init__(self):
        super().__init__()
        self.lines: List[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        attrs = [(k.lower(), v) for k, v in attrs if v is not None]
        attrs.sort(key=lambda x: x[0])
        if attrs:
            attr_str = " " + " ".join(f'{k}="{v}"' for k, v in attrs)
        else:
            attr_str = ""
        self.lines.append(f"<{tag}{attr_str}>")

    def handle_endtag(self, tag: str) -> None:
        self.lines.append(f"</{tag.lower()}>")

    def handle_data(self, data: str) -> None:
        text = re.sub(r"\s+", " ", data).strip()
        if text:
            self.lines.append(text)

    def handle_startendtag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        attrs = [(k.lower(), v) for k, v in attrs if v is not None]
        attrs.sort(key=lambda x: x[0])
        if attrs:
            attr_str = " " + " ".join(f'{k}="{v}"' for k, v in attrs)
        else:
            attr_str = ""
        self.lines.append(f"<{tag}{attr_str} />")

    def get_normalized(self) -> str:
        return "\n".join(self.lines).strip()


def html_to_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    text = parser.get_text()
    # Normalize whitespace but preserve newlines as line boundaries
    text = text.replace("\r", "")
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.split("\n")]
    lines = [line for line in lines if line]
    return "\n".join(lines).strip()


def normalize_html(html: str) -> str:
    parser = _HtmlNormalizer()
    parser.feed(html)
    return parser.get_normalized()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(a=a, b=b).ratio()


@dataclass
class PageResult:
    page: str
    html_ratio: float
    text_ratio: float
    html_diff_lines: int
    text_diff_lines: int


def write_diff(a: str, b: str, a_name: str, b_name: str, out_path: Path) -> int:
    a_lines = a.splitlines(keepends=True)
    b_lines = b.splitlines(keepends=True)
    diff = list(unified_diff(a_lines, b_lines, fromfile=a_name, tofile=b_name))
    out_path.write_text("".join(diff), encoding="utf-8")
    return len(diff)


def build_gold_text(gold_dir: Path, gold_text_dir: Path) -> None:
    gold_text_dir.mkdir(parents=True, exist_ok=True)
    for html_path in gold_dir.glob("*.html"):
        text = html_to_text(read_text(html_path))
        out_path = gold_text_dir / f"{html_path.stem}.txt"
        out_path.write_text(text + "\n", encoding="utf-8")


def compare(gold_dir: Path, gold_text_dir: Path, model_dir: Path, out_dir: Path) -> Dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    results: List[PageResult] = []

    for html_path in sorted(gold_dir.glob("*.html")):
        name = html_path.name
        model_path = model_dir / name
        if not model_path.exists():
            continue

        gold_html = read_text(html_path)
        model_html = read_text(model_path)
        gold_html_norm = normalize_html(gold_html)
        model_html_norm = normalize_html(model_html)

        gold_text_path = gold_text_dir / f"{html_path.stem}.txt"
        gold_text = read_text(gold_text_path) if gold_text_path.exists() else html_to_text(gold_html) + "\n"
        model_text = html_to_text(model_html) + "\n"

        html_ratio = similarity(gold_html_norm, model_html_norm)
        text_ratio = similarity(gold_text, model_text)

        html_diff = write_diff(gold_html_norm, model_html_norm, f"gold/{name}", f"model/{name}", out_dir / f"{html_path.stem}.html.diff")
        text_diff = write_diff(gold_text, model_text, f"gold/{html_path.stem}.txt", f"model/{html_path.stem}.txt", out_dir / f"{html_path.stem}.text.diff")

        results.append(PageResult(
            page=html_path.stem,
            html_ratio=round(html_ratio, 6),
            text_ratio=round(text_ratio, 6),
            html_diff_lines=html_diff,
            text_diff_lines=text_diff,
        ))

    summary = {
        "pages": len(results),
        "avg_html_ratio": round(sum(r.html_ratio for r in results) / len(results), 6) if results else 0,
        "avg_text_ratio": round(sum(r.text_ratio for r in results) / len(results), 6) if results else 0,
        "results": [r.__dict__ for r in results],
    }
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="OCR benchmark diff (HTML + text-only).")
    parser.add_argument("--gold-dir", required=True)
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--gold-text-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--regen-gold-text", action="store_true")
    args = parser.parse_args()

    gold_dir = Path(args.gold_dir)
    model_dir = Path(args.model_dir)
    gold_text_dir = Path(args.gold_text_dir)
    out_dir = Path(args.out_dir)

    if args.regen_gold_text or not gold_text_dir.exists():
        build_gold_text(gold_dir, gold_text_dir)

    summary = compare(gold_dir, gold_text_dir, model_dir, out_dir)
    summary_path = out_dir / "diff_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
