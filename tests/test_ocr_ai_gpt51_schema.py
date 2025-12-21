from html.parser import HTMLParser
from pathlib import Path

from modules.extract.ocr_ai_gpt51_v1.main import ALLOWED_TAGS, RUNNING_HEAD_CLASS, PAGE_NUMBER_CLASS


class HtmlSchemaValidator(HTMLParser):
    def __init__(self):
        super().__init__()
        self.errors = []

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
            # only allow alt (may be empty)
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


def test_gold_html_conforms_to_schema():
    base = Path("testdata/ocr-gold/ai-ocr-simplification")
    files = sorted(base.glob("*.html"))
    assert files, "no gold HTML fixtures found"

    for path in files:
        parser = HtmlSchemaValidator()
        parser.feed(path.read_text(encoding="utf-8"))
        assert not parser.errors, f"{path}: {parser.errors}"
