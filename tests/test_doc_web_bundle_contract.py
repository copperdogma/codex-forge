import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from schemas import (
    ChapterHtmlManifestEntry,
    DocWebBundleManifest,
    DocWebProvenanceBlock,
)
from validate_artifact import SCHEMA_MAP


REPO_ROOT = Path(__file__).resolve().parents[1]
GOLDEN_DIR = (
    REPO_ROOT
    / "benchmarks"
    / "golden"
    / "onward"
    / "reviewed_html_slice"
    / "story149-onward-build-regression-r1"
)
VALIDATOR = REPO_ROOT / "validate_artifact.py"


DOC_WEB_BUNDLE_MANIFEST_EXAMPLE = {
    "schema_version": "doc_web_bundle_manifest_v1",
    "document_id": "onward-to-the-unknown",
    "title": "Onward to the Unknown",
    "creator": "",
    "source_artifact": "input/onward-to-the-unknown-images",
    "index_path": "index.html",
    "entries": [
        {
            "entry_id": "chapter-010",
            "kind": "chapter",
            "title": "ARTHUR L'HEUREUX",
            "path": "chapter-010.html",
            "order": 1,
            "next_entry_id": "chapter-011",
            "source_pages": [28, 29, 30, 31, 32, 33, 34, 35, 36, 37],
            "printed_pages": [19, 20, 21, 22, 23, 24, 25, 26, 27, 28],
        },
        {
            "entry_id": "chapter-011",
            "kind": "chapter",
            "title": "LEONIDAS L'HEUREUX",
            "path": "chapter-011.html",
            "order": 2,
            "prev_entry_id": "chapter-010",
            "source_pages": [38, 39, 40, 41, 42, 43, 44, 45, 46, 47],
            "printed_pages": [29, 30, 31, 32, 33, 34, 35, 36, 37, 38],
        },
    ],
    "reading_order": ["chapter-010", "chapter-011"],
    "asset_roots": ["images"],
    "provenance_path": "provenance/blocks.jsonl",
}


DOC_WEB_PROVENANCE_BLOCK_EXAMPLE = [
    {
        "schema_version": "doc_web_provenance_block_v1",
        "block_id": "blk-chapter-010-0001",
        "entry_id": "chapter-010",
        "block_kind": "paragraph",
        "source_page_number": 28,
        "source_printed_page_number": 19,
        "source_element_ids": ["p028-b1"],
        "text_quote": "Although weddings are meant to be happy occasions...",
    },
    {
        "schema_version": "doc_web_provenance_block_v1",
        "block_id": "blk-chapter-010-0002",
        "entry_id": "chapter-010",
        "block_kind": "figure",
        "source_page_number": 28,
        "source_printed_page_number": 19,
        "source_element_ids": ["p028-b2"],
        "confidence": 0.94,
    },
]


def _load_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def test_chapter_html_manifest_schema_validates_committed_golden_slice():
    rows = _load_jsonl(GOLDEN_DIR / "chapters_manifest_regression.jsonl")

    parsed = [ChapterHtmlManifestEntry(**row) for row in rows]

    assert len(parsed) == 33
    assert sum(1 for row in parsed if row.kind == "chapter") == 24
    assert sum(1 for row in parsed if row.kind == "page") == 9
    assert parsed[9].title == "The Ancestral Lineage of Moïse and Sophie"


def test_doc_web_bundle_manifest_roundtrip_via_schema_map():
    model_cls = SCHEMA_MAP["doc_web_bundle_manifest_v1"]
    manifest = model_cls(**DOC_WEB_BUNDLE_MANIFEST_EXAMPLE)

    assert isinstance(manifest, DocWebBundleManifest)
    assert manifest.reading_order == ["chapter-010", "chapter-011"]
    assert manifest.entries[0].path == "chapter-010.html"
    assert manifest.entries[0].printed_page_start == 19
    assert manifest.provenance_path == "provenance/blocks.jsonl"


def test_doc_web_bundle_manifest_rejects_non_bundle_local_paths():
    manifest_data = deepcopy(DOC_WEB_BUNDLE_MANIFEST_EXAMPLE)
    manifest_data["index_path"] = "/abs/index.html"
    manifest_data["entries"][0]["path"] = "/abs/chapter-010.html"
    manifest_data["provenance_path"] = "/abs/blocks.jsonl"

    with pytest.raises(ValueError):
        DocWebBundleManifest(**manifest_data)


def test_doc_web_bundle_manifest_rejects_non_contiguous_order():
    manifest_data = deepcopy(DOC_WEB_BUNDLE_MANIFEST_EXAMPLE)
    manifest_data["entries"][0]["order"] = 2
    manifest_data["entries"][1]["order"] = 3

    with pytest.raises(ValueError):
        DocWebBundleManifest(**manifest_data)


def test_doc_web_bundle_manifest_rejects_navigation_that_disagrees_with_reading_order():
    manifest_data = deepcopy(DOC_WEB_BUNDLE_MANIFEST_EXAMPLE)
    manifest_data["entries"][1]["next_entry_id"] = "chapter-010"

    with pytest.raises(ValueError):
        DocWebBundleManifest(**manifest_data)


def test_doc_web_provenance_blocks_roundtrip_via_schema_map():
    model_cls = SCHEMA_MAP["doc_web_provenance_block_v1"]
    blocks = [model_cls(**row) for row in DOC_WEB_PROVENANCE_BLOCK_EXAMPLE]

    assert all(isinstance(block, DocWebProvenanceBlock) for block in blocks)
    assert blocks[0].block_id == "blk-chapter-010-0001"
    assert blocks[1].confidence == pytest.approx(0.94)


def test_doc_web_provenance_rejects_invalid_block_id():
    with pytest.raises(ValueError):
        DocWebProvenanceBlock(
            block_id="chapter-010-0001",
            entry_id="chapter-010",
            block_kind="paragraph",
            source_page_number=28,
            source_element_ids=["p028-b1"],
        )


def test_validate_artifact_cli_accepts_json_manifest(tmp_path: Path):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(DOC_WEB_BUNDLE_MANIFEST_EXAMPLE, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    proc = subprocess.run(
        [sys.executable, str(VALIDATOR), "--schema", "doc_web_bundle_manifest_v1", "--file", str(manifest_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    assert proc.returncode == 0, proc.stdout
    assert "Validation OK" in proc.stdout


def test_validate_artifact_cli_rejects_invalid_json_manifest(tmp_path: Path):
    manifest_path = tmp_path / "invalid-manifest.json"
    invalid_manifest = deepcopy(DOC_WEB_BUNDLE_MANIFEST_EXAMPLE)
    invalid_manifest["entries"][1]["next_entry_id"] = "chapter-010"
    manifest_path.write_text(
        json.dumps(invalid_manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    proc = subprocess.run(
        [sys.executable, str(VALIDATOR), "--schema", "doc_web_bundle_manifest_v1", "--file", str(manifest_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    assert proc.returncode == 1, proc.stdout
    assert "Validation finished with 1 errors out of 1 rows." in proc.stdout


def test_validate_artifact_cli_accepts_jsonl_provenance_blocks(tmp_path: Path):
    blocks_path = tmp_path / "blocks.jsonl"
    with blocks_path.open("w", encoding="utf-8") as f:
        for row in DOC_WEB_PROVENANCE_BLOCK_EXAMPLE:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    proc = subprocess.run(
        [sys.executable, str(VALIDATOR), "--schema", "doc_web_provenance_block_v1", "--file", str(blocks_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    assert proc.returncode == 0, proc.stdout
    assert "Validation OK" in proc.stdout
