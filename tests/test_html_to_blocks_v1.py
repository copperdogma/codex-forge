import json
from pathlib import Path

from modules.adapter.html_to_blocks_v1.main import parse_blocks


FIXTURE_DIR = Path("testdata/html-blocks-fixtures")


def _load_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_html_to_blocks_fixtures():
    pages = _load_jsonl(FIXTURE_DIR / "pages_html.jsonl")
    expected = _load_jsonl(FIXTURE_DIR / "page_blocks.expected.jsonl")
    assert len(pages) == len(expected)

    for page, exp in zip(pages, expected):
        blocks = parse_blocks(page.get("html") or "", drop_empty=True)
        is_blank = len(blocks) == 0

        assert is_blank == exp["is_blank"]
        assert blocks == exp["blocks"]
