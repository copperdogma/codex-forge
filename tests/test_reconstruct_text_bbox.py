import sys
import tempfile
from pathlib import Path

from modules.adapter.reconstruct_text_v1.main import main as rt_main


def test_reconstruct_text_merges_bbox_union():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        inp = d / "pagelines_final.jsonl"
        out = d / "pagelines_reconstructed.jsonl"

        page = {
            "schema_version": "pagelines_v1",
            "module_id": "test",
            "page": 1,
            "image": "page-001.png",
            "lines": [
                {"text": "Hello", "source": "tesseract", "bbox": [0.1, 0.2, 0.3, 0.25]},
                {"text": "world.", "source": "tesseract", "bbox": [0.1, 0.26, 0.35, 0.31]},
            ],
        }

        inp.write_text(f"{__import__('json').dumps(page)}\n", encoding="utf-8")
        sys.argv = ["prog", "--input", str(inp), "--out", str(out)]
        rt_main()

        rows = out.read_text(encoding="utf-8").strip().splitlines()
        assert len(rows) == 1
        data = __import__("json").loads(rows[0])
        assert len(data["lines"]) == 1
        merged = data["lines"][0]
        assert merged["text"].startswith("Hello")
        assert merged.get("bbox") == [0.1, 0.2, 0.35, 0.31]

