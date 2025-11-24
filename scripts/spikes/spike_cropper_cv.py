"""Heuristic illustration detector (CV-only).

Reads an image list (JSONL with page/image fields) or glob of images.
Outputs JSONL records with detected boxes for each image.

Example:
. .venv/bin/activate
python scripts/spikes/spike_cropper_cv.py \
  --image-root input/images \
  --images-json configs/groundtruth/image_boxes_eval.jsonl \
  --out /tmp/detections_cv.jsonl
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Dict, Any

import cv2
import numpy as np


def load_image_list(image_root: Path, images_json: Path = None, glob: str = None):
    items = []
    if images_json:
        with images_json.open() as f:
            for line in f:
                if not line.strip():
                    continue
                rec = json.loads(line)
                items.append({"image": rec["image"], "page": rec.get("page")})
    elif glob:
        for path in image_root.glob(glob):
            items.append({"image": path.name, "page": None})
    else:
        raise SystemExit("Provide --images-json or --glob")
    return items


def detect_boxes(image_path: Path, blur: int, min_area_ratio: float, max_area_ratio: float):
    img = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if img is None:
        return []
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur_k = blur if blur % 2 == 1 else blur + 1
    gray = cv2.GaussianBlur(gray, (blur_k, blur_k), 0)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Morph open to drop specks
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    opened = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=1)

    contours, _ = cv2.findContours(opened, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    h, w = gray.shape[:2]
    img_area = w * h
    boxes = []
    for cnt in contours:
        x, y, cw, ch = cv2.boundingRect(cnt)
        area = cw * ch
        ratio = area / img_area
        if ratio < min_area_ratio or ratio > max_area_ratio:
            continue
        # Require reasonable aspect ratio (avoid page-wide gutters)
        aspect = cw / max(ch, 1)
        if aspect > 10 or aspect < 0.05:
            continue
        boxes.append({"x0": int(x), "y0": int(y), "x1": int(x + cw), "y1": int(y + ch)})
    return boxes


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--image-root", default="input/images", type=Path)
    ap.add_argument("--images-json", type=Path, default=None, help="JSONL with page/image fields")
    ap.add_argument("--glob", default=None, help="Glob relative to image-root (e.g., 'img-0*.jpg')")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--blur", type=int, default=5)
    ap.add_argument("--min-area-ratio", type=float, default=0.005)
    ap.add_argument("--max-area-ratio", type=float, default=0.8)
    args = ap.parse_args()

    items = load_image_list(args.image_root, args.images_json, args.glob)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w") as f:
        for item in items:
            path = args.image_root / item["image"]
            boxes = detect_boxes(path, args.blur, args.min_area_ratio, args.max_area_ratio)
            rec = {
                "page": item.get("page"),
                "image": item["image"],
                "boxes": boxes,
            }
            f.write(json.dumps(rec) + "\n")

if __name__ == "__main__":
    main()
