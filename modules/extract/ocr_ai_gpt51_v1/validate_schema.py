#!/usr/bin/env python3
import argparse
from html.parser import HTMLParser
from typing import List

from modules.common.utils import read_jsonl
from modules.extract.ocr_ai_gpt51_v1.main import ALLOWED_TAGS, RUNNING_HEAD_CLASS, PAGE_NUMBER_CLASS


class HtmlSchemaValidator(HTMLParser):
    def __init__(self):
        super().__init__()
        self.errors: List[str] = []

    def handle_starttag(self, tag, attrs):
        self._validate_tag(tag, attrs)

    def handle_startendtag(self, tag, attrs):
        self._validate_tag(tag, attrs)

    def _validate_tag(self, tag, attrs):
        tag = tag.lower()
        if tag not in ALLOWED_TAGS:
            self.errors.append(f"disallowed tag: {tag}")
            return

        attrs_dict = {k.lower(): v for k, v in attrs}

        if tag == "img":
            extra = [k for k in attrs_dict.keys() if k != "alt"]
            if extra:
                self.errors.append(f"img has extra attrs: {extra}")
            return

        if tag == "p":
            if not attrs_dict:
                return
            cls = attrs_dict.get("class")
            if cls not in (RUNNING_HEAD_CLASS, PAGE_NUMBER_CLASS):
                self.errors.append(f"p has invalid class: {cls}")
            extra = [k for k in attrs_dict.keys() if k != "class"]
            if extra:
                self.errors.append(f"p has extra attrs: {extra}")
            return

        if attrs_dict:
            self.errors.append(f"{tag} has unexpected attrs: {list(attrs_dict.keys())}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate OCR HTML output against allowed tag schema.")
    parser.add_argument("--pages", required=True, help="page_html_v1 JSONL path")
    args = parser.parse_args()

    total = 0
    error_pages = 0
    for row in read_jsonl(args.pages):
        total += 1
        html = row.get("html") or ""
        validator = HtmlSchemaValidator()
        validator.feed(html)
        if validator.errors:
            error_pages += 1
            page_num = row.get("page_number") or row.get("page")
            print(f"[ERROR] page {page_num}: {validator.errors}")

    if error_pages:
        raise SystemExit(f"Schema validation failed on {error_pages}/{total} pages")
    print(f"Schema validation OK: {total} pages")


if __name__ == "__main__":
    main()
