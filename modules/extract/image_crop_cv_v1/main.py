import argparse
import os
from pathlib import Path
from typing import List, Dict, Any

import cv2
from tqdm import tqdm

from modules.common.utils import read_jsonl, save_jsonl, ensure_dir


def detect_boxes(image_path: Path, blur: int, min_area_ratio: float, max_area_ratio: float, topk: int = 3) -> List[Dict[str, int]]:
    img = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if img is None:
        return []
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # aggressive binarization to keep illustrations; lower threshold to avoid losing inked areas
    _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
    blur_k = blur if blur % 2 == 1 else blur + 1
    thresh = cv2.GaussianBlur(thresh, (blur_k, blur_k), 0)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    opened = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=1)
    contours, _ = cv2.findContours(opened, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    h, w = gray.shape[:2]
    img_area = w * h
    cand = []
    for cnt in contours:
        x, y, cw, ch = cv2.boundingRect(cnt)
        area = cw * ch
        ratio = area / img_area
        if ratio < min_area_ratio or ratio > max_area_ratio:
            continue
        aspect = cw / max(ch, 1)
        if aspect > 20 or aspect < 0.05:
            continue
        cand.append((area, {"x0": int(x), "y0": int(y), "x1": int(x + cw), "y1": int(y + ch)}))

    cand = sorted(cand, key=lambda x: x[0], reverse=True)[:topk]
    boxes = [c[1] for c in cand]
    # fallback: full image if nothing found
    if not boxes:
        boxes = [{"x0": 0, "y0": 0, "x1": w, "y1": h}]
    return boxes


def crop_and_save(img_path: Path, boxes: List[Dict[str, int]], out_dir: Path, page: int) -> List[str]:
    img = cv2.imread(str(img_path), cv2.IMREAD_COLOR)
    if img is None:
        return []
    paths = []
    for idx, b in enumerate(boxes):
        x0, y0, x1, y1 = b["x0"], b["y0"], b["x1"], b["y1"]
        crop = img[y0:y1, x0:x1]
        fname = f"page-{page:03d}-crop-{idx}.jpg"
        out_path = out_dir / fname
        cv2.imwrite(str(out_path), crop)
        paths.append(str(out_path))
    return paths


def main():
    parser = argparse.ArgumentParser(description="Detect and crop illustrations from page images (CV heuristic).")
    parser.add_argument("--pages", required=True, help="Input page_doc_v1 JSONL with image paths")
    parser.add_argument("--out", required=True, help="Output JSONL for image_crop_v1 records")
    parser.add_argument("--crop-dir", required=True, help="Directory to write cropped images")
    parser.add_argument("--min-area-ratio", type=float, default=0.005)
    parser.add_argument("--max-area-ratio", type=float, default=0.8)
    parser.add_argument("--blur", type=int, default=5)
    parser.add_argument("--topk", type=int, default=3)
    args = parser.parse_args()

    pages = list(read_jsonl(args.pages))
    crop_dir = Path(args.crop_dir)
    ensure_dir(crop_dir)

    outputs = []
    for p in tqdm(pages, desc="Crop images"):
        img_path = p.get("image")
        if not img_path or not os.path.exists(img_path):
            continue
        boxes = detect_boxes(Path(img_path), args.blur, args.min_area_ratio, args.max_area_ratio, args.topk)
        crops = crop_and_save(Path(img_path), boxes, crop_dir, p.get("page", 0))
        outputs.append({
            "schema_version": "image_crop_v1",
            "module_id": "image_crop_cv_v1",
            "page": p.get("page"),
            "image": img_path,
            "boxes": boxes,
            "crops": crops,
        })

    save_jsonl(args.out, outputs)
    print(f"Wrote {len(outputs)} records → {args.out}")


if __name__ == "__main__":
    main()
