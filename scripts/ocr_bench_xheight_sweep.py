#!/usr/bin/env python3
"""Run OCR bench across x-height targets for old + pristine PDFs."""
import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Tuple, List, Optional

from pdf2image import convert_from_path

from modules.extract.extract_pdf_images_capped_v1.main import (
    _estimate_line_height_px,
    _sample_pages,
    _page_max_image_dpi,
    _choose_target_dpi,
)


OLD_PDF = "input/06 deathtrap dungeon.pdf"
PRISTINE_PDF = "input/deathtrapdungeon00ian_jn9_1 - from internet archive.pdf"

# Benchmark pages (intersection across editions; excludes page-004L and adventure sheet)
OLD_MAPPING: Dict[str, Tuple[int, str]] = {
    "page-007R.png": (7, "R"),
    "page-009L.png": (9, "L"),
    "page-017L.png": (17, "L"),
    "page-017R.png": (17, "R"),
    "page-019R.png": (19, "R"),
    "page-020R.png": (20, "R"),
    "page-026L.png": (26, "L"),
    "page-035R.png": (35, "R"),
    "page-054R.png": (54, "R"),
}

PRISTINE_MAPPING: Dict[str, int] = {
    "page-007R.png": 13,
    "page-009L.png": 16,
    "page-017L.png": 32,
    "page-017R.png": 33,
    "page-019R.png": 37,
    "page-020R.png": 39,
    "page-026L.png": 50,
    "page-035R.png": 69,
    "page-054R.png": 107,
}

OCR_HINTS = """- This book uses either running heads OR page numbers, not both on the same page.
- In gameplay pages, section numbers are centered standalone digits (1–3 digits) and should be <h2>.
- Do not treat running heads (e.g., \"16-17\") as section headers.
"""


def compute_line_heights(pdf_path: str, baseline_dpi: int, sample_count: int) -> Tuple[List[int], List[float]]:
    from pypdf import PdfReader
    reader = PdfReader(pdf_path)
    total_pages = len(reader.pages)
    sampled_pages = _sample_pages(total_pages, sample_count)
    line_heights: List[float] = []
    for page_idx in sampled_pages:
        page_obj = reader.pages[page_idx - 1]
        max_source_dpi = _page_max_image_dpi(page_obj)
        sample_dpi = min(baseline_dpi, int(max_source_dpi)) if max_source_dpi else baseline_dpi
        images = convert_from_path(pdf_path, dpi=sample_dpi, first_page=page_idx, last_page=page_idx)
        if not images:
            continue
        estimate = _estimate_line_height_px(images[0])
        if estimate:
            normalized = estimate * (float(baseline_dpi) / float(sample_dpi))
            line_heights.append(normalized)
    return sampled_pages, line_heights


def render_page(pdf_path: str, page_idx: int, render_dpi: float, out_path: Path) -> None:
    images = convert_from_path(pdf_path, dpi=render_dpi, first_page=page_idx, last_page=page_idx)
    if not images:
        raise RuntimeError(f"No image rendered for page {page_idx}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    images[0].save(out_path, "JPEG")


def split_old_pages(render_dir: Path, split_dir: Path) -> None:
    # Use split_pages_from_manifest_v1 for consistent behavior
    split_dir.mkdir(parents=True, exist_ok=True)
    manifest = split_dir / "pages_rendered_manifest.jsonl"
    with open(manifest, "w", encoding="utf-8") as f:
        for img in sorted(render_dir.glob("page-*.jpg")):
            page_num = int(img.stem.split("-")[-1])
            row = {
                "schema_version": "page_image_v1",
                "module_id": "extract_pdf_images_capped_v1",
                "run_id": None,
                "created_at": "",
                "page": page_num,
                "page_number": page_num,
                "original_page_number": page_num,
                "image": str(img.resolve()),
                "spread_side": None,
            }
            f.write(json.dumps(row) + "\n")
    subprocess.check_call([
        "python",
        "modules/extract/split_pages_from_manifest_v1/main.py",
        "--pages",
        str(manifest),
        "--outdir",
        str(split_dir),
    ])


def build_images_for_target(label: str, pdf_path: str, target_line_height: int,
                            baseline_dpi: int, min_dpi: int, sample_count: int,
                            output_root: Path) -> Dict[str, float]:
    from pypdf import PdfReader
    reader = PdfReader(pdf_path)
    sampled_pages, line_heights = compute_line_heights(pdf_path, baseline_dpi, sample_count)
    target_dpi = _choose_target_dpi(
        baseline_dpi=baseline_dpi,
        target_line_height=target_line_height,
        line_heights=line_heights,
        dpi_cap=None,
        min_dpi=min_dpi,
    )

    render_dir = output_root / "rendered"
    render_dir.mkdir(parents=True, exist_ok=True)

    if pdf_path == OLD_PDF:
        pages_needed = sorted({page for page, _ in OLD_MAPPING.values()})
        for page_idx in pages_needed:
            page_obj = reader.pages[page_idx - 1]
            max_source_dpi = _page_max_image_dpi(page_obj)
            render_dpi = min(target_dpi, float(max_source_dpi)) if max_source_dpi else target_dpi
            render_dpi = max(render_dpi, min_dpi)
            render_page(pdf_path, page_idx, render_dpi, render_dir / f"page-{page_idx:03d}.jpg")
        split_dir = output_root / "split"
        split_old_pages(render_dir, split_dir)
        images_root = output_root / "images"
        images_root.mkdir(parents=True, exist_ok=True)
        for name, (page_idx, side) in OLD_MAPPING.items():
            src = split_dir / "images" / f"page-{page_idx:03d}{side}.png"
            shutil.copyfile(src, images_root / name)
    else:
        images_root = output_root / "images"
        images_root.mkdir(parents=True, exist_ok=True)
        for name, page_idx in PRISTINE_MAPPING.items():
            page_obj = reader.pages[page_idx - 1]
            max_source_dpi = _page_max_image_dpi(page_obj)
            render_dpi = min(target_dpi, float(max_source_dpi)) if max_source_dpi else target_dpi
            render_dpi = max(render_dpi, min_dpi)
            render_page(pdf_path, page_idx, render_dpi, images_root / f"page-{page_idx:03d}.jpg")
            shutil.copyfile(images_root / f"page-{page_idx:03d}.jpg", images_root / name)

    return {
        "target_dpi": target_dpi,
        "sampled_pages": sampled_pages,
        "line_heights_px": line_heights,
    }


def run_ocr_bench(images_root: Path, out_dir: Path, model: str, ocr_hints: str) -> None:
    subprocess.check_call([
        "python",
        "scripts/ocr_bench_openai_ocr.py",
        "--model",
        model,
        "--out-dir",
        str(out_dir),
        "--images-root",
        str(images_root),
        "--ocr-hints",
        ocr_hints,
        "--force",
    ])


def run_diff(model_dir: Path, out_dir: Path) -> None:
    subprocess.check_call([
        "python",
        "scripts/ocr_bench_diff.py",
        "--gold-dir",
        "testdata/ocr-gold/ai-ocr-simplification",
        "--gold-text-dir",
        "testdata/ocr-gold/ai-ocr-simplification-text",
        "--model-dir",
        str(model_dir),
        "--out-dir",
        str(out_dir),
    ])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--targets", default="16,20,24,28", help="Comma-separated line-height targets")
    parser.add_argument("--baseline-dpi", type=int, default=72)
    parser.add_argument("--min-dpi", type=int, default=72)
    parser.add_argument("--sample-count", type=int, default=5)
    parser.add_argument("--model", default="gpt-5.1")
    parser.add_argument("--out-root", default="testdata/ocr-bench/xheight-sweep")
    args = parser.parse_args()

    targets = []
    for raw in args.targets.split(","):
        raw = raw.strip()
        if not raw:
            continue
        targets.append(int(raw))

    for label, pdf_path in ("old", OLD_PDF), ("pristine", PRISTINE_PDF):
        for target in targets:
            root = Path(args.out_root) / label / f"xh-{target}"
            root.mkdir(parents=True, exist_ok=True)
            images_root = root / "images"
            meta = build_images_for_target(
                label,
                pdf_path,
                target,
                args.baseline_dpi,
                args.min_dpi,
                args.sample_count,
                root,
            )
            meta_path = root / "render_meta.json"
            meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

            ocr_dir = root / "ocr"
            run_ocr_bench(images_root, ocr_dir, args.model, OCR_HINTS)

            diff_dir = root / "diffs"
            run_diff(ocr_dir, diff_dir)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
