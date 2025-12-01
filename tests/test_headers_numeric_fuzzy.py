import json
import tempfile
from modules.portionize.portionize_headers_numeric_v1.main import clean_lines, main as num_main
from modules.common.utils import save_jsonl, read_jsonl
import argparse
import sys
from pathlib import Path


def run_numeric(pages_text):
    with tempfile.TemporaryDirectory() as d:
        pages_path = Path(d) / "pages.jsonl"
        out_path = Path(d) / "out.jsonl"
        rows = []
        for i, text in enumerate(pages_text, start=1):
            rows.append({"page": i, "clean_text": text})
        save_jsonl(pages_path, rows)
        sys.argv = ["prog", "--pages", str(pages_path), "--out", str(out_path)]
        num_main()
        return list(read_jsonl(out_path))


def test_fused_numbers_detected():
    rows = run_numeric([
        "271 Some text\n272Text fused\n273 more",
    ])
    ids = {int(r['portion_id']) for r in rows}
    assert 272 in ids
    assert 271 in ids


def test_fuzzy_digits_detected():
    rows = run_numeric([
        "305.. trailing",  # fuzzy match digits then non-digit
    ])
    ids = {int(r['portion_id']) for r in rows}
    assert 305 in ids


if __name__ == "__main__":
    # allow running directly
    test_fused_numbers_detected()
    test_fuzzy_digits_detected()
    print("tests passed")
