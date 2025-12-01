import json
import tempfile
import sys
from pathlib import Path

from modules.adapter.missing_header_resolver_v1.main import main as resolver_main
from modules.common.utils import save_json, save_jsonl, read_jsonl


def make_headers(path):
    # only section 1 present
    save_jsonl(path, [{"portion_id": "1", "page_start": 1, "page_end": 1}])


def make_index_quality(index_path, quality_path, images_dir):
    pages = {"1": str(Path(images_dir) / "page-001.json")}
    save_json(index_path, pages)
    save_json(quality_path, [])
    # minimal page file
    Path(images_dir).mkdir(parents=True, exist_ok=True)
    save_json(Path(images_dir) / "page-001.json", {"page": 1, "image": "dummy", "lines": []})


def test_resolver_dry_run_no_candidates():
    with tempfile.TemporaryDirectory() as d:
        headers = Path(d) / "hdr.jsonl"
        make_headers(headers)
        index = Path(d) / "idx.json"
        quality = Path(d) / "qual.json"
        images = Path(d) / "images"
        make_index_quality(index, quality, images)
        outdir = Path(d) / "out"
        outdir.mkdir()
        sys.argv = [
            "prog",
            "--headers",
            str(headers),
            "--pagelines-index",
            str(index),
            "--quality",
            str(quality),
            "--images-dir",
            str(images),
            "--outdir",
            str(outdir),
            "--dry-run",
        ]
        resolver_main()
        report = json.load(open(outdir / "missing_header_report.json"))
        assert 169 in report["absent_marked"]


if __name__ == "__main__":
    test_resolver_dry_run_no_candidates()
    print("resolver tests passed")
