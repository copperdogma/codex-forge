import json
from pathlib import Path

from modules.adapter.detect_duplicate_pages_v1.main import _similarity, _tokenize, _build_page_text


def test_similarity_basic():
    a = _tokenize("the quick brown fox jumps over the lazy dog")
    b = _tokenize("the quick brown fox jumps over the lazy dog")
    assert _similarity(a, b, "the quick brown fox jumps over the lazy dog", "the quick brown fox jumps over the lazy dog") == 1.0


def test_detect_duplicate_pages_smoke(tmp_path: Path):
    pages = [
        {
            "schema_version": "page_html_v1",
            "page_number": 1,
            "original_page_number": 1,
            "html": "<p>Alpha beta gamma delta.</p><p>Some extra text.</p>",
        },
        {
            "schema_version": "page_html_v1",
            "page_number": 2,
            "original_page_number": 2,
            "html": "<p>Alpha beta gamma delta.</p><p>Some extra text.</p>",
        },
        {
            "schema_version": "page_html_v1",
            "page_number": 3,
            "original_page_number": 3,
            "html": "<p>Completely different content here.</p>",
        },
    ]
    # Verify text normalization does not drop real content.
    assert "alpha beta" in _build_page_text(pages[0])

    in_path = tmp_path / "pages.jsonl"
    with in_path.open("w", encoding="utf-8") as f:
        for row in pages:
            f.write(json.dumps(row) + "\n")

    out_path = tmp_path / "pages_dedup.jsonl"
    report_path = tmp_path / "duplicate_pages.json"

    from modules.adapter.detect_duplicate_pages_v1.main import main as run
    import sys

    argv = [
        "detect_duplicate_pages_v1",
        "--pages",
        str(in_path),
        "--out",
        str(out_path),
        "--report-out",
        str(report_path),
        "--similarity-threshold",
        "0.9",
        "--min-tokens",
        "2",
        "--max-lookback",
        "2",
        "--max-page-gap",
        "2",
    ]
    old_argv = sys.argv
    sys.argv = argv
    try:
        run()
    finally:
        sys.argv = old_argv

    lines = out_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["duplicate_pages"] == 1
