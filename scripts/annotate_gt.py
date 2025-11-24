"""Generate or update ground-truth box JSONL for eval pages.

Each record:
{"page": 1, "image": "img-000.jpg", "width": 1350, "height": 1069, "boxes": [{"x0":0,"y0":0,"x1":100,"y1":100,"section_id":null}]}

Usage examples:
python scripts/annotate_gt.py --out configs/groundtruth/image_boxes_eval.jsonl
python scripts/annotate_gt.py --out configs/groundtruth/image_boxes_eval.jsonl --overlay-dir output/annotations_preview
"""

import argparse
import json
import os
from pathlib import Path
from typing import List, Dict, Any

from PIL import Image, ImageDraw


DEFAULT_PAGES = [
    (1, "img-000.jpg"),
    (3, "img-008.jpg"),
    (11, "img-023.jpg"),
    (14, "img-034.jpg"),
    (17, "img-038.jpg"),
    (18, "img-040.jpg"),
    (63, "img-208.jpg"),
]


def read_existing(path: Path) -> Dict[int, Dict[str, Any]]:
    """Return existing records keyed by page number."""
    if not path.exists():
        return {}
    data = {}
    with path.open() as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            data[int(rec["page"])] = rec
    return data


def load_image_meta(image_root: Path, image_name: str) -> Dict[str, int]:
    path = image_root / image_name
    with Image.open(path) as im:
        width, height = im.size
    return {"width": width, "height": height}


def write_jsonl(path: Path, records: List[Dict[str, Any]]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=True) + "\n")


def render_overlays(image_root: Path, overlay_dir: Path, records: List[Dict[str, Any]]):
    overlay_dir.mkdir(parents=True, exist_ok=True)
    for rec in records:
        boxes = rec.get("boxes", [])
        if not boxes:
            continue
        src = image_root / rec["image"]
        if not src.exists():
            continue
        with Image.open(src).convert("RGB") as im:
            draw = ImageDraw.Draw(im)
            for box in boxes:
                xy = [box["x0"], box["y0"], box["x1"], box["y1"]]
                draw.rectangle(xy, outline="red", width=4)
                label = str(box.get("section_id", ""))
                if label:
                    draw.text((box["x0"] + 4, box["y0"] + 4), label, fill="red")
            out_path = overlay_dir / f"overlay-{rec['page']:03d}.jpg"
            im.save(out_path, quality=95)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image-root", default="input/images", help="Directory holding page images")
    parser.add_argument(
        "--pages",
        nargs="*",
        default=[f"{p}:{img}" for p, img in DEFAULT_PAGES],
        help="Pages as page:image_name (default: eval set)",
    )
    parser.add_argument("--out", default="configs/groundtruth/image_boxes_eval.jsonl", help="Output JSONL path")
    parser.add_argument("--overlay-dir", default=None, help="Optional directory to render overlays if boxes present")
    parser.add_argument("--preserve-boxes", action="store_true", help="Keep existing boxes if record already exists")
    args = parser.parse_args()

    image_root = Path(args.image_root)
    out_path = Path(args.out)
    existing = read_existing(out_path) if args.preserve_boxes else {}

    records = []
    for item in args.pages:
        try:
            page_str, image_name = item.split(":", 1)
            page = int(page_str)
        except ValueError:
            raise SystemExit(f"Invalid page spec: {item}. Use page:image_name")

        meta = load_image_meta(image_root, image_name)
        rec = existing.get(page, {})
        boxes = rec.get("boxes", []) if args.preserve_boxes else []
        records.append(
            {
                "page": page,
                "image": image_name,
                "width": meta["width"],
                "height": meta["height"],
                "boxes": boxes,
            }
        )

    records.sort(key=lambda r: r["page"])
    write_jsonl(out_path, records)

    if args.overlay_dir:
        render_overlays(image_root, Path(args.overlay_dir), records)


if __name__ == "__main__":
    main()
